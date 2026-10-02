# Claude Code template — skill `deliver-work-item`

> Claude Code packaging of the canonical recipe **`../../../DELIVERY.md`** (how to carry a work
> item through its phases) over the protocol **`../../../backlog/README.md §Phases`** (what each
> gate requires). This template redefines NEITHER — it only says what Claude Code changes: the
> trigger, the delegation tool, and the **roles table the project fills in**. Install it as
> `.claude/skills/<name>/SKILL.md` under the project's own name for it.

## Skill `deliver-work-item`

**Trigger** — a doc-backed work item to resume, drive or close; a batch about to go to a
subagent; "carry this work item", "execute this work item". Opening a new work item: write the
intent in `spec.md`, open it in `framing`, and **ask the user whether to frame it now**. A work
item still in `framing` is framed **with** the user (a questioning skill, one question at a time
with a recommended answer) — the AI never carries it alone before `validated:` is set on the
user's explicit approval.

**Steps** — the loop of `DELIVERY.md §The loop`, phase by phase, one commit per gate passed. Run
`backlog-check.py` after each gate: it proves the gate files are where the phase says they are.

## What Claude Code changes

- **Delegation = the `Agent` tool.** Pass `model` **explicitly** on every call — the call's
  parameter overrides the agent definition's `model:`, and the default decides otherwise. The
  `Agent` tool does not set the reasoning effort: only an agent definition's frontmatter does, so
  a batch that needs a given effort goes to the agent type that carries it.
- **An auditor agent is read-only.** Its report comes back to the orchestrator, which writes
  `audit-plan.md` (and `validation.md`) itself — `verdict: pass` only when no blocking finding is
  left open. The audit is never DONE in the context that wrote what it audits: the orchestrator
  launches the auditor as a fresh subagent and copies its report — that is what makes it independent.
  A re-audit (after a FAIL, or a plan amended in `build`) is committed WITH `audit-plan.md`: its
  last commit is the gate `E-PLAN-DRIFT` measures the plan against. An amendment in `build` gets a
  SHORT audit: the auditor is told to judge the amendment only, against the code already
  delivered — not to re-audit the whole plan, and not to assume nothing is built.
- **Foreground or background**: a gate the next step depends on (the plan audit) runs in the
  foreground; independent batches run in the background, launched in one message.
- **Tools that drive a shared application** (an editor bridge, a device) can stall or vanish in a
  subagent — the batch prompt says which interface the agent uses, and the orchestrator re-runs
  the proof itself on return (`DELIVERY.md §The proof is never delegated`).
- **`isolation: "worktree"`** suits only a batch that needs no shared resource; choosing it over
  the main checkout is the user's call.

## Roles — filled in by the project

The framework names the phases; the project names who does each. Keep this table in the
project's instance of the skill, the single place that says who does what:

| Phase | Role (agent / skill / the orchestrator itself) |
|---|---|
| `framing` | <questioning skill, with the user> |
| `architecture` | <orchestrator; diagram skill; decision log if structural> |
| `plan` | <orchestrator> |
| `plan-audit` | <independent auditor agent, plan mode, top tier> |
| `build` | <one row per kind of work: code, UI, data, content — the agent that owns it, and the per-batch review> |
| `validation` | <how this project exercises the real thing: test benches, play sessions, captures, a demo> |
| `closure` | <the project's review at the Definition of Done (`closure.review`)> |

Plus the project's own constraints: the batch-size cap, the model tier for writing code, the
shared resources that never run in parallel.
