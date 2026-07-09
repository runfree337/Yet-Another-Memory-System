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
#            targeting the configured manifest path or its directory (index/
#            manifest.tsv, index/INDEX.md by default — WORKFLOW.md's navigation
#            channel), OR one of the other channels' index files/dirs
#            (FEATURE_MAP.md/features/, MEMORY.md/memory/, decisions/): routing that
#            happened via the Feature/Memory/Decision channel is a consultation too,
#            not a bypass.
#   covered_zone_reads/searches = Read / Grep+Glob calls landing under one of the
#            configured `roots` — the zones the navigation index is supposed to
#            spare a blind sweep of.
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
# broad-vs-targeted distinction needs a file-existence test per logged search.
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
    """Repo-relative form of a logged path (Claude Code often passes absolute)."""
    p = p.replace("\\", "/").rstrip("/")
    if p == root_abs:
        return "."
    if p.startswith(root_abs + "/"):
        return p[len(root_abs) + 1:]
    return p


index_reads = covered_reads = covered_searches = broad_searches = 0
try:
    lines = open(log_path, encoding="utf-8").read().splitlines()
except OSError:
    sys.exit(3)

for line in lines:
    if line.startswith("#") or "|" not in line:
        continue
    tool, raw = line.split("|", 1)
    p = norm(raw)
    if any(p == c.rstrip("/") or p.startswith(c) for c in consult):
        index_reads += 1
        continue
    # Covered? Same containment as before: a root at the start of the normalized
    # path, or appearing anywhere in the raw string (glob/pattern fallbacks).
    covered = any(p == r or p.startswith(r + "/") or (r + "/") in raw for r in roots)
    if not covered:
        continue
    if tool == "Read":
        covered_reads += 1
    elif tool in ("Grep", "Glob"):
        covered_searches += 1
        # Targeted (logged path = an existing single file) never feeds bypass.
        if not os.path.isfile(os.path.join(root, p)):
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
[[ ! -f "$CSV" ]] && printf '%s\n' "$HEADER" > "$CSV"

ROW="$DATE,$SESSION_ID,$DURATION,$INDEX_READS,$COVERED_READS,$COVERED_SEARCHES,$BYPASS"
TMP=$(mktemp)
grep -v ",${SESSION_ID}," "$CSV" > "$TMP" 2>/dev/null
printf '%s\n' "$ROW" >> "$TMP"
mv "$TMP" "$CSV"

exit 0
