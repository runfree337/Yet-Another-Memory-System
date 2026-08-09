# Git adapter — native hooks

The wiring surface for plain git, no agent in the loop. One file today:

| File | Delegates to | Trigger |
|---|---|---|
| `pre-commit` | `hooks/stamp-staged.sh` (the `updated` stamp home) | every `git commit` |

**Install, once per clone/machine** (`.git/hooks/` is not versioned):

```sh
git config core.hooksPath adapters/git
```

or copy `pre-commit` into the active hooks directory — the `SessionStart` sweep
(`adapters/claude-code/hooks/session-start-sweep.sh`) recognizes an up-to-date copy, and
surfaces the missing/stale/non-executable cases as an actionable command.

Why a git-native hook when the Claude Code adapter already has `pre-commit-stamp.sh`: the
`PreToolUse` channel only sees the **agent's** commits. Commits made by hand, from an IDE,
a script or CI never went through it — measured on a real adoption as weeks of silent
`updated` drift. This hook covers them all, and every case where it **renounces** (merge
and other sister-head commits, partial-commit temporary index, unresolvable root) is said
on stderr — where a git hook's voice actually reaches the terminal. Scope and known holes
are stated once, in `backlog/README.md` (the `updated` field); the mechanics and their
traps in the hook's own header; the wiring doctrine in `checks/README.md §Pre-commit
wiring`.

Contributor note: this file must stay **indexed in mode 100755** (`git add --chmod=+x` /
`git update-index --chmod=+x adapters/git/pre-commit`) — under `core.filemode=false` a
100644-indexed hook is silently skipped on every POSIX clone.
