#!/usr/bin/env bash
# PreToolUse — wiring for the three universal guards of ../../../hooks/ (hooks/README.md
# §Wiring by tool), a single entry point dispatched by tool_name:
#   poisoning-scan    on Write|Edit
#   secret-scan       on Bash|Write|Edit
#   destructive-guard on Bash ("ask" decision, never a hard block)
#
# Each guard is called with --stdin-json (it reads tool_name/tool_input itself). The
# BLOCKING guards (poisoning-scan, secret-scan) short-circuit on exit 2; destructive-guard
# never blocks itself — it emits its own "ask" JSON decision on stdout, which is passed
# through untouched here.
set -u

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0
cd "$ROOT" || exit 0

PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && exit 0

INPUT="$(cat)"
TOOL=$(printf '%s' "$INPUT" | "$PY" -c 'import json,sys
try:
    print(json.load(sys.stdin).get("tool_name",""))
except Exception:
    print("")' 2>/dev/null)

case "$TOOL" in
  Write|Edit)
    printf '%s' "$INPUT" | "$PY" hooks/poisoning-scan.py --stdin-json
    [ "$?" -eq 2 ] && exit 2

    printf '%s' "$INPUT" | "$PY" hooks/secret-scan.py --stdin-json
    [ "$?" -eq 2 ] && exit 2
    ;;
  Bash)
    printf '%s' "$INPUT" | "$PY" hooks/secret-scan.py --stdin-json
    [ "$?" -eq 2 ] && exit 2

    printf '%s' "$INPUT" | "$PY" hooks/destructive-guard.py --stdin-json
    exit "$?"   # always 0 — the "ask" decision is carried by the already-printed JSON
    ;;
esac

exit 0
