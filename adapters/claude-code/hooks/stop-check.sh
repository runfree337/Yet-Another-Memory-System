#!/usr/bin/env bash
# Stop — one hook PER check, gated on the exit code (checks/README.md §To wire, "Stop wiring").
#
# Unlike the SessionStart sweep (several checks aggregated into 1 line), this pattern is
# ONE hook per check: silent on a clean exit code, otherwise relays the check's full report
# + the fix command. Reserved for end of session (more verbose, an acceptable cost once).
#
# Usage in settings.json: pass the check name (without .py) as the hook's argument.
#   e.g. stop-check.sh index-check
#        stop-check.sh backlog-check
#        stop-check.sh decisions-check
#        stop-check.sh memory-check
#        stop-check.sh feature-map-check
#        stop-check.sh doc-refs-check
set -u

CHECK="${1:-}"
if [ -z "$CHECK" ]; then
  echo "usage: stop-check.sh <check-name>  (e.g. index-check, backlog-check, decisions-check, memory-check, feature-map-check, doc-refs-check)" >&2
  exit 0
fi

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0
cd "$ROOT" || exit 0

PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && exit 0

SCRIPT="checks/${CHECK}.py"
[ -f "$SCRIPT" ] || exit 0

report=$("$PY" "$SCRIPT" 2>&1)
code=$?
[ "$code" -eq 0 ] && exit 0   # silent on clean state

printf '[%s] drift —\n%s\nFix before closing, or rerun `python3 %s`.\n' "$CHECK" "$report" "$SCRIPT"
exit 0   # never blocking — informational only
