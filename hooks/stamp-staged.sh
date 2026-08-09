#!/usr/bin/env bash
# stamp-staged.sh — the ONE place that runs the `--stamp --staged` commands.
#
# Home of the `updated` stamp action shared by every pre-commit caller: the git-native
# hook (`adapters/git/pre-commit`) and the Claude Code adapter
# (`adapters/claude-code/hooks/pre-commit-stamp.sh`) both delegate HERE. Two callers that
# each listed the three commands themselves would be two paths saying the same thing —
# they would diverge at the first channel added or flag changed, and the divergence would
# be silent (this is exactly the mirror the single-home rule exists to prevent).
#
# Stamps the three stampable channels on the STAGED entries (backlog/<id>/STATE.md,
# features/*.md, memory/*.md) and re-stages them — the frontmatter date mechanically
# becomes the commit date. Triple safeguard inherited from the called scripts
# (`checks/README.md §Pre-commit wiring`): strictly staged scope, one mechanical field,
# never blocking.
#
# The framework root is derived from THIS FILE's location, not from the caller's cwd or
# any environment variable: the caller chose which copy of this script to invoke (the
# worktree's own, in a worktree), and that choice IS the answer to "which tree?" — a
# second resolution here could only contradict it. Repo-root resolution below this point
# has exactly one home: `entrylib.repo_root`, robust under a git hook's exported
# environment (`entrylib.git_env`).
#
# stdout (the normal "N stamped" counts) is silenced here; stderr is NOT — every
# renunciation the chain announces (unresolvable target, failed git selection) must reach
# the caller's terminal. Audible from a git hook; the Claude Code PreToolUse channel
# swallows stderr on exit 0, which is why the git-native hook is the primary wiring.
set -u

FW="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then
  echo "updated stamp: no python interpreter on PATH, nothing stamped" >&2
  exit 0
fi

"$PY" "$FW/checks/backlog-check.py"     --stamp --staged >/dev/null
"$PY" "$FW/checks/feature-map-check.py" --stamp --staged >/dev/null
"$PY" "$FW/checks/memory-check.py"      --stamp --staged >/dev/null

exit 0   # never blocks — if a write fails, the commit proceeds unstamped
