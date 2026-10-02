# Backlog — protocol + closure (DoD)

`backlog/` = the **single home for open work** (the *todo*: design, in-progress tasks, what's
left). Distinct from the **durable** (the project's doc + the three memory channels) and the
*why* (`decisions/`). **Transient**, not a memory — but every `STATE.md` follows the **same entry
format** as the memory channels: it's an instance of the common `ENTRY-TEMPLATE.md` template
(**Backlog** channel, §Instantiation per channel table).

## The chain

`spec` (framing a work item) → **`backlog`** (decided, not yet built) → *in progress: broken into
tasks* → on delivery, the content **migrates to the durable** and the work item **leaves** the
backlog. A doc-backed work item makes the chain explicit and checkable through its **phases**
(§Phases below): each gate it passes leaves a file that proves it.

## Structure

**Two tiers**:
- Small item → an **inline** line in `INDEX.md` (status carried by a badge on the line,
  `[todo]` / `[in-progress]`).
- **Doc-backed** work item → a `backlog/<id>/` folder whose `STATE.md` opens with a **frontmatter**
  using **English** keys (`id / title / status / milestone / after / docs / updated`, the
  **source of truth for state**), followed by a **mandatory** `## Tasks` section (see below); its
  companion docs (spec, manifest, task working docs) live in the same folder.
- Key semantics (unchanged, only the vocabulary changes): `after` = dependency (formerly
  `apres`); `docs` = the folder's companion docs; `updated` = last-touched date (formerly `maj`),
  **mechanically stamped** at pre-commit; `milestone` = milestone (formerly `jalon`), an integer or
  `null` (Unplanned); `impacts` = the **impact ledger** (see below).
- `phase` = where a doc-backed work item stands in its delivery (§Phases); `status` only says
  whether work has started. A work item in `framing` may be `todo`; past it, `in-progress`.
- `status: todo | in-progress` (in the frontmatter for a doc-backed item, the badge for an inline
  one). Done → **removed** (no accumulating "done" status — a work item never turns
  `status: done`, it leaves the backlog). The `INDEX.md` line for a doc-backed item carries only
  title + target + gist (status lives in the frontmatter). Bounded mechanically: an entry
  (bullet + wrapped lines, `[…]` tokens excluded) over `sizes.backlog-index-entry-max-words`
  words (default 60) is flagged `I-ENTRY-LEN` (to-confirm) — detail and history live in the work
  item's folder and `git log`, never in the index.
- **Opening** a doc-backed work item = `mkdir <id>/` + a `STATE.md` copied from
  `STATE.template.md` (frontmatter with `phase: framing` + `## Tasks` + `## Remaining`) + a
  `spec.md` carrying only the **intent**, written at once + its line in `INDEX.md` (no badge).
  The only task is framing it (`- [todo] Frame the work item with the user → spec.md`), and the
  AI **asks the user whether to frame it now**. An inline item has no phase; one that needs a
  doc becomes a doc-backed work item.
- `updated`: **auto-stamped at pre-commit** — the stamp home `hooks/stamp-staged.sh` (the ONE
  script that runs `backlog-check.py --stamp --staged` and its two channel siblings) sets
  `updated = commit date` on staged STATE.md files, **mechanically** (no manual bump, no
  staleness — via `entrylib.stamp_updated`). Two callers, one home: the **git-native hook**
  `adapters/git/pre-commit` (covers every `git commit`, whoever runs it — install:
  `git config core.hooksPath adapters/git`, surfaced at session start when missing) and the
  Claude Code `PreToolUse` adapter (catch-up net for machines without the git hook). **Exact
  scope and known holes live here, once** — scripts point at this statement instead of
  recopying it: a commit replaying someone else's work (merge/cherry-pick/revert/rebase, any
  sister head) is NOT stamped, keeping the original date; a **partial commit** (`git commit --
  <path>`, `-p`, temporary index) is not stamped and says so; `git merge --squash` leaves no
  signal and stamps like an ordinary commit (accepted hole); `--no-verify` bypasses the hook.
  A drifted date is **never rewritten to today** (that would fake freshness) — it self-heals
  at the next pass made where the hook runs, and the drift is visible meanwhile via
  `E-STATE-FRESH` (a check survives an uninstalled/bypassed/absent hook).

## The `## Tasks` section — the canonical line format

Every `STATE.md` carries a **mandatory** `## Tasks` section: per-task tracking lives **there**,
never duplicated in the frontmatter or in `INDEX.md`. One line, one task, two forms:

```
- [<state>] <label ≤ 30 words>
- [<state>] <short label> → <working-doc.md>
```

- **States** (task sub-state, distinct from the work item's `status`): `todo | in-progress |
  blocked | done`.
- **A simple task fits in its label** (≤ 30 words). Beyond that, it **must** reference a
  **working doc** — a file **inside the work item's folder**, cited after `→` — and the label
  goes back to being short (the detail lives in the doc, not in the line).
- **Work item ⟺ tasks consistency** (a signal, not a hard verdict — tier 2 decides):
  - work item `in-progress` ⟹ at least one task started (state ≠ `todo`);
  - all tasks `done` ⟹ work item ready to close (run the DoD below).
- An optional `## Remaining` section carries, in free prose, what's **not yet** broken into
  tasks — it empties out into `## Tasks` as the breakdown progresses. No other section is
  canonical: `## Tasks` and `## Remaining` are the only two expected in a `STATE.md` (beyond the
  frontmatter).

## STATE.md never carries durable content

Capitalizing the durable (architecture doc, `FEATURE_MAP` entry, decision…) happens **at the end
of each task that produces it**, not at the end of the work item — that's when it's freshest.
Direct consequence: **`STATE.md` never carries durable content**, only **state** (frontmatter +
tasks) and **references** — to the work item's working docs, and to durable content already
written elsewhere. A finished task that produced doc → that doc goes **immediately** to its
durable home (never left "pending" in STATE.md), the task turns `[done]` with, if useful, a
reference to that home. A `STATE.md` that bloats (content > state + references) is the signal
that this rule was bypassed — see `checks/backlog-check.py §E-STATE-SIZE / §E-STATE-SECTION`
(soft, to-confirm).

## Phases — a work item proves each gate it passes

**Intent: once the user and the AI have framed a work item together, the AI can carry it alone to
closure, and resume it at any step** — everything it needs to resume lives in the repository, not
in a conversation that gets compacted. The user steps in at framing, then at the end (an issue, or
a corrective work item, if the result doesn't suit).

`phase:` in the frontmatter of `STATE.md`, in this order:

`framing` → `architecture` → `plan` → `plan-audit` → `build` → `validation` → `closure`

**Gates are cumulative**: a phase requires the proof of every gate it is past.
`checks/backlog-check.py` enforces them (`E-GATE`, blocking).

| To be in… | the work item needs |
|---|---|
| `architecture` and later | `spec.md` (declared in `docs:`) whose frontmatter carries `validated: <date>` — set **only on the user's explicit approval** |
| `plan` and later | the architecture doc **named by the spec** (`architecture:` in its frontmatter): a companion of the folder (no `/`), or a durable doc it modified (a path from the repository root) |
| `plan-audit` and later | `plan.md` (declared in `docs:`) |
| `build` and later | `audit-plan.md` (declared in `docs:`) whose frontmatter says `verdict: pass` — an **independent** audit of spec + architecture + plan against the real code, never by whoever wrote the plan |
| `validation` and later | every build task `done` — with no build task at all, this gate is empty and passes: name the build in tasks |
| `closure` | `validation.md` (declared in `docs:`) whose frontmatter says `verdict: pass` — for **each success criterion of the spec**: what was exercised, the evidence (capture, log, measure), the verdict; plus a last line, "left for the human to judge" |

A companion missing from `docs:` reads as absent. `validated:` and `verdict: pass|fail` live in the
file's **YAML frontmatter** (between `---`), never in its body: a "PASS" copied at the top of a
report does not open the gate.

- **Only `architecture` and `plan-audit` may be skipped** — `skip: [architecture]` in the spec's
  frontmatter, the reason in its prose (`E-SKIP` otherwise). Framing, plan and validation never
  skip: a validation can be short (re-read a doc against the spec), it is not skipped. The
  architecture step is due when the work item modifies an existing architecture, or adds a
  feature that changes the existing docs.
- **`architecture:` and `skip:` are written before the user validates the spec** — adding them
  afterwards would be editing a validated spec.
- **Build tasks start with the word `Batch`** (`backlog.build-task-prefix` — a project may set its
  own word): it is how the check sees a build task done before the plan audit passed
  (`E-PHASE-ORDER`, blocking) or in progress before `build` (`E-PHASE-LATE`). A written rule of
  the protocol, not a convention — the check sees the label, not the code. Markdown emphasis
  around the word is fine; a plural (`Batches 1-2`) is not a build task (`E-BUILD-PREFIX`): one
  task, one batch.
- **A file created along the way** (a gate file, `questions.md`) enters `docs:` **in the same
  commit** — otherwise `E-DOCS`.
- **Each gate passed is committed**: gate file written, task ticked, `phase:` advanced, commit. A
  crash loses at most the step in progress.
- **A red gate** (blocking audit, failed validation, a code fix asked by the closure review): step
  `phase:` back, the task says why, fix, run the gate again. A code fix at closure is a build task:
  the phase goes back to `build`, then the validation is replayed on the criterion it touches. If the fix would touch the **spec** — the intent the user validated — remove
  `validated:` and set `phase: framing` **in the same commit**, then stop and ask. Stop as well at
  the second failed validation on the same point.
- **A task waiting on the user** (an open question, a text only the user may approve) turns
  `blocked`, the question goes to `questions.md` in the folder, and the rest goes on. A work item
  whose content is the user's to approve cannot reach `closure` without them — by design.
- **A gate reopened is seen by commit, not by date.** `backlog-check` finds the commit that set
  the gate and asks git whether anything touched the approved file after it — a same-day edit is
  seen:
  - **the spec** (`E-SPEC-DRIFT`, blocking): a commit touches `spec.md` after the one that set its
    `validated:` line — `skip:` included, it lives in the spec. Re-validating keeps the same line,
    so the gesture is the red gate's: drop `validated:` (stepping back, one commit), then set it
    again on the user's approval (another commit);
  - **the plan** (`E-PLAN-DRIFT`, blocking, from `build` on): a commit touches `plan.md` after the
    last commit of `audit-plan.md` — the audit approved another plan. Before `build`, revising
    the plan is the prescribed step back;
  - **the validation** (`E-VALIDATION-STALE`, to-confirm, in `closure`): a batch done after the
    last commit of `validation.md` — replay the validation on what it touches.
- **A plan amended during `build`** — it happens: development teaches what the plan could not
  know. `plan.md` never carries progress (that is `STATE.md`'s job), so touching it means
  changing what will be built. The gesture: write the amendment in the plan, have it audited
  **short** — the same independent auditor, bounded to the amendment, against the code the done
  batches already delivered —, add that audit as a section of `audit-plan.md`, and commit the
  amendment and its audit **together**: that commit becomes the gate. A short audit that FAILs
  flips the single `verdict:` of `audit-plan.md` to `fail` (`E-GATE` then holds the phase) and the
  phase steps back to `plan`.
- `status: todo` past `framing` (`E-STATUS-PHASE`) and an `architecture:` path that leaves the
  repository (`E-ARCH-PATH`, absolute or `..`) block.
- **Resuming a work item that predates phases** (migrated to `framing`): name its existing
  architecture doc in `architecture:`, have the user validate the spec so completed, audit the plan
  if it never was, and prefix its remaining code tasks with the build word (`Batch`).
- `backlog.require-phase: true` (the project's `checks-config.json`) makes a missing `phase:`
  blocking once every work item has one; the default only warns, so updating the standard never
  breaks an adopting project.

How to carry a work item through these phases — batches, delegation, the proof the orchestrator
never delegates — is the **delivery recipe**, `DELIVERY.md`.

## The impact ledger — `impacts:`

The `impacts:` frontmatter key is a **checklist, not a summary**: fill it in **during work**, as
soon as you learn a durable doc/memory will need updating — not reconstructed from memory at
closure. Two kinds of entry:
- a **target path** (e.g. `WORKFLOW.md`, `features/x.md`) — no existence requirement, it may name <!-- template -->
  a doc that will only be **created** at closure;
- a **channel keyword** — `decision | feature | memory` — when the impact is "log a decision" or
  "touch that channel" rather than a specific file.

`checks/backlog-check.py` enforces the closed vocabulary (`E-IMPACT`, blocking) and nudges when a
work item looks ready to close with an empty ledger (`E-IMPACT-EMPTY`, to-confirm — never fires
while tasks remain open). `--checklist <id>` reads the ledger back: its **Durable** step (DoD 1
below) enumerates the declared impacts instead of the generic wording, so closure stops relying on
recall.

## Milestones — ordered grouping

`INDEX.md` **groups** work items by **milestone**: a subheading `### Milestone N — <name>` (N
integer = the order — the `<name>` stays in the team's own working language, the human face of
the plan), unassigned work items under `### Unplanned`. The milestone **orders**, it
doesn't partition (always a single `INDEX.md` — the "milestone's backlog" is the *view* = its
group). The `milestone:` frontmatter key carries the **machine copy**, reconciled by the check.
Reclassifying a work item = move its line from one group to another **and** update `milestone:`
in its frontmatter.

## Definition of Done — closing a work item (in order)

1. **Durable check** — since capitalization already happened task by task (see above), this step
   is no longer heavy lifting but a **verification**: is there any durable content left
   unmigrated (in `STATE.md`, a forgotten working doc…)? If so, migrate it now to its durable home
   + the memory channels it touches (`FEATURE_MAP`…) — the durable *carries the content*, not a
   promise. Run `backlog-check.py --checklist <id>`: it enumerates the work item's `impacts:`
   ledger (see above) as a **nominative checklist** for this step, instead of relying on recall.
   **If the work item changed a contract** — a default flipped, a guard moved, an API replaced, a
   symbol removed — also ask **what still EXPLAINS the old one**, not what calls it: the compiler
   and the tests find the callers, nothing finds the explainers. `grep` the contract's
   **vocabulary**, not only the symbol (an explainer often describes a behavior without naming a
   line of code), in this order of measured frequency: the summary comment above the code itself,
   the tests and their assertion messages, the work item's own tracking (written *during* the
   change, outdated *by* it), feature entries and durable docs, then the recipes agents follow
   (`knowledge-capture.md §3`). A stale explainer breaks nothing — it **teaches the old contract**
   to the next reader, often an agent that applies it to the letter. *Measured on a host project:
   a skill kept teaching a call to a class deleted three months earlier; the deleting commit had
   swept the callers and none of the explainers.*
2. **Decision** recorded if the closure settles a structural choice.
3. **Review** — the standard's own tier-1 checks first (`checks/memory-audit.py --tier1`, then
   `checks/coverage-check.py <work-item-dir>` if any of its documents dispatches an enumerated
   list into a table — **a plan of work is not the inventory of what it claims to cover**, and
   this step is exactly where a closure gets signed on the table's authority); they
   are agnostic and always available, so this half never depends on the project. Then the
   **project's review of the delivered surface** — its content belongs to the project, not to the
   framework: a review skill, an auditing agent, a second pair of eyes, a cross-read. **Ask before
   assuming.** Unless the user already settled it in the session, or a standing answer sits under
   `closure.review` in `checks-config.json` (a non-empty string = do it, and this is what
   reviewing means here; `false` = the project waived it, and the step still prints, marked as
   waived, so the choice stays visible). No key, no session answer → the question gets asked. The
   framework **requires** the review; it neither prescribes its nature nor assumes the answer
   (`INSTALL.md §Guiding principle`).
4. **Backlog cleared** — the work item + its `INDEX.md` line are **removed** (or status updated if
   partial).
5. **State updated** — `DASHBOARD.md`: progress of the relevant milestone, hot spots (resolved
   ones removed / new ones added), the date. **Not a log**: the work item's story does not go
   there — it lives in `git log` and `decisions/`.
6. **Knowledge capture** — ask "reusable method learned here?" and route it if so.

> Until these steps are done, the work item **is not closed**. Step 3 is where the project's own
> ritual plugs in (its review skill, its merge, its auditing agent) — the process requires the
> step, never its content, and there is **no mechanical check that the review happened**:
> unverifiable without false positives, so out of tier 1 by construction (`checks/TEMPLATE.md`).
> It's a box to tick, like the five others.
