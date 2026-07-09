# Feature map — "feature" memory

> Router: **"feature → understand the subject: what it does, the code to look at, the
> architecture doc"**. When a task touches a feature listed here, **read its entry before
> searching**. Update the entry **at the same time as the code** — an entry that lies is worse
> than none.
> **DURABLE references only**: architecture/spec doc + code + decisions. **Never** a transient
> doc (backlog, in-progress spec/plan) — "planned" lives in the backlog. An entry describes what
> *exists*.
> An entry ≈ "a single subject you understand in one pass". Too long → probably two features
> (a **semantic** test, not a plain line count; `checks/feature-map-check.py` gives a *soft*
> signal — `FM-GRAN` — but doesn't decide).

This file is the **index** of the Feature channel — the same role `MEMORY.md` plays for the
Memory channel. It's an **instance** of `ENTRY-TEMPLATE.md` (the common meta-schema shared by
every channel): it doesn't redefine the frontmatter, only what's **specific** to the Feature
channel.

## The format — one file per entry + one index line

- **`features/<slug>.md`** — one entry per feature, `feature`-channel frontmatter up top (see
  `ENTRY-TEMPLATE.md §The common frontmatter` for the key details):
  ```
  ---
  id: <slug>
  created: YYYY-MM-DD
  updated: YYYY-MM-DD
  links: [D-YYYY-MM-DD-NN]        # optional — ids of related decisions, or other entries
  source: human                    # optional
  confidence: verified             # optional
  ratified: <who>, YYYY-MM-DD      # optional — required if confidence: verified
  ---
  ```
  Required for this channel: `id`, `created`, `updated`. No `status` — a Feature entry has no
  states, unlike the Decision or Backlog channel.
- **This index (`FEATURE_MAP.md`)** — one line per entry, never the detail:
  ```
  - [<slug>](features/<slug>.md) — <summary ≤ 1 line>
  ```

*(`features/` starts **empty** — the adopting project populates it over time, as a feature becomes
significant enough to deserve an entry. `checks/feature-map-check.py` checks the file↔index
concordance and the format — see its rules.)*

## An entry's body — canonical keys

The frontmatter is common to every channel; the **body**, though, stays specific to the Feature
channel — free prose organized under the following keys (French or whatever the team's working
language is, cf. `ENTRY-TEMPLATE.md §Note — English vocabulary by design`):

| Key | Meaning | Status |
|---|---|---|
| `**Role:**` | what the feature does, in 1 sentence — to understand the subject | core |
| `**Code:**` | the key files to look at, grouped by role in the project | core |
| `**Doc (durable):**` | pointer to the project's DURABLE architecture/spec doc — never transient | core |
| `**Tests:**` | the tests that cover the behavior | — |
| `**Add pattern:**` | replication recipe — mostly useful for data-driven work | optional |

**Core keys** (`checks/feature-map-check.py`, rules `FM1-*`): a `**Role:**` line, ≥ 1 file path
under `**Code:**`, and ≥ 1 durable reference — either a non-empty `**Doc (durable):**` key, or a
decision id `D-YYYY-MM-DD-NN` (in the body or in `links:`). An entry missing any one of these
three is **blocking**: it fails its job as a router.

## Full example

<!-- template -->

`features/null-check-unity.md`:

```
---
id: null-check-unity
created: 2026-07-09
updated: 2026-07-09
links: [D-2026-07-09-01]
source: human
confidence: verified
ratified: raphael, 2026-07-09
---

**Role:** Prevents Unity false-negatives — a destroyed `UnityEngine.Object` still reads as
"non-null" for `??`/`?.`, which bypass Unity's `==` override; never use `??` on a Unity type.

**Code:** `Scripts/Combat/CombatManager.cs` (turn resolution), `Scripts/Core/NullGuard.cs`
(shared `IsAlive` guard).

**Doc (durable):** `Docs/architecture/ARCHITECTURE.md §Unity null check`.

**Tests:** `Tests/EditMode/NullGuardTests.cs`.

**Add pattern:** any new component referencing an optional `UnityEngine.Object` goes through
`NullGuard.IsAlive(obj)` rather than a raw `??`/`?.` operator.
```

Matching line in `FEATURE_MAP.md`:

```
- [null-check-unity](features/null-check-unity.md) — guard against Unity null-check false negatives.
```

<!-- /template -->

## Entries

<!-- (empty) — the adopting project populates it: one line per `features/<slug>.md` entry. -->
