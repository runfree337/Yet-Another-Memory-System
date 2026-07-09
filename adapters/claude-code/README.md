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
| `hooks/security-guards.sh` | `hooks/poisoning-scan.py`, `hooks/secret-scan.py`, `hooks/destructive-guard.py`, `hooks/normative-write-guard.py` | `PreToolUse(Write\|Edit\|Bash)` |
| `hooks/index-usage-tracker.sh` | none — logs raw `Read`/`Grep`/`Glob` calls to a session-scoped tmp file | `PreToolUse(Read\|Grep\|Glob)` |
| `hooks/index-usage-flush.sh` | `index/index-config.json` (`roots`, `manifest`) | `Stop` | <!-- template -->
| `hooks/index-nudge.sh` | `index/index-config.json` (`roots`, `manifest`, `hub`) + the channel indexes (`FEATURE_MAP.md`, `MEMORY.md`, manifest) | `PostToolUse(Grep\|Glob)` | <!-- template -->
| `hooks/tests/index-hooks-test.sh` | end-to-end tests of `index-nudge.sh` + `index-usage-flush.sh` on a throwaway fixture — run by hand, never wired | — |
| `skills/decisions-audit.md` | `checks/decisions-audit.md` recipe | skill + subagent (on demand / volume) |
| `skills/memory-audit.md` | `checks/memory-audit.md` recipe | skill + subagent (on demand / volume) |

All `.sh` scripts are **silent on success**, except `security-guards.sh` (blocks with a message on
`exit 2`, as prescribed by the guards it calls), `pre-commit-stamp.sh` (never writes as a
blocking step — cf. `checks/README.md §Pre-commit wiring`) and `index-nudge.sh` (its whole job is
to *speak* — a JSON `additionalContext` — but only under the strict conditions listed in its
header, at most once per zone per session, and it never alters or blocks anything). Each script detects `python3`/`python`
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
    ],
    "PostToolUse": [
      {
        "matcher": "Grep|Glob",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/index-nudge.sh\""
          }
        ]
      }
    ]
  }
}
```

**Reading notes:**
- The `SessionStart` sweep also surfaces the **ratification inbox** (`checks/memory-audit.py
  --pending`) as a single `📥 N entrie(s) awaiting ratification` line when non-empty, silent
  otherwise — same zero-tokens-when-clean, exit-code-only discipline as the drift block.
- `Stop` lists 3 checks as an example (`index-check`, `backlog-check`, `decisions-check`) — one
  more hook per check you want recalled in detail before end of session; the `SessionStart` sweep
  already covers all 6 in aggregate. Add `memory-check`/`feature-map-check`/`doc-refs-check` the
  same way if wanted. `index-usage-flush.sh` is listed alongside them — same trigger, but it
  <!-- template -->
  aggregates a metric (`.memory-reports/index-usage.csv`) instead of flagging a drift; silent
  unless the config (`index/index-config.json`) is missing or the session log is empty, in
  <!-- /template -->
  which case it's a silent no-op too.
- `PreToolUse(Write|Edit)` runs `normative-write-guard.py` last, after poisoning-scan and
  secret-scan — it stays silent (no config found or no `normative-paths` match) unless the
  adopting project has a root `capture-policy.json`, in which case a write to a listed path
  turns into an "ask" confirmation instead of a silent auto-approval.
- `PreToolUse(Bash)` carries **two** hooks: `security-guards.sh` (secret-scan + destructive-guard,
  each reading `tool_name`/`tool_input` from its own `--stdin-json`) and `pre-commit-stamp.sh`
  (only acts if the command contains `git commit`, otherwise an immediate no-op). Both receive the
  same JSON on stdin, independently.
- `PreToolUse(Read|Grep|Glob)` carries `index-usage-tracker.sh` — the counterpart of
  `index-usage-flush.sh` above: it only appends a line to a session-scoped tmp file, it doesn't
  read `index-config.json` itself (no per-call config parsing, kept fast and dependency-free);
  the zone classification happens once, at flush time.
- `PostToolUse(Grep|Glob)` carries `index-nudge.sh` — the **active** half of the index-usage
  story: where tracker/flush *measure* bypasses after the fact, the nudge intervenes at the
  moment one happens. It **never substitutes** the cartography for the search (the map is a
  derived representation — an entry that lies is worse than none, `FEATURE_MAP.md`; and a
  targeted grep is often pre-edit verification, where only the real file counts): the search
  runs untouched, and *next to* its raw results the hook injects one `additionalContext` note —
  consult the index, plus up to 3 entries matching the search terms, each with its `updated`
  date so the agent calibrates trust itself. Strictly conditioned (broad search only, covered
  zone only, no cartography consultation yet this session — read from the tracker's log when
  installed —, once per zone per session), silent no-op otherwise, never blocking. Works
  without the tracker; with it, a session that already consulted any channel index is never
  nudged. Tested end-to-end by `hooks/tests/index-hooks-test.sh`.
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
