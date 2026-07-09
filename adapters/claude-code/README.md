# `adapters/claude-code/` — Claude Code materialization of the wiring

> **Role.** `checks/README.md` and `hooks/README.md` describe the wiring as **tables** (which
> guard, which trigger, which tool) and illustrative `sh` skeletons — agnostic by construction, to
> stay valid outside Claude Code. This folder is the **concrete materialization** of those tables
> for **Claude Code**: real, executable hook files, plus a `settings.json` fragment that wires
> them in. This is the **first brick** of the future `install.py` (`INSTALL.md §Target shape`):
> when the installer detects Claude Code as the host, it will copy this folder and offer this
> fragment instead of generating the glue on the fly.
>
> Nothing here reimplements a guard or a check — every script in this folder only **calls** a
> script from `../../checks/` or `../../hooks/` with the right arguments, at the right trigger.
> The logic stays **canonical** in `checks/`/`hooks/`; here, only the glue.

## Inventory

| File | Wraps | Claude Code trigger |
|---|---|---|
| `hooks/session-start-sweep.sh` | `checks/*.py` (6 structural checks), aggregated | `SessionStart` |
| `hooks/stop-check.sh <check-name>` | one `checks/<check-name>.py`, in detail | `Stop` (one hook per desired check) |
| `hooks/pre-commit-stamp.sh` | `checks/backlog-check.py --stamp --staged` | `PreToolUse(Bash)`, before `git commit` |
| `hooks/security-guards.sh` | `hooks/poisoning-scan.py`, `hooks/secret-scan.py`, `hooks/destructive-guard.py` | `PreToolUse(Write\|Edit\|Bash)` |
| `hooks/index-usage-tracker.sh` | none — logs raw `Read`/`Grep`/`Glob` calls to a session-scoped tmp file | `PreToolUse(Read\|Grep\|Glob)` |
| `hooks/index-usage-flush.sh` | `index/index-config.json` (`roots`, `manifest`) | `Stop` |
| `skills/decisions-audit.md` | `checks/decisions-audit.md` recipe | skill + subagent (on demand / volume) |
| `skills/memory-audit.md` | `checks/memory-audit.md` recipe | skill + subagent (on demand / volume) |

All `.sh` scripts are **silent on success**, except `security-guards.sh` (blocks with a message on
`exit 2`, as prescribed by the guards it calls) and `pre-commit-stamp.sh` (never writes as a
blocking step — cf. `checks/README.md §Pre-commit wiring`). Each script detects `python3`/`python`
and resolves the repo root via `$CLAUDE_PROJECT_DIR` (provided by Claude Code) or, failing that,
`git rev-parse --show-toplevel` — no hardcoded absolute path.

## `settings.json` fragment

<!-- template -->
To merge into `.claude/settings.json` (or `.claude/settings.local.json`) of the project adopting
the framework — paths **on the adopting project's side**, not in this repo (YAMS is not itself a
Claude Code consumer).
<!-- /template -->

As everywhere in this framework (`INSTALL.md §Guiding principle`): this is a **proposal**, not
imposed wiring — each block can be adopted separately.

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/session-start-sweep.sh\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/stop-check.sh\" index-check"
          },
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/stop-check.sh\" backlog-check"
          },
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/stop-check.sh\" decisions-check"
          },
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/index-usage-flush.sh\""
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/security-guards.sh\""
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/security-guards.sh\""
          },
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/pre-commit-stamp.sh\""
          }
        ]
      },
      {
        "matcher": "Read|Grep|Glob",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/index-usage-tracker.sh\""
          }
        ]
      }
    ]
  }
}
```

**Reading notes:**
- `Stop` lists 3 checks as an example (`index-check`, `backlog-check`, `decisions-check`) — one
  more hook per check you want recalled in detail before end of session; the `SessionStart` sweep
  already covers all 6 in aggregate. Add `memory-check`/`feature-map-check`/`doc-refs-check` the
  same way if wanted. `index-usage-flush.sh` is listed alongside them — same trigger, but it
  aggregates a metric (`.memory-reports/index-usage.csv`) instead of flagging a drift; silent
  unless the config (`index/index-config.json`) is missing or the session log is empty, in
  which case it's a silent no-op too.
- `PreToolUse(Bash)` carries **two** hooks: `security-guards.sh` (secret-scan + destructive-guard,
  each reading `tool_name`/`tool_input` from its own `--stdin-json`) and `pre-commit-stamp.sh`
  (only acts if the command contains `git commit`, otherwise an immediate no-op). Both receive the
  same JSON on stdin, independently.
- `PreToolUse(Read|Grep|Glob)` carries `index-usage-tracker.sh` — the counterpart of
  `index-usage-flush.sh` above: it only appends a line to a session-scoped tmp file, it doesn't
  read `index-config.json` itself (no per-call config parsing, kept fast and dependency-free);
  the zone classification happens once, at flush time.
- The semantic audit (`skills/decisions-audit.md`, `skills/memory-audit.md`) **never** appears in
  `settings.json` — it's not a hook, cf. `checks/README.md §Semantic — agent,
  memory<->code`. It triggers via skill (on demand) or the OS cron job's report loop
  (`INSTALL.md step 5`).

## Skill/subagent templates

`skills/decisions-audit.md` and `skills/memory-audit.md` are **not** scripts — they are text
templates in Claude Code's skill/subagent format, which **point** to the canonical scale
(`checks/decisions-audit.md`, `checks/memory-audit.md`) without ever duplicating it: they only
specify which script to run, which scale to load, which output format to render. Adapting to the
concrete format of a Claude Code skill/subagent (frontmatter, file name under `.claude/skills/` /
`.claude/agents/`) is up to the installer or a manual copy — the business content doesn't change.
