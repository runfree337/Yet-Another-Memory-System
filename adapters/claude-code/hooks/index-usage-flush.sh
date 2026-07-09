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
#   index_reads = index *consultations* this session — a Read or Grep/Glob targeting
#            the configured manifest path or its directory (index/manifest.tsv,
#            index/INDEX.md by default — WORKFLOW.md's navigation channel).
#   covered_zone_reads/searches = Read / Grep+Glob calls landing under one of the
#            configured `roots` — the zones the navigation index is supposed to
#            spare a blind sweep of.
#   bypass = covered_zone_searches when index_reads == 0 this session (= searched a
#            covered zone without ever consulting the index first).

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

# Derive the covered-zone regex from `roots`, and the index-consultation regex from
# the directory of `manifest` (defaults: index/index-config.example.json). Two lines
# on stdout on success; exits 3 if the config has no usable `roots` (same graceful
# no-op as checks/index-check.py when roots/extensions are empty).
CFG_OUT=$("$PY" - "$CONFIG" <<'PYEOF'
import json
import os
import re
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        cfg = json.load(fh)
except (OSError, json.JSONDecodeError):
    sys.exit(3)

roots = cfg.get("roots") or []
if not roots:
    sys.exit(3)

covered_re = "|".join(re.escape(r.rstrip("/")) + "/" for r in roots)

manifest = cfg.get("manifest", "index/manifest.tsv")
index_dir = os.path.dirname(manifest) or "index"
index_re = re.escape(index_dir) + "/"

print(covered_re)
print(index_re)
PYEOF
)
[ $? -ne 0 ] && exit 0
COVERED_RE=$(printf '%s\n' "$CFG_OUT" | sed -n '1p')
INDEX_RE=$(printf '%s\n' "$CFG_OUT" | sed -n '2p')
[ -z "$COVERED_RE" ] && exit 0

CSV="${YAMS_MEMORY_REPORT_DIR:-.memory-reports}/index-usage.csv"
mkdir -p "$(dirname "$CSV")"

START=$(grep -m1 '^# session_start=' "$LOG" 2>/dev/null | cut -d= -f2)
[[ -z "$START" ]] && START=$(date -u +%s)
NOW=$(date -u +%s)
DURATION=$(( (NOW - START + 30) / 60 ))
DATE=$(date -u +%Y-%m-%d)

INDEX_READS=$(grep -cE "^(Read|Grep|Glob)\|.*${INDEX_RE}" "$LOG")
COVERED_READS=$(grep -cE "^Read\|.*(${COVERED_RE})" "$LOG")
COVERED_SEARCHES=$(grep -cE "^(Grep|Glob)\|.*(${COVERED_RE})" "$LOG")

BYPASS=0
[[ "$INDEX_READS" -eq 0 && "$COVERED_SEARCHES" -gt 0 ]] && BYPASS=$COVERED_SEARCHES

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
