# Delivery — carrying a work item from its validated spec to closure

> **What.** The recipe the AI follows to carry a doc-backed work item through its phases
> (`backlog/README.md §Phases`), alone, once the user has validated the spec. The phases say
> **what** each gate requires; this recipe says **how** the work gets done — mostly by delegation
> — and what the orchestrator keeps for itself.
> **Agnostic** to the tool and the tech. The Claude Code packaging is
> `adapters/claude-code/skills/deliver-work-item.md`; the project fills in its **roles** (which
> agent or skill does each phase) and its own constraints (shared editors, batch size, model tiers).

## The loop

One loop, resumable after any cut — a crash, a context compaction, a new session — because
everything it needs lives in the repository:

1. **Read where it stands**: the work item's `INDEX.md` line, `STATE.md` (`phase:`, the first task
   not `done`, `## Remaining`), `questions.md` if any, and the companion docs — **the intent lives
   in the spec, never in the code**. Then `git log` on the files the work item announces: a recap
   can call "to do" what the log shows delivered, or the reverse — **a gap is a finding for the
   user, not a silent correction.** If the project runs a memory graph, list what governs the
   files about to be touched (decisions, features, recipes) and read it before cutting batches.
2. **Do the current phase** with the project's role for it.
3. **Pass its gate**: write the gate file, add it to `docs:`, tick the task, advance `phase:`,
   **commit**. A crash then loses at most the step in progress.
4. **A red gate** steps `phase:` back (`backlog/README.md §Phases`): fix and run the gate again (a code fix at closure goes back to `build`, then to validation);
   stop when the fix would touch the spec, or at the second failed validation on the same point.
5. **Waiting on the user** blocks a task, never the work item: the question goes to
   `questions.md`, the task turns `blocked`, the rest goes on.

| Phase | What the orchestrator does |
|---|---|
| `framing` | with the user, question by question, until the intent, scope and success criteria are shared; writes `spec.md` (`architecture:` / `skip:` included) and sets `validated:` **only on the user's explicit approval** |
| `architecture` | when an existing architecture changes or a feature changes the existing docs: where each piece lives, the contracts, the risks; a structural choice also goes to the decision log |
| `plan` | batches (below), their order, the proof of each, how the spec's criteria will be validated |
| `plan-audit` | an **independent** auditor — never whoever wrote the plan — confronts spec, architecture and plan with the **real code**: false premises, holes, broken order, underestimated cost. The orchestrator writes `audit-plan.md`; no blocking finding open ⟹ `verdict: pass` |
| `build` | batches, delegated or not; the proof never delegated (below); a per-batch review |
| `validation` | each success criterion of the spec exercised for real — run, played, read — with its evidence; `validation.md` |
| `closure` | the Definition of Done (`backlog/README.md`), including the overall review once the code no longer moves |

## Batches

- **A batch carries one fact**, nameable in one sentence, and the tests that prove it. A batch
  framed as a list of files drops every defect that lives in none of them; "the remaining files"
  is not a batch.
- **Small enough to be read, audited and reverted in one gesture** — the project sets the cap (a
  host project uses 5 files). It is not a context limit: past it, a batch is no longer reviewable
  by a human.
- **Check the surface on disk** before cutting: `git log --name-only` also lists files touched,
  then deleted.
- **Build tasks start with `Batch`** — or the word the project set (`backlog/README.md §Phases`).
- **Touching an approved file reopens its gate**: an edited spec steps back to `framing` (drop
  `validated:`, ask, set it again in another commit); a plan amended in `build` gets a short
  audit of the amendment only, added to `audit-plan.md` and committed with it. Progress never
  goes in `plan.md` — it lives in `STATE.md`.

## The batch prompt — frozen, copied for every batch

Pick the model **explicitly** for each delegation — judgment (design, adversarial review, unknown
cause) at the top tier, writing code at the project's chosen tier, mechanical reading and renaming
below. Left to the default, the tier is chosen for you, and you pay judgment for execution or the
reverse. Never pick it by the size of the diff.

```
You execute batch <n> of the work item `backlog/<id>/`: **<the batch's intent, one sentence>**.

## BEFORE WRITING — tool check, mandatory
<the exact command that proves you can run the tests>
If you cannot run them, STOP and say so: delivering unproven work is the worst outcome.
A shared test runner is EXCLUSIVE — never two runs at once. Build as often as needed;
targeted tests while writing; the full suite ONCE, at the end.

## Read first
- <the plan section framing THIS batch>
- <the MODEL file — one that already solved the same problem, to imitate>
- <the project rule this batch applies>

## The fact
<what the behavior does, in domain language — not class language>

## What already exists — do not touch
<the legitimate state and code, file:line, and WHY it stays>

## What is wrong — measured
<each defect with its VERIFIED file:line. Never "it seems that": a supposed defect sends
the agent to fix what is not broken>

## Scope
The files listed here, and no other.
Forbidden: opportunistic refactoring, stepping on another batch, pushing.
Commits: <either "do not commit", or "commit yourself in <n> commits, format imitated from
`git log -3`"> — never both.
<if the tree carries INTENDED uncommitted changes: one line per file — which change, why it is
intended, "no checkout/restore/stash on it">

## Report
The diff per file, the test output, and what you could NOT do.
```

## Parallelize — what isolates, what doesn't

- **Isolates**: batches with **disjoint** file scopes, one agent each, launched together so they
  truly run concurrently.
- **Doesn't**: an exclusive resource — a test runner, a single shared editor or device, a
  tool that always drives the main checkout. Two runs at once invalidate each other; a run started
  while another agent rebuilds proves nothing.
- **An isolated worktree** suits only work that needs no shared resource, and choosing it over
  the main checkout is the user's call.

## The proof is never delegated

Delegating the writing does not delegate the proof. When a batch returns, the orchestrator:

1. **Runs the suite itself.** An agent can lose its tools mid-way and deliver code that compiles
   without having run a single test — only its honesty said so, on a host project.
2. **Redoes the red counter-proof** of the one or two gates carrying the batch's invariant:
   neutralize the line, run the targeted test, check that it **fails**, restore. Copy the files
   to a **fresh** folder before mutating, file by file, and re-read `git status` after restoring —
   a reused backup folder once put seven files back to stale copies.
3. **Checks the intended changes survived** (`git status`, `git diff`) — never trusting the
   report, which can present their destruction as a service rendered.
4. **Runs the project's per-batch review** (linter, standards review if the batch deserves it).
5. **Compares the report with the frozen prompt, point by point.** A report can announce the next
   step without having done it, and an agent still running has not finished. An open point → a
   relaunch naming it; two relaunches at most, then the user — or, when the user said to proceed
   alone, `questions.md` with the task `blocked`.

For a large refactor and at closure, an **independent** auditor reviews the whole surface — never
whoever wrote the code in the same context: its value is not having watched that code being born.

**When to stop reviewing**: one round with **no behavioral defect** closes the loop. Freeze the
audited surface — if the code is rewritten between rounds, the auditor never re-sees what it
judged, and "coming back empty" becomes unreachable by construction. Weigh the review by the size
of the batch.

## Closure

The Definition of Done lives in `backlog/README.md` — follow it there, do not copy it here. The
step delegation makes frequent: at step 1, list what **explains** the files the batches changed
(a memory graph over the diff, then a grep of the contract's vocabulary) — the agent of the batch
did not read those explainers.

## The traps that cost a batch

| Trap | What happens | The counter |
|---|---|---|
| **Tier left to the default** | the agent inherits the session's model: judgment paid for execution, or the reverse | pass the model explicitly, by the nature of the work |
| **Delegated proof** | "suite green" announced by an agent that never could run the tests | demand the tool check **before** writing; rerun yourself on return |
| **"Two commits" + "do not commit"** | incompatible instructions: the agent stacks B on A in one tree, the two steps become unrecoverable | a wanted split ⟹ **the agent commits itself**, the orchestrator re-reads and amends |
| **Undeclared dirty tree** | the agent takes an uncommitted deliverable for pollution and restores it to HEAD | name each intended change in the prompt — or **commit before delegating**, the safest |
| **Push by the agent "to survive a restart"** | each push re-runs the CI of the pull request on a half-done version (measured on a host project: the user stopped it) | pushing stays forbidden to the batch; **the orchestrator pushes once**, docs included |
| **Review on a moving surface** | audit rounds never come back empty because the target moves between them | freeze the audited surface; audit the **work item's** surface, not the one just written to close it |
