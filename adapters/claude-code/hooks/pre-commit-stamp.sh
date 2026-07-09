#!/usr/bin/env bash
# PreToolUse(Bash) — le cas MUTANT (checks/README.md §Câblage pré-commit).
#
# Seul câblage qui ÉCRIT plutôt que signaler : pose updated=aujourd'hui sur les entrées STAGÉES
# des trois canaux stampables (backlog/STATE.md, features/*.md, memory/*.md),
# AVANT que `git commit` ne s'exécute, puis les re-stage — la date du frontmatter devient
# mécaniquement la date du commit, sans bump manuel qui pourrit.
#
# Triple garde-fou (repris du script appelé, checks/backlog-check.py --stamp --staged) :
# (1) scope strictement STAGÉ — ne tire jamais un fichier hors du commit en cours ;
# (2) champ touché MÉCANIQUE (une date), jamais un jugement ;
# (3) JAMAIS BLOQUANT — si l'écriture échoue, le commit part quand même, non tamponné.
#
# Le hook reçoit le JSON {tool_name, tool_input} sur stdin ; on n'agit que si la commande
# Bash contient "git commit" (le matcher settings.json filtre déjà sur l'outil "Bash").
set -u

INPUT="$(cat)"
case "$INPUT" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0
cd "$ROOT" || exit 0

PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && exit 0

"$PY" checks/backlog-check.py     --stamp --staged >/dev/null 2>&1
"$PY" checks/feature-map-check.py --stamp --staged >/dev/null 2>&1
"$PY" checks/memory-check.py      --stamp --staged >/dev/null 2>&1

exit 0   # ne bloque jamais — la correction est silencieuse, git commit voit le stamp
