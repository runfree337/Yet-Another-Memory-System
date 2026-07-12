#!/usr/bin/env bash
# PostToolUse(Grep|Glob) — glue for two INDEPENDENT nudge sources sharing one
# trigger and one stdin JSON:
#   1. `hooks/index-nudge.py` (canonical logic + firing conditions documented
#      there, `--stdin-json` entry) — points at the navigation index + the
#      entries matching the search. Opt-in on `index/index-config.json`.
#   2. `hooks/memory-graph.py --mode match` (the memory-graph engine) — points
#      at the DECISIONS/FEATURES whose ids/titles/tags/roles match the search
#      terms. Opt-in on `hooks/memory-graph.py` existing.
# Same trigger, same JSON, two unrelated notes side by side: the index nudge
# reports the map (paths), the graph nudge reports the memories (nodes).
# Neither reimplements the other; this wrapper only resolves the repo root and
# the session-scoped state files. Silent no-op when a source isn't installed;
# never blocks — always exit 0.

set +e

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0

PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && exit 0

SESSION_ID="${CLAUDE_CODE_SESSION_ID:-unknown}"
INPUT="$(cat)"   # captured once — fed to both consumers below

if [ -f "$ROOT/index/index-config.json" ] && [ -f "$ROOT/hooks/index-nudge.py" ]; then
  printf '%s' "$INPUT" | "$PY" "$ROOT/hooks/index-nudge.py" --stdin-json --root "$ROOT" \
    --track-log "${TMPDIR:-/tmp}/yams-index-usage-${SESSION_ID}.log" \
    --marker "${TMPDIR:-/tmp}/yams-index-nudge-${SESSION_ID}.log"
fi

if [ -f "$ROOT/hooks/memory-graph.py" ]; then
  printf '%s' "$INPUT" | "$PY" "$ROOT/hooks/memory-graph.py" --root "$ROOT" --stdin-json --mode match \
    --marker "${TMPDIR:-/tmp}/yams-memory-match-${SESSION_ID}.log"
fi

exit 0
