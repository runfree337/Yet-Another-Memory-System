# YAMS — Yet Another Memory System

**A working method, and the memory that goes with it, for building a software project with an AI
agent over hundreds of sessions.**

An AI agent starts every session from zero. On a long project, that shows: it searches again for
where a feature lives, re-argues a decision settled a month ago, follows a recipe in the docs that
the code has outgrown, and — given enough sessions — writes its own guesses down as if they were
facts. YAMS is a set of habits and files that keeps this from happening, plus checks that tell you
when it starts happening anyway.

It **plugs into** your project and replaces nothing. The project keeps its architecture, its
linters, its tests and its review; YAMS brings **how to work and how to remember**. It is agnostic
to the agent (Claude Code, Copilot, others) and to the stack.

## Where it comes from

YAMS was extracted from a real solo project, worked on with an AI agent over several months. What
is here is what held up there — most rules name the failure that motivated them, and most checks
were written after the drift they catch had actually happened.

The framework itself was mostly written with Claude — you will spot its em-dashes everywhere ;)

## What you get

- **A work loop** — orient and verify before coding, develop to the project's standards,
  validate, update the durable record, capture what was learned, hand back. Detailed in
  **[`WORKFLOW.md`](WORKFLOW.md)**, the heart of the framework.
- **A short-term memory** (`backlog/`) — the work not done yet, cut into tasks with their own
  states and, for larger items, phases gated by a validated spec and an audited plan. Steering
  rests on three legs: the **plan** (milestones), the **state** (`DASHBOARD.md`, enough to resume
  cold) and the **todo** (the backlog itself).
- **A long-term memory in three channels** — **feature** (where the code is and how to extend
  it), **decision** (the why of a structural choice) and **preferences** (rules and learnings).
  Every entry follows **one common model** ([`ENTRY-TEMPLATE.md`](ENTRY-TEMPLATE.md)): one file,
  one index line, and front matter recording its source, its confidence and who ratified it.
- **Navigation** (`index/`) — find a file without reading the repo.
- **Deterministic checks** (`checks/`) — orphan entries, dead links and paths, inconsistent
  statuses, stale numbers in the docs, a plan table that silently drops an item.
- **A delivery recipe** ([`DELIVERY.md`](DELIVERY.md)) — how the agent carries a work item alone
  once its spec is validated: batches, a frozen batch prompt, and the proof it never delegates.

## What sets it apart

- **It reports; it never fixes in your place.** The checks are designed for zero false positives,
  stay silent when everything is clean, and speak through exit codes — so they fit a session hook,
  a pre-commit or a CI job. Questions that need judgment ("does this doc still describe the
  code?") go to a semantic audit whose findings a human ratifies.
- **Nothing unverified silently becomes team truth.** An entry written by the agent stays
  `unverified` until a human promotes it, and the checks keep the ratification inbox visible.
- **Start small, grow on a signal.** The `core` profile is the loop, a dashboard, an inline
  backlog, the decision channel, three checks and the security guards. Every other layer comes
  with the signal that justifies it, and every check exits cleanly on a channel you haven't
  adopted — a partial install is a supported state.
- **No dependencies.** Plain Markdown and Python standard library. Copy the folders; there is
  nothing to install.
- **Guards in the write path** — secrets, invisible or bidirectional characters (prompt
  injection), destructive shell commands, and writes to the agent's own instruction files.

## Getting started

1. Copy the framework folders to the root of your repo — whole, not cherry-picked
   ([`INSTALL.md` step 2](INSTALL.md#steps-manual-today--what-the-installer-will-do-tomorrow)).
2. Point your agent's context file at `WORKFLOW.md`:

   | Tool | Where to hook it |
   |---|---|
   | **Claude Code** | `CLAUDE.md` (or a `.claude/skills/…` skill) that includes/points to `WORKFLOW.md` |
   | **GitHub Copilot** | `.github/copilot-instructions.md` + `AGENTS.md` pointing to `WORKFLOW.md` | <!-- template -->
   | **Other agent** | system prompt / context file that includes `WORKFLOW.md` |

3. Wire the `core` checks wherever you want them to run — session start, end of turn,
   pre-commit, CI, or by hand. For Claude Code, ready-made hooks and skills live in
   [`adapters/claude-code/`](adapters/claude-code/README.md); for git, in `adapters/git/`.
4. Run the checks once and confirm they're green.

Then **adapt**: everywhere the process says "the project's standards", point to your own docs and
tools, and hook closure into your existing review ritual.

The full adoption path — profiles, configuration, wiring choices, migrating an existing corpus,
seeding the feature channel on a mature codebase — is in **[`INSTALL.md`](INSTALL.md)**.

## Current limits

- The interactive `install.py` is **not built yet**: adoption is manual, guided by `INSTALL.md`,
  which also holds the installer's spec.
- Ready-made glue exists for **Claude Code** and **git** only. Other agents get the method and the
  scripts, and wire them by hand.
- It has been run in depth on **one** host project. Expect to amend it to yours.

## Contents

- `WORKFLOW.md` — the loop + the principles (**the core**).
- `ENTRY-TEMPLATE.md` — the **common memory-entry model** every channel instantiates
  (front matter, index line, confidence lifecycle).
- `backlog/` — **work in progress**: protocol + INDEX, one `STATE.md` per work item
  (`STATE.template.md`), its **phases and gates**, the closure Definition of Done.
- `DELIVERY.md` — how the AI **carries a work item alone** once its spec is validated: the loop
  over the phases, batches, the frozen batch prompt, the proof it never delegates.
- `DASHBOARD.md` — the **current state**, one page (the "state" leg of plan / state / todo).
- `FEATURE_MAP.md` + `features/` — "feature" channel: index + one file per entry.
- `decisions/` — "decision" channel: protocol + INDEX + one file per decision.
- `MEMORY.md` + `memory/` — "preferences / learnings" channel: index + one file per entry
  (shared vs personal).
- `index/INDEX.md` — navigation (template); `index/manifest.py` maintains the per-file detail
  on write (`set`/`rm`/`get`/`stamp`).
- `checks/` — the process's **deterministic checks** (channel integrity, cross-links, dead doc
  references — paths, decision ids, code symbols —, recounted coverage tables, re-measured numbers)
  to be wired into a hook or CI; `checks/entrylib.py` is the single shared validator behind them.
  `checks/index-eval/` goes one step further: it measures whether the index's intent phrases
  actually earn their keep over bare file names (lexical prefilter + LLM-judged recipe).
- `hooks/` — **portable guardrails + router aids**: the security guards (secrets, poisoning,
  destructive commands, normative writes) plus the never-blocking **nudges** that add context
  beside a tool's result — `index-nudge.py` (points at the navigation index on a broad search) and
  `memory-graph.py` (the derived graph over the memory channels: which memory covers a file
  about to be edited, which decisions/features match a search).
- `adapters/claude-code/` — ready-to-wire **Claude Code adapter**: hook scripts + skill
  templates materializing the wiring tables — including the **index-usage metrics** pair
  (does the navigation index actually get consulted?). `adapters/git/` — the git-native
  pre-commit hook.
- `capture-policy.example.json` — the **capture policy** template: who may write knowledge to
  each memory channel and in what state (`off`/`propose`/`draft` + confirmation-gated normative
  paths), enforced by a check and a write-time guard (`knowledge-capture.md §Capture policy`).
- `checks-config.example.json` — the **global settings** template: audit-recommendation
  thresholds, size/granularity signals, extension-only guard lists — one optional file every
  check and guard reads (absent = the built-in defaults; `SCRIPTS.md §The global settings file`).
- `SCRIPTS.md` — **reference** for every script under `checks/`, `hooks/` and `index/`: intent +
  parameters + exit codes.
- `knowledge-capture.md` — agnostic routing for a method-level learning (the "is it worth
  tooling?" gate + function → per-tool mechanism).
- `ROADMAP.md` — the framework's **own improvement tracks** (objectives, not plans) — distinct
  from `backlog/`, which is a template for host projects.
- `run-tests.py` — the framework's own test suites, one entry point.

## Amend it

This is a **seed**. The project and its people adjust it: placement, conventions, delegation
roles, wiring into the existing review and closure rituals. The process is meant to be
**modified**, not endured as-is.
