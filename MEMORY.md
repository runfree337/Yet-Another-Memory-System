# "Preferences & learnings" memory

Two levels, **never** to be mixed:

- **Shared** (team rule, **versioned**) — a preference or rule that holds for everyone. Lives in
  the repo (here, or the project's own convention) and only evolves **explicitly**.
- **Personal** (machine-local, **unversioned**) — your own shortcuts and learnings. Stay **out of
  the repo** (e.g. your tool's automatic memory). Never impose them on the team.

**Promotion / demotion**: a personal learning that turns out to be of general interest can be
*promoted* to shared memory — explicitly. Conversely, a "shared rule" that's really just an
individual taste gets *demoted* out of the repo.

## Shared preferences — one fact per file + frontmatter

Same format as your tool's personal memory (e.g. Claude Code's auto-memory: "one fact per file +
frontmatter; `MEMORY.md` = index") — applied here to **shared** memory. The frontmatter (and
possibly the content) must be **mechanically loadable**, not extracted from a prose line by
regex.

This channel is an **instance** of the `ENTRY-TEMPLATE.md` meta-schema — the common frontmatter,
the index line, the file↔index concordance, and the confidence lifecycle are defined **once and
for all** there; this paragraph only situates the Memory instance, it doesn't reproduce them. The
Memory channel has **no keys of its own**: the common frontmatter is enough (no `status`, unlike
the Decision/Backlog channels).

- **`memory/<slug>.md`** — one file per preference, frontmatter up top (full schema →
  `ENTRY-TEMPLATE.md §The common frontmatter`):
  ```
  ---
  id: mem-null-check-unity
  source: human
  confidence: verified
  created: 2026-07-09
  updated: 2026-07-09
  links: [D-2026-07-09-01]
  ratified: raphael, 2026-07-09
  ---
  <the rule itself, in free prose>
  ```
- **This index (`MEMORY.md`)** — one line per file, never the detail, in the template's uniform
  format (`ENTRY-TEMPLATE.md §The principle`):
  ```
  - [<id>](memory/<slug>.md) — <summary ≤ 1 line>
  ```

*(`memory/` starts empty — the project populates it. `checks/memory-check.py` checks each file
against `checks/entrylib.py::validate_entry(..., "memory")`, the file↔index concordance, and the
`links:` cross-references — see its docstring for the rule table.)*

## Provenance & confidence (against poisoning)

Every write to **shared** memory (and every durable note) carries **where it came from** and
**whether it's validated** — `source`/`confidence` keys from the common frontmatter
(`ENTRY-TEMPLATE.md`):
- **`source`** — `inferred` (deduced by the AI) · `human` (proposed by a human) ·
  `external:<ref>` (taken from **external content** — third-party doc, issue, web page; `<ref>` =
  the source's url/id).
- **`confidence`** — `verified` (a human ratified it) vs `unverified`.

An `unverified` memory, or one with `external:` source, is **not used as a fact**: it gets
**cross-checked** first (real code, a reliable source, or a human). This is the guardrail against
*poisoning* — external content slipped into a note doesn't become "team truth" by mere
persistence. **Nothing gets promoted to shared without going through the tracked lifecycle
below.**

The **capture policy** (`knowledge-capture.md §Capture policy`) parameterizes *where* the AI may
write drafts at all (per-channel `off` / `propose` / `draft`, plus confirmation-gated
`normative-paths`); this provenance lifecycle stays the gate for *what becomes team truth*
regardless of that setting.

### Confidence lifecycle

- **`unverified → verified`** requires `ratified: <who>, <YYYY-MM-DD>` in the frontmatter — the
  AI **proposes** the promotion (the frontmatter diff), the human **ratifies** (sets `ratified`).
  Never self-promotion: an entry at `confidence: verified` with no matching `ratified` is flagged
  (`R-VERIFIED-NOT-RATIFIED`, to-confirm — not blocking, but still an outstanding debt). Full
  mechanics → `ENTRY-TEMPLATE.md §Confidence lifecycle`.
- **Leaving** `verified` (withdrawal or revision) goes through **semantic review** (tier 2,
  `checks/memory-audit.md`) **+ a user decision**, and is **logged** (reason + git history) —
  never silent.

**Conflict resolution**: between two memories that contradict each other, the **more confident
one wins** — a `verified` one is never overridden by an `unverified` one (nor by an uncross-checked
`external:` source); at equal confidence, the most recently ratified one wins.

**Memory ↔ code**: if a memory (decision, doc) diverges from the **code** (the observable truth)
without knowing which one drifted — a stale memory *or* code that moved away from intent — **the
user decides**; the AI **flags it**, it never silently "corrects" one for the other.

> Golden rule: what's versioned **binds everyone**. Only version what's shared and deliberate.
