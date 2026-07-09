# `hooks/` — universal guards (portable) + per-tool wiring

> Second family of controls, alongside `checks/`. A **hook** = a **guard** (portable
> logic, here in Python stdlib) **+** a **trigger point** (mechanism specific to
> the tool). The guard lives here, **canonical**; a **per-tool installer** wires it to the
> right trigger. None of them fix anything: they **report** / ask for confirmation.

## Guards provided (universal, agnostic)

| Guard | What it catches | Verdict |
|---|---|---|
| `poisoning-scan.py` | **invisible/bidi** Unicode in instruction & memory files (a "TrapDoor" poisoning vector) | exit 2 = block |
| `secret-scan.py` | committed **keys/tokens** (18 patterns) — Anthropic, AWS, GitHub, Slack, Stripe… | exit 2 = block |
| `destructive-guard.py` | broad **destructive** shell commands (`find -delete`, `-exec rm`) | "ask" (confirm) |

Each one is **portable** (stdlib, no dependency) and offers two entry points:
- **universal**: `--staged` (git-staged content — pre-commit / CI) or paths as arguments;
- **Claude Code adapter**: `--stdin-json` (reads the hook's `tool_name`/`tool_input` JSON).

```bash
python3 hooks/poisoning-scan.py --staged
python3 hooks/secret-scan.py --staged
python3 hooks/destructive-guard.py --command "find . -name '*.tmp' -delete"
```

## Wiring per tool — what the installer materializes

The **trigger** is tool-specific; the guard is not. Materialization table:

| Guard | When | Claude Code | Git / CI |
|---|---|---|---|
| poisoning-scan | session start · before writing an instruction file | `SessionStart` / `PreToolUse(Write\|Edit)` hook → `--stdin-json` | `pre-commit` → `--staged` |
| secret-scan | before a commit · before writing | `PreToolUse(Bash\|Write\|Edit)` hook → `--stdin-json` | `pre-commit` → `--staged` |
| destructive-guard | before a shell command | `PreToolUse(Bash)` hook → `--stdin-json` ("ask" decision) | `pre-commit` (exit 2 = block) |

> The `checks/` **method controls** (`backlog-check`, `decisions-check`, `memory-audit`)
> also get wired as hooks — typically `Stop` (end of task) / `SessionStart` (post-merge
> drift) on the Claude Code side, or a CI job. See `../checks/README.md`.

## What is NOT here — the project brings it

**Tech-specific** guards/controls (lint, tests, analyzers, host-language style
standards) belong to the **project**, not the process. Here: only the **universal**
guards (security, integrity) that every team wants, regardless of language.

## Installer model (to come)

A per-tool installer (Claude Code, Copilot…) will read this folder + `../checks/` and
**generate** the concrete artifacts — hook files, config entries
(`settings.json`, `.pre-commit-config.yaml`, CI workflow…) — pointing each guard to its
trigger via the table above. The logic is **never** rewritten: only the wiring
glue differs. Embedded Claude Code implementation: `adapters/claude-code/hooks/security-guards.sh` +
`adapters/claude-code/README.md` (the `settings.json` fragment that wires it all up).
