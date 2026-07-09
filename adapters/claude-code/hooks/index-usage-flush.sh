#!/usr/bin/env bash
# Stop hook: aggregate the session's tracker log (index-usage-tracker.sh) and upsert
# one row in $YAMS_MEMORY_REPORT_DIR/index-usage.csv, keyed by session_id. Stop fires
# every turn, so the row is replaced on each flush — the file grows monotonically
# across turns/sessions. The tmp log naturally evaporates when the container is
# reclaimed.
#
# AGNOSTIC by construction (checks/index-check.py §graceful degradation): the
# "covered zones" measured against are NOT hardcoded — they're derived from the
# `roots` array of index/index-config.json, the same config the framework's own
# index-check.py/manifest.py read. No config -> nothing to measure -> exit 0,
# silently, no file written. Parsed with python3 (a hard dependency of every YAMS
# check already), never jq.
#
# Schema: date,session_id,duration_min,index_reads,covered_zone_reads,
#         covered_zone_searches,bypass
#   index_reads = cartography *consultations* this session — a Read or Grep/Glob
#            whose logged VALUE is a path (tracker KIND=path, see
#            index-usage-tracker.sh's header) targeting the configured manifest
#            path or its directory (index/manifest.tsv, index/INDEX.md by
#            default — WORKFLOW.md's navigation channel), OR one of the other
#            channels' index files/dirs (FEATURE_MAP.md/features/,
#            MEMORY.md/memory/, decisions/): routing that happened via the
#            Feature/Memory/Decision channel is a consultation too, not a
#            bypass. A KIND=glob or KIND=pattern line is never a consultation,
#            however it happens to read (a Grep for the literal word "memory"
#            is not a visit to memory/).
#   covered_zone_reads/searches = Read / Grep+Glob calls landing under one of the
#            configured `roots` — the zones the navigation index is supposed to
#            spare a blind sweep of. For KIND=path lines this is a direct
#            containment check on the (repo-relative) value; for KIND=glob
#            lines only the glob's literal (non-wildcard) prefix is tested;
#            KIND=pattern (a bare Grep regex) never counts — no substring
#            matching against roots anywhere.
#   bypass = the BROAD covered searches when index_reads == 0 this session (= swept
#            a covered zone without ever consulting the cartography first). A
#            TARGETED search — its logged path resolves to an existing single file —
#            never counts: knowing already which file to grep is the outcome the
#            index exists to produce, wherever that routing came from.

set +e

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0
cd "$ROOT" || exit 0

PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && exit 0

CONFIG="$ROOT/index/index-config.json"
[ -f "$CONFIG" ] || exit 0   # not opted into the per-file index -> nothing to measure

SESSION_ID="${CLAUDE_CODE_SESSION_ID:-unknown}"
LOG="${TMPDIR:-/tmp}/yams-index-usage-${SESSION_ID}.log"
[ -f "$LOG" ] || exit 0

# Classify the log against the config (covered zones from `roots`, consultation
# paths from the directory of `manifest` + the channel constants). One line on
# stdout on success: "index_reads covered_reads covered_searches bypass". Exits 3
# if the config has no usable `roots` (same graceful no-op as checks/index-check.py
# when roots/extensions are empty). Done in python rather than grep -c because the
# broad-vs-targeted distinction needs a file-existence test per logged search, and
# because the log's KIND field (see index-usage-tracker.sh's header) needs
# kind-specific handling: only kind=path lines are locations directly comparable to
# `roots`/consult paths; kind=glob lines only contribute their glob's literal
# (non-wildcard) prefix; kind=pattern (a bare Grep regex) is never a location and
# never counts toward index_reads or coverage — no substring matching anywhere.
COUNTS=$("$PY" - "$ROOT" "$CONFIG" "$LOG" <<'PYEOF'
import json
import os
import sys

# The other channels' index files/dirs — framework constants, hardcoded like in
# checks/memory-check.py; reading any of them counts as consulting the cartography.
CHANNEL_PATHS = ("FEATURE_MAP.md", "features/", "MEMORY.md", "memory/", "decisions/")

root, config_path, log_path = sys.argv[1:4]
root_abs = os.path.abspath(root).replace("\\", "/")

try:
    with open(config_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
except (OSError, json.JSONDecodeError):
    sys.exit(3)

roots = [r.rstrip("/") for r in (cfg.get("roots") or []) if r and r.strip("/")]
if not roots:
    sys.exit(3)

manifest = cfg.get("manifest", "index/manifest.tsv")
index_dir = (os.path.dirname(manifest) or "index").rstrip("/")
consult = CHANNEL_PATHS + (index_dir + "/",)


def norm(p):
    """Repo-relative form of a logged path (Claude Code often passes absolute).
    Resolves symlinks on both sides (root always; the value only when it's
    absolute — a relative value is already repo-relative and must not be
    resolved against this script's cwd)."""
    root_r = os.path.realpath(root_abs).replace("\\", "/").rstrip("/")
    p = p.replace("\\", "/").rstrip("/")
    if p.startswith("/"):
        p = os.path.realpath(p).replace("\\", "/").rstrip("/")
    if p == root_r:
        return "."
    if p.startswith(root_r + "/"):
        return p[len(root_r) + 1:]
    return p


def glob_literal_prefix(pattern):
    """Literal (non-wildcard) prefix of a glob pattern, up to the first `*`,
    `?`, `[` or `{` — the only part of a glob that's a location."""
    for i, ch in enumerate(pattern or ""):
        if ch in "*?[{":
            return pattern[:i]
    return pattern or ""


def parse_line(line):
    """Parse one tracker log line into (tool, kind, value), or None for a
    comment/blank/malformed line. Tolerates legacy 2-field 'TOOL|value' lines
    (kind defaults to 'path') from a log started before the 3-field format
    landed — a mixed log mid-session should still degrade gracefully."""
    if not line or line.startswith("#") or "|" not in line:
        return None
    parts = line.split("|", 2)
    if len(parts) == 2:
        return parts[0], "path", parts[1]
    return parts[0], parts[1], parts[2]


index_reads = covered_reads = covered_searches = broad_searches = 0
try:
    lines = open(log_path, encoding="utf-8", errors="replace").read().splitlines()
except OSError:
    sys.exit(3)

for line in lines:
    parsed = parse_line(line)
    if not parsed:
        continue
    tool, kind, value = parsed

    if kind == "path":
        p = norm(value)
        if any(p == c.rstrip("/") or p.startswith(c) for c in consult):
            index_reads += 1
            continue
        covered = any(p == r or p.startswith(r + "/") for r in roots)
        # Targeted (logged path = an existing single file) never feeds bypass.
        targeted = os.path.isfile(os.path.join(root, p))
    elif kind == "glob":
        # The log carries no separate directory for a glob line (the tracker
        # logs path OR glob OR pattern, never a combination) — only the glob's
        # own literal prefix is tested for containment.
        p = norm(glob_literal_prefix(value))
        covered = any(p == r or p.startswith(r + "/") for r in roots)
        targeted = False  # a glob sweep is never a single targeted file
    else:  # kind == "pattern": a bare regex is never a location
        covered = False
        targeted = False

    if not covered:
        continue
    if tool == "Read":
        covered_reads += 1
    elif tool in ("Grep", "Glob"):
        covered_searches += 1
        if not targeted:
            broad_searches += 1

bypass = broad_searches if index_reads == 0 else 0
print(index_reads, covered_reads, covered_searches, bypass)
PYEOF
)
[ $? -ne 0 ] && exit 0
[ -z "$COUNTS" ] && exit 0

CSV="${YAMS_MEMORY_REPORT_DIR:-.memory-reports}/index-usage.csv"
mkdir -p "$(dirname "$CSV")"

START=$(grep -m1 '^# session_start=' "$LOG" 2>/dev/null | cut -d= -f2)
[[ -z "$START" ]] && START=$(date -u +%s)
NOW=$(date -u +%s)
DURATION=$(( (NOW - START + 30) / 60 ))
DATE=$(date -u +%Y-%m-%d)

read -r INDEX_READS COVERED_READS COVERED_SEARCHES BYPASS <<< "$COUNTS"

# Skip writing entirely if the session never touched anything relevant.
TOTAL=$((INDEX_READS + COVERED_READS + COVERED_SEARCHES))
[[ "$TOTAL" -eq 0 ]] && exit 0

HEADER='date,session_id,duration_min,index_reads,covered_zone_reads,covered_zone_searches,bypass'
[[ ! -s "$CSV" ]] && printf '%s\n' "$HEADER" > "$CSV"

ROW="$DATE,$SESSION_ID,$DURATION,$INDEX_READS,$COVERED_READS,$COVERED_SEARCHES,$BYPASS"
TMP=$(mktemp)
grep -v ",${SESSION_ID}," "$CSV" > "$TMP" 2>/dev/null
printf '%s\n' "$ROW" >> "$TMP"
mv "$TMP" "$CSV"

exit 0
