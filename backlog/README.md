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
  `null` (Unplanned).
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
   promise.
2. **Decision** recorded if the closure settles a structural choice.
3. **Backlog cleared** — the work item + its `INDEX.md` line are **removed** (or status updated if
   partial).
4. **State updated** — `DASHBOARD.md`: progress of the relevant milestone, hot spots (resolved
   ones removed / new ones added), date line.
5. **Knowledge capture** — ask "reusable method learned here?" and route it if so.

> Until these steps are done, the work item **is not closed**. The validation step plugs into the
> project's own ritual (its review skill, etc.) — the process doesn't impose one.
