# YAMS — Yet Another Memory System

A **methodological orchestrator** for working with an AI on a software project.
**Agnostic** to the tool (Claude Code, Copilot, other) and to the tech/architecture. The project
brings its architecture, its code tools, its doc and its review; YAMS brings **how to work and
remember** — it *plugs into* the project, it doesn't replace any of that.

## The idea

YAMS provides five pieces that fit together:

- a **work loop** — orient and verify before coding, develop per the project's standards,
  validate, update the durable record, capture knowledge, hand back;
- a **temporary memory** (`backlog/`) — work not yet done, distinct from any memory channel;
- a **long-term memory** in three channels — **feature** (`FEATURE_MAP.md`, where the code is),
  **decision** (`decisions/`, the why of a structural choice) and **preferences**
  (`MEMORY.md`, rules and learnings, shared vs personal);
- a **navigation** layer (`index/`) — find a file without reading everything;
- **deterministic checks** (`checks/`) that keep the whole thing consistent — orphans,
  dead pointers, inconsistent statuses — and flag issues without ever fixing them in the
  human's place.

The detail of the loop and how these pieces fit together: **[`WORKFLOW.md`](WORKFLOW.md)** —
that's the heart of the framework.

## Where to drop it, by tool (the core stays the same)

`WORKFLOW.md` is plain Markdown that an agent reads as context/instructions. Only the
**placement** changes:

| Tool | Where to hook it |
|---|---|
| **Claude Code** | `CLAUDE.md` (or a `.claude/skills/…` skill) that includes/points to `WORKFLOW.md` |
| **GitHub Copilot** | `.github/copilot-instructions.md` + `AGENTS.md` pointing to `WORKFLOW.md` | <!-- template -->
| **Other agent** | system prompt / context file that includes `WORKFLOW.md` |

**Adapting** = pointing to the **project's own** doc and tools everywhere the process says "the
project's standards", and wiring closure into the existing ritual (e.g. the review skill).

> **Adopting into a project → [`INSTALL.md`](INSTALL.md)**: the adoption path (scaffolding,
> index config, **wiring the checks wherever the user wants**, triggering the semantic audit).
> Principle: *detect + flag, the user decides when checks run*. The interactive `install.py`
> still needs to be built; `INSTALL.md` holds its spec and serves as a manual guide until then.

## Contents

- `WORKFLOW.md` — the loop + the principles (**the core**).
- `backlog/` — **work in progress** (the todo + the closure Definition of Done).
- `FEATURE_MAP.md` — "feature" memory channel (template).
- `decisions/` — "decision" memory channel (protocol + INDEX).
- `MEMORY.md` — "preferences / learnings" memory channel (shared vs personal).
- `index/INDEX.md` — navigation (template); `index/manifest.py` maintains the per-file detail
  on write (`set`/`rm`/`get`/`stamp`).
- `checks/` — the process's **deterministic checks** (backlog / decisions / index integrity…) to
  be wired into a hook or CI.
- `hooks/` — **universal guardrails** (security: secrets, poisoning, destructive commands),
  portable.
- `SCRIPTS.md` — **reference** for every script under `checks/`, `hooks/` and `index/`: intent +
  parameters + exit codes.
- `knowledge-capture.md` — agnostic routing for a method-level learning (the "is it worth
  tooling?" gate + function → per-tool mechanism).

## Amend it

This is a **seed**. The project and the user adjust it: placement, conventions, delegation
roles, wiring into the existing review/closure ritual. The process is meant to be
**modified**, not endured as-is.
