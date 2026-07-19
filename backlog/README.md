# Backlog — protocol + closure (DoD)

`backlog/` = the **single home for open work** (the *todo*: design, in-progress tasks, what's
left). Distinct from the **durable** (the project's doc + the three memory channels) and the
*why* (`decisions/`). **Transient**, not a memory — but every `STATE.md` follows the **same entry
format** as the memory channels: it's an instance of the common `ENTRY-TEMPLATE.md` template
(**Backlog** channel, §Instantiation per channel table).

## The chain

`spec` (framing a work item) → **`backlog`** (decided, not yet built) → *in progress: broken into
tasks* → on delivery, the content **migrates to the durable** and the work item **leaves** the
backlog.

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
- `status: todo | in-progress` (in the frontmatter for a doc-backed item, the badge for an inline
  one). Done → **removed** (no accumulating "done" status — a work item never turns
  `status: done`, it leaves the backlog). The `INDEX.md` line for a doc-backed item carries only
  title + target + gist (status lives in the frontmatter).
- **Opening** a doc-backed work item = `mkdir <id>/` + a `STATE.md` copied from
  `STATE.template.md` (frontmatter + `## Tasks` + `## Remaining`) + its line in `INDEX.md`
  (no badge).
- `updated`: **auto-stamped at pre-commit** — a hook (`backlog-check.py --stamp --staged`, wired to
  **pre-commit**: a git `pre-commit` hook or your tool's equivalent) sets `updated = commit date`
  on indexed STATE.md files, **mechanically** (no manual bump, no staleness — via
  `entrylib.stamp_updated`).

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
2. **Decision** recorded if the closure settles a structural choice.
3. **Review** — the standard's own tier-1 checks first (`checks/memory-audit.py --tier1`); they
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
   ones removed / new ones added), date line.
6. **Knowledge capture** — ask "reusable method learned here?" and route it if so.

> Until these steps are done, the work item **is not closed**. Step 3 is where the project's own
> ritual plugs in (its review skill, its merge, its auditing agent) — the process requires the
> step, never its content, and there is **no mechanical check that the review happened**:
> unverifiable without false positives, so out of tier 1 by construction (`checks/TEMPLATE.md`).
> It's a box to tick, like the five others.
