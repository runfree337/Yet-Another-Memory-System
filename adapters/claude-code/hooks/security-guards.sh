#!/usr/bin/env bash
# PreToolUse — câblage des trois gardes universelles de ../../../hooks/ (hooks/README.md
# §Câblage par outil), un seul point d'entrée dispatché par tool_name :
#   poisoning-scan   sur Write|Edit
#   secret-scan       sur Bash|Write|Edit
#   destructive-guard sur Bash (décision "ask", jamais un blocage dur)
#
# Chaque garde est appelée avec --stdin-json (elle lit tool_name/tool_input elle-même). Les
# gardes BLOQUANTES (poisoning-scan, secret-scan) court-circuitent sur exit 2 ; destructive-guard
# ne bloque jamais elle-même — elle émet sa propre décision JSON "ask" sur stdout, qu'on laisse
# remonter telle quelle (jamais réécrite ici).
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
    exit "$?"   # toujours 0 — la décision "ask" est portée par le JSON déjà imprimé
    ;;
esac

exit 0
