#!/usr/bin/env bash
# SessionStart — sweep structurel MUET (checks/README.md §À câbler).
#
# Agrège plusieurs checks/*.py en démarrage de session : RIEN imprimé si tout est propre (0 token
# injecté dans le contexte), une ligne terse par dérive sinon. Keyer sur le code retour, jamais
# parser un rapport localisé/accentué — cf. la « Règle du silence » du README cité ci-dessus.
#
# Détecte aussi un rapport d'audit sémantique en attente (produit hors session par le cron OS,
# cf. INSTALL.md étape 5) : ne le traite jamais lui-même, se contente de le SURFACER — l'agent
# demande, l'utilisateur décide.
set -u

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0
cd "$ROOT" || exit 0

PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && exit 0

lines=""

"$PY" checks/decisions-check.py   >/dev/null 2>&1
[ "$?" -eq 2 ] && lines="${lines}• décisions: dérive (python3 checks/decisions-check.py)\n"

"$PY" checks/backlog-check.py     >/dev/null 2>&1
[ "$?" -eq 2 ] && lines="${lines}• backlog: erreur (python3 checks/backlog-check.py)\n"

"$PY" checks/feature-map-check.py >/dev/null 2>&1
[ "$?" -eq 2 ] && lines="${lines}• feature-map: erreur (python3 checks/feature-map-check.py)\n"

"$PY" checks/memory-check.py      >/dev/null 2>&1
[ "$?" -eq 2 ] && lines="${lines}• mémoire: erreur (python3 checks/memory-check.py)\n"

"$PY" checks/index-check.py       >/dev/null 2>&1
[ "$?" -eq 2 ] && lines="${lines}• index: dérive (python3 checks/index-check.py)\n"

"$PY" checks/doc-refs-check.py 2>/dev/null | grep -q BLOQUANT
[ "$?" -eq 0 ] && lines="${lines}• doc: réf morte (python3 checks/doc-refs-check.py)\n"

[ -n "$lines" ] && printf "⚠️ dérive structurelle au démarrage :\n%b" "$lines"

REPORT="${UC_MEMORY_REPORT_DIR:-.memory-reports}/memory-report.md"
[ -f "$REPORT" ] && printf "📋 rapport mémoire en attente: %s — DEMANDER à l'utilisateur de le traiter, puis le supprimer.\n" "$REPORT"

exit 0   # jamais bloquant ; MUET si ni dérive ni rapport → 0 token injecté
