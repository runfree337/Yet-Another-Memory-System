# Memory entry template — how to write a new one

> **Who this is for.** This file does not provide a memory entry itself — it's the **meta-schema**
> that every entry in this framework's memory channels follows (`WORKFLOW.md §The three
> memories`), the same way `checks/TEMPLATE.md` normalizes the shape of a **check**. Writing a
> new entry without starting from this template means re-discovering by hand a choice already
> settled identically in every other channel.
>
> **Companion library:** `checks/entrylib.py` — frontmatter parser + common-schema validation,
> imported by every per-channel check (`memory-check.py`, `decisions-check.py`,
> `feature-map-check.py`, `backlog-check.py`). One single place defines what a valid memory
> entry is; this file documents what that place enforces.

## The principle

Every memory entry = **one file + one index line**, written at the same time:

- The **file** opens with a **common frontmatter** (below), followed by a **free-prose body**
  specific to the channel — the template doesn't constrain the body, only the frontmatter.
- The **index line** is uniform across channels:
  ```
  - [<id>](<path>) — <summary ≤ 1 line>
  ```
  An id, a link to the file, a summary that fits on one line — never the detail duplicated
  in the index (the detail lives in the file, the index only points to it).

## The common frontmatter

```
---
id: mem-money-uses-decimal
source: human
confidence: verified
created: 2026-07-09
updated: 2026-07-09
links: [D-2026-07-09-01]
ratified: <who>, 2026-07-09
---
```

| Key | Meaning |
|---|---|
| `id` | Stable, greppable identifier — serves as the file↔index concordance key (`checks/entrylib.py::check_index_concordance`). Never changes after creation. |
| `status` | Values are **channel-specific** (see the instantiation table below) — absent from the Memory and Feature channels, present (mandatory) for Decision and Backlog. |
| `source` | `inferred \| human \| external:<ref>` — where the entry comes from. Any `external:` source mandatorily carries a `confidence` (otherwise `R-EXT-NO-CONF`, blocking). |
| `confidence` | `verified \| unverified` — whether a human has ratified it or not. Governs promotion (see lifecycle below). |
| `created` | YYYY-MM-DD, creation date — written once, never touched again. |
| `updated` | YYYY-MM-DD, **stamped mechanically** (`checks/entrylib.py::stamp_updated`, or a per-channel check's equivalent `--stamp`) — never bumped by hand. |
| `links` | `[<ids or paths>]` — cross-channel references (e.g. a Feature entry pointing to a decision `D-YYYY-MM-DD-NN`). |
| `ratified` | `<who>, <YYYY-MM-DD>` — **required** to move to `confidence: verified` (traceability of human ratification). Missing on a `verified` entry = to-confirm, not blocking (`R-VERIFIED-NOT-RATIFIED`). |

These keys and their values are deliberately in **English** (see §Note at the bottom); the
entry's **body**, on the other hand, stays in the team's own language.

## Instantiation per channel

Each channel **details its own rules** in its README (`MEMORY.md`, `decisions/README.md`,
`FEATURE_MAP.md`, `backlog/README.md`) — the table below only locates the instance:

<!-- template -->

| Channel | Entry file | Index | Channel-specific keys | Notes |
|---|---|---|---|---|
| **Memory** | `memory/<slug>.md` | `MEMORY.md` | *(none — the common frontmatter is enough)* | No mandatory `status`. |
| **Decision** | `decisions/D-YYYY-MM-DD-NN.md` | `decisions/INDEX.md` | `status: active \| revoked \| archived`, `replaces: [ids]`, `replaced-by: <id>` | `status` mandatory; revocation/archival is a **`status` + links transition**, verifiable — more than a pure prose discipline. |
| **Feature** | `features/<slug>.md` | `FEATURE_MAP.md` | *(none — the common frontmatter is enough)* | No mandatory `status`; the body keeps its own sections (Role/Code/Doc/Tests/How to add one). |
| **Backlog** | `backlog/<id>/STATE.md` | `backlog/INDEX.md` | `status: todo \| in-progress`, `title`, `milestone`, `after: [ids]`, `docs: [paths]` | **Transient** (the *todo*), not a memory entry — but follows the **same entry format**. Tasks under the body's `## Tasks` section carry their own sub-state `todo \| in-progress \| blocked \| done`, distinct from the work item's own `status`. |

<!-- /template -->

## Confidence lifecycle

- **`unverified → verified`** requires `ratified: <who>, <YYYY-MM-DD>` in the frontmatter — the
  AI **proposes** the promotion (the frontmatter diff), the human **ratifies** it (sets
  `ratified`). Never auto-promotion: an entry that moves to `verified` without a matching
  `ratified` is flagged (`R-VERIFIED-NOT-RATIFIED`, to-confirm), not blocked — but stays an
  outstanding debt.
- **Exit** (`verified` → removal or revocation) goes through **semantic review** (tier 2,
  cf. `checks/memory-audit.md` / `checks/decisions-audit.md`) **+ a user decision**, and is
  **logged** (reference to the successor + reason + git history) — never silent.
- The substance of the rule (source, poisoning, conflict resolution between two memory entries)
  is settled once and for all in `MEMORY.md §Provenance & confidence` — this file only gives
  the frontmatter mechanics.

## Note — English vocabulary by design

The **frontmatter keys and values** are a machine API (parsed by `checks/entrylib.py`,
grepped by the checks and the agents): they are in **English from the start**, without waiting
for the framework's general translation (`PLAN.md` step 3, which covers the **prose**). The
**body prose** of an entry, on the other hand, stays in the team's own language — this template
doesn't constrain it.
