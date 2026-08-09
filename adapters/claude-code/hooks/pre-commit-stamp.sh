#!/usr/bin/env bash
# PreToolUse(Bash) — the MUTATING case (checks/README.md §Pre-commit wiring).
#
# The only wiring that WRITES rather than flags: delegates to the stamp home
# (`hooks/stamp-staged.sh`), which sets updated=today on the STAGED entries of the three
# stampable channels (backlog/STATE.md, features/*.md, memory/*.md) BEFORE `git commit`
# runs, then re-stages them — the frontmatter date mechanically becomes the commit date,
# with no manual bump that would rot. This adapter does NOT list the stamp commands
# itself: the git-native hook (`adapters/git/pre-commit`) calls the same home, and two
# callers that each carried the list would silently diverge.
#
# Triple safeguard (inherited from the called scripts, cf. checks/README.md):
# (1) strictly STAGED scope — never pulls a file outside the commit in progress;
# (2) MECHANICAL field touched (a date), never a judgment;
# (3) NEVER BLOCKING — if the write fails, the commit proceeds anyway, unstamped.
#
# SCOPE OF THIS CHANNEL — a catch-up net, not the primary wiring. It only fires when the
# agent's Bash call CONTAINS `git commit`; a commit made by hand, from an IDE or a script
# never goes through PreToolUse at all. And a PreToolUse hook exiting 0 has its stderr
# swallowed (probed), so the home's renunciations are inaudible here. The primary wiring
# is the git-native hook, which covers every `git commit` and whose stderr reaches the
# terminal — this adapter remains for machines where `core.hooksPath` is not (yet)
# installed, which the SessionStart sweep surfaces as an actionable command.
#
# The hook receives the JSON {tool_name, tool_input} on stdin; it only acts if the Bash
# command contains "git commit" (the settings.json matcher already filters on the "Bash"
# tool — the substring test, unlike a `git commit*` prefix matcher, also catches a
# chained `git add … && git commit …` in one call).
set -u

INPUT="$(cat)"
case "$INPUT" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0
[ -f "$ROOT/hooks/stamp-staged.sh" ] || exit 0   # nested host: adjust this path

bash "$ROOT/hooks/stamp-staged.sh"

exit 0   # never blocks — the correction is silent, git commit sees the stamp
