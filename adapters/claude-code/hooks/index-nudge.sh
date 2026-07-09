#!/usr/bin/env bash
# PostToolUse(Grep|Glob) — glue for `hooks/index-nudge.py` (canonical logic + all
# the firing conditions documented there, `--stdin-json` entry). This wrapper only
# resolves the repo root and the session-scoped state files: the consultation log
# written by index-usage-tracker.sh (when installed) and the once-per-zone marker.
# Silent no-op without `index/index-config.json`; never blocks — always exit 0.

set +e

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0
[ -f "$ROOT/index/index-config.json" ] || exit 0

PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && exit 0
[ -f "$ROOT/hooks/index-nudge.py" ] || exit 0  # adopting project didn't copy the hook

SESSION_ID="${CLAUDE_CODE_SESSION_ID:-unknown}"
"$PY" "$ROOT/hooks/index-nudge.py" --stdin-json --root "$ROOT" \
  --track-log "${TMPDIR:-/tmp}/yams-index-usage-${SESSION_ID}.log" \
  --marker "${TMPDIR:-/tmp}/yams-index-nudge-${SESSION_ID}.log"

exit 0
