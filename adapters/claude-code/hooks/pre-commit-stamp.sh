#!/usr/bin/env bash
# PreToolUse(Bash) — the MUTATING case (checks/README.md §Pre-commit wiring).
#
# The only wiring that WRITES rather than flags: sets updated=today on the STAGED entries
# of the three stampable channels (backlog/STATE.md, features/*.md, memory/*.md),
# BEFORE `git commit` runs, then re-stages them — the frontmatter date mechanically
# becomes the commit date, with no manual bump that would rot.
#
# Triple safeguard (inherited from the called script, checks/backlog-check.py --stamp --staged):
# (1) strictly STAGED scope — never pulls a file outside the commit in progress;
# (2) MECHANICAL field touched (a date), never a judgment;
# (3) NEVER BLOCKING — if the write fails, the commit proceeds anyway, unstamped.
#
# The hook receives the JSON {tool_name, tool_input} on stdin; it only acts if the Bash
# command contains "git commit" (the settings.json matcher already filters on the "Bash" tool).
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

exit 0   # never blocks — the correction is silent, git commit sees the stamp
