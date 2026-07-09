# "Decision" memory — protocol

The *why* behind **structural** choices: an organizational pivot, an abandoned path, a tool
choice, a settled scope, a cross-cutting convention.

This channel is an **instance** of `../ENTRY-TEMPLATE.md` (the common meta-schema shared by every
memory entry — one file + one index line, common frontmatter). What follows only redefines what's
**specific to the Decision channel**; the common keys (`id`, `source`, `confidence`, `created`,
`updated`, `links`, `ratified`) and their lifecycle live in `ENTRY-TEMPLATE.md`.

1. **One file per decision**: `D-YYYY-MM-DD-NN.md` + **its line in `INDEX.md`**, written **at the
   same time**.
2. **`INDEX.md` is read first** (1 line per decision). The detail only opens up when the *why* is
   needed.
3. **Format of a `D-*.md`** — a frontmatter above three free-prose sections:

   ```
   ---
   id: D-2026-07-09-01
   status: active
   source: human
   confidence: verified
   created: 2026-07-09
   updated: 2026-07-09
   replaces: []
   replaced-by: null
   links: []
   ratified: raphael, 2026-07-09
   ---

   **Decision**: what was settled.

   **Why**: the reason + the alternatives ruled out.

   **Invariant**: the rule that survives (verifiable).
   ```

   **Common** keys (`ENTRY-TEMPLATE.md`): `id`, `source`, `confidence`, `created`, `updated`,
   `links`, `ratified`. Keys **specific to this channel**:

   | Key | Meaning |
   |---|---|
   | `status` | `active \| revoked \| archived` — **mandatory** for this channel. |
   | `replaces` | `[<ids>]` — decisions this one replaces (reciprocal of `replaced-by`). |
   | `replaced-by` | `<id>` — decision that replaces this one, once revoked. |

   The **body** keeps its three canonical sections, each opened by a bold bullet — **Decision** /
   **Why** / **Invariant** — mechanically checked by `checks/decisions-check.py` (rule `D4`).
   This is the canonical form retained (as opposed to `##` headings): it matches what this
   protocol already documented before the frontmatter existed, so no migration of existing bodies
   is needed.
4. **Revocation**: a decision that contradicts another moves to `status: revoked` and points
   `replaced-by: <successor-id>`; the successor carries the reciprocal `replaces:
   [<revoked-id>, …]`. This is now a **`status` + link transition, mechanically verifiable**
   (`checks/decisions-check.py`, rule `D6`: the `replaced-by` target exists, the `replaces`
   reciprocity holds, no cycle) — no longer a pure prose discipline. The substance doesn't change:
   if the old decision **was implemented**, it stays a **tombstone** — file kept
   (`status: revoked`), line kept in `INDEX.md` ("don't reintroduce X" stays alive). If it was
   **never implemented**, it's **deleted** (file + INDEX line) and the successor absorbs the
   rejected alternative — no tombstone for something never built. When in doubt, keep it.
5. **Archiving**: a stale decision moves to `status: archived` **and** its line migrates under
   `## Archived` in `INDEX.md` — both **at once**. This is now a **`status` + index-section
   transition, mechanically verifiable** (`checks/decisions-check.py`, rule `D5`: an `archived`
   entry referenced under `## Active`, or an `active` one referenced under `## Archived`, is
   blocking). The line leaves the active index as soon as a **living authority holds its ground**
   — an already-indexed successor (`replaced-by` resolved, cf. `D6`), a guard test, the
   architecture doc; it **stays** under Active only if the `revoked` decision is the **sole
   guardian** of a living constraint (no other home for "don't reintroduce X"). This way the
   index **shrinks** instead of growing forever (an *append-only* index eventually becomes
   unreadable); the **permanent record** stays the archived files + git. **To check that an
   already-ruled-out option isn't resurfacing, consult both the active index AND the archived
   ones.**
6. **Provenance**: `source` / `confidence` / `ratified` follow the **common lifecycle** defined by
   `../ENTRY-TEMPLATE.md §Confidence lifecycle` — a decision gets **ratified by a human**
   (`confidence: verified` + `ratified: <who>, <YYYY-MM-DD>`), not an unverified inference left as
   is. If it stems from external content (`source: external:<ref>`, `confidence` then mandatory —
   otherwise blocking, `R-EXT-NO-CONF`), note it in the *Why* as well.

> One file per decision (vs a single big file) = no conflict when several contributors add ones
> in parallel.

## Pruning model (when trimming a memory)

1. **Memory ↔ memory conflict** — the most recent entry *that is at least as reliable* wins (a
   `verified` one is never overridden by an `unverified` one) → revocation (never-built →
   deletion; built → tombstone).
2. **Memory ↔ code conflict (the truth)** — the doc/decision says X, the code does Y. The code is
   reality, but which side needs fixing (stale memory or code that drifted from intent) can't be
   settled by a machine → **the user decides**; the AI **flags it**, never silently "corrects" one
   for the other.
3. **Redundancy** — already carried by a living authority (test / architecture / entry) →
   deletion / promotion.
4. **Volume** — audit when the index grows, **run** via the `checks/decisions-audit.py`
   orchestrator (recipe + review rubric: `checks/decisions-audit.md`, decisions slice of the
   multi-channel audit `checks/memory-audit.md`). **No TTL / age alone** ("unused" ≠ "useless").

Every pruning pass is **logged** (reference to the successor + reason + git); never silent.
