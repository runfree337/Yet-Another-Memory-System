#!/usr/bin/env bash
# Stop — un hook PAR check, gated sur le code retour (checks/README.md §À câbler, « Câblage Stop »).
#
# Contrairement au sweep SessionStart (plusieurs checks agrégés en 1 ligne), ce patron est
# UN hook par check : muet sur code retour propre, sinon relaie le rapport complet du check
# + la commande de correctif. Réservé à la fin de session (plus verbeux, coût acceptable une fois).
#
# Usage dans settings.json : passer le nom du check (sans .py) en argument du hook.
#   ex. stop-check.sh index-check
#       stop-check.sh backlog-check
#       stop-check.sh decisions-check
#       stop-check.sh memory-check
#       stop-check.sh feature-map-check
#       stop-check.sh doc-refs-check
set -u

CHECK="${1:-}"
if [ -z "$CHECK" ]; then
  echo "usage: stop-check.sh <nom-du-check>  (ex. index-check, backlog-check, decisions-check, memory-check, feature-map-check, doc-refs-check)" >&2
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
[ "$code" -eq 0 ] && exit 0   # muet sur état propre

printf '[%s] dérive —\n%s\nCorrige avant de clore, ou relance `python3 %s`.\n' "$CHECK" "$report" "$SCRIPT"
exit 0   # jamais bloquant — informe seulement
