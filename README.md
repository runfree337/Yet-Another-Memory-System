# YAMS — Yet Another Memory System

A **methodological orchestrator** for working with an AI on a software project.
**Agnostic** to the tool (Claude Code, Copilot, other) and to the tech/architecture. The project
brings its architecture, its code tools, its doc and its review; YAMS brings **how to work and
remember** — it *plugs into* the project, it doesn't replace any of that.

This framework was mostly developped with the help of Claude AI

## The idea

YAMS provides five pieces that fit together:

- a **work loop** — orient and verify before coding, develop per the project's standards,
  validate, update the durable record, capture knowledge, hand back;
- a **temporary memory** (`backlog/`) — work not yet done, broken into short tasks with their
  own states, distinct from any memory channel; steering rests on three legs: the **plan**
  (milestones in `backlog/INDEX.md`), the **state** (`DASHBOARD.md`, where things stand so you
  can resume) and the **todo** (the backlog itself);
- a **long-term memory** in three channels — **feature** (where the code is and how to
  replicate it), **decision** (the why of a structural choice) and **preferences** (rules and
  learnings, shared vs personal). Every entry, whatever the channel, follows **one common
  model** ([`ENTRY-TEMPLATE.md`](ENTRY-TEMPLATE.md)): one file + one index line, with
  provenance, confidence and a traced ratification in its front matter — so nothing unverified
  ever silently becomes "team truth";
- a **navigation** layer (`index/`) — find a file without reading everything;
- **deterministic checks** (`checks/`) that keep the whole thing consistent — orphans,
  dead pointers, inconsistent statuses, dead cross-links, stale entries — and flag issues
  without ever fixing them in the human's place.

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
- `ENTRY-TEMPLATE.md` — the **common memory-entry model** every channel instantiates
  (front matter, index line, confidence lifecycle).
- `backlog/` — **work in progress**: protocol + INDEX, one `STATE.md` per work item
  (`STATE.template.md`), the closure Definition of Done.
- `DASHBOARD.md` — the **current state**, one page (the "state" leg of plan / state / todo).
- `FEATURE_MAP.md` + `features/` — "feature" channel: index + one file per entry.
- `decisions/` — "decision" channel: protocol + INDEX + one file per decision.
- `MEMORY.md` + `memory/` — "preferences / learnings" channel: index + one file per entry
  (shared vs personal).
- `index/INDEX.md` — navigation (template); `index/manifest.py` maintains the per-file detail
  on write (`set`/`rm`/`get`/`stamp`).
- `checks/` — the process's **deterministic checks** (channel integrity, cross-links, dead doc
  references — paths, decision ids, code symbols…) to be wired into a hook or CI;
  `checks/entrylib.py` is the single shared validator behind them. `checks/index-eval/` goes one
  step further: it measures whether the index's intent phrases actually earn their keep over
  bare file names (lexical prefilter + LLM-judged recipe).
- `hooks/` — **universal guardrails** (security: secrets, poisoning, destructive commands),
  portable.
- `adapters/claude-code/` — ready-to-wire **Claude Code adapter**: hook scripts + skill
  templates materializing the wiring tables — including the **index-usage metrics** pair
  (does the navigation index actually get consulted?).
- `capture-policy.example.json` — the **capture policy** template: who may write knowledge to
  each memory channel and in what state (`off`/`propose`/`draft` + confirmation-gated normative
  paths), enforced by a check and a write-time guard (`knowledge-capture.md §Capture policy`).
- `SCRIPTS.md` — **reference** for every script under `checks/`, `hooks/` and `index/`: intent +
  parameters + exit codes.
- `knowledge-capture.md` — agnostic routing for a method-level learning (the "is it worth
  tooling?" gate + function → per-tool mechanism).

## Amend it

This is a **seed**. The project and the user adjust it: placement, conventions, delegation
roles, wiring into the existing review/closure ritual. The process is meant to be
**modified**, not endured as-is.
