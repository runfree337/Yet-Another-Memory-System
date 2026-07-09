# `STATE.md` template — copy as-is into `backlog/<id>/STATE.md`

> Concrete instance of `ENTRY-TEMPLATE.md` for the **Backlog** channel (see its
> §Instantiation per channel table). The frontmatter is the **source of truth for state**; the
> body never carries durable content — only state (tasks) and references (see
> `README.md §STATE.md never carries durable content`).

## Frontmatter

<!-- template -->
```
---
id: <work-item-id>
title: <Readable work item title>
status: todo
milestone: null
after: []
docs: []
impacts: []
updated: 2026-07-09
---
```
<!-- /template -->

`id` = folder name (kebab-case). `status` = `todo | in-progress` (never `done` — a finished work
item is **removed**, not marked). `milestone` = integer (milestone) or `null` (Unplanned).
`after` = list of work-item `id`s this one depends on. `docs` = list of the folder's companion
`.md` files (excluding `STATE.md` itself). `impacts` = the **impact ledger**: fill it in **as you
learn**, during work, as soon as you know a durable doc/memory will need updating — each entry is
either a target path (e.g. `WORKFLOW.md`, `features/x.md` — no existence requirement, it may be a
doc to create at closure) or a channel keyword (`decision | feature | memory`). Consumed at
closure — DoD step 1 (`README.md`) enumerates it instead of relying on recall. `updated` =
mechanically stamped by `backlog-check.py --stamp`, never by hand.

## Tasks

<!-- template -->
- [done] Frame the work item's intent and write the initial spec.
- [in-progress] Break the resolution engine down into testable bricks → plan-resolution.md
- [todo] Write integration tests once the breakdown is stable.
<!-- /template -->

One line = one task. The `<!-- template -->` marker above only exempts the **example paths** in
this template — it's not a format to copy into a real `STATE.md`'s comments. Two forms:
- `- [<state>] <label ≤ 30 words>` — the task fits in its label.
- `- [<state>] <short label> → <working-doc.md>` — the detail lives in the working doc (inside
  the work item's folder), the label stays short.

States: `todo | in-progress | blocked | done`.

## Remaining

<!-- template -->
As long as a work item isn't yet broken into tasks, describe here in free prose what's left to
do. This section **empties out** into `## Tasks` as the breakdown progresses — it's not a
permanent log, just the holding area before breakdown.
<!-- /template -->
