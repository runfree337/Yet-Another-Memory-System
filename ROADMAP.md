# ROADMAP — improvement tracks

> The framework's **own** todo. Not to be confused with `backlog/`, which is a **template**
> shipped to host projects (`INSTALL.md §Target shape`), nor with `DASHBOARD.md` (state).
> A track is an **objective**, not a plan: no dates, no task breakdown — it becomes a work
> item (with its own state and tasks) the day someone opens it.
>
> **Order = priority** (ratio value / cost), not a dependency chain. Tracks 1 and 2 close
> known holes for a few dozen lines each; track 3 is the only heavy one; tracks 4-6 keep the
> framework honest about itself.

## 1. Memory aging — re-verification beyond the inbox

The ratification inbox (`checks/memory-audit.py --pending`) catches entries that were
**never** ratified. Nothing yet catches a `verified` entry whose **subject moved on**: the
paths it links changed after its `updated` date. The track: a deterministic, git-driven
staleness signal ("the code this entry points to changed since it was last touched —
re-verify or re-stamp"), feeding the same report loop as the rest of tier 1. Complements —
never replaces — the "volume" trigger of the semantic audit.

**Why first.** This is the only track that closes the failure mode the framework itself
names as the worst one (*"an entry that lies is worse than none"*, `WORKFLOW.md`). It is
also the cheapest: `git log --since=<updated> -- <cited paths>` against the paths already
extracted by `hooks/memory-graph.py::extract_paths`. Zero LLM, zero new dependency, one
new rule id per channel (`R-AGED` / `FM-AGED`, to-confirm — never blocking: a change in a
cited file does not *prove* the entry is wrong).

## 2. Cheap ratification — close the loop the inbox opens

`--pending` shows what awaits a human; nothing makes acting on it **cheap**. Today, a
`RATIFY` verdict is a frontmatter diff the human applies by hand — so the marginal cost of
ratifying is high enough that the inbox wins by default, and the tier-1 signal (age,
staleness) turns into a graveyard the framework was explicitly designed to avoid.

The track: make the *human decision* the only expensive part. A single scoped write command
(`entrylib.stamp_updated`'s sibling — e.g. `memory-audit.py --ratify <id> --who <name>`)
that sets `confidence: verified` + `ratified: <who>, <today>` on one entry or a batch,
**and nothing else**. The invariant of `MEMORY.md §Provenance` is preserved: the human still
decides — the command only removes the typing, never the judgment. Symmetrically, a
`--reject <id> --reason <…>` that removes the file + its index line, logged.

## 3. Structural code map — one deterministic extractor, three consumers

*(merge of the former tracks 1 "deterministic index map" and 2 "source-code memory" — they
described the same artifact from two ends)*

The three memory channels capture the *why* and the *how we work*; none captures the
**structure of the code itself** (symbols, exports, entry points, dependency/call edges, the
blast radius of a change). And the navigation index still depends on judgment twice — for the
**intent phrases** (legitimate: that is where judgment adds value) *and* for the **coverage
and structural freshness** of the map (illegitimate: that is mechanical).

Both needs are served by the **same object**: a deterministic, local, parsing-based
extraction of the repo's symbol/structure facts — same tier-1 discipline as everything else
(no LLM inference, zero-FP, plain files, no external service).

**Three consumers, one producer:**
- `index/` — derive the file list, the per-directory census, exports and entry points
  mechanically; judgment is then spent **only** on the intent phrase, and staleness of
  everything else is detected (or repaired) without an LLM call.
- `checks/doc-refs-check.py` — today it *greps a flat code corpus* for dead symbols, the most
  fragile mechanism in the repo. It would consume real symbols instead (`R-DEAD-SYMBOL` /
  `R-GHOST-ABSENCE` become exact rather than lexical).
- **The agent** — query the structure ("who calls X", "what breaks if I rename Y") instead of
  re-reading files: the impact analysis `index/INDEX.md` promises but does not yet deliver.

**Scope decision to take when opening — and the trap to avoid.** *Do not write a parser.*
Lean on an existing local, offline indexer (tree-sitter, universal-ctags, an LSP/SCIP
producer for the host language). The day this track builds its own extractor, the framework
becomes a compiler project. The deliverable is the **contract** (a stable, greppable
symbol/edge file + a query API), not the parsing.

## 4. Memory utility — measure the outcome, not just the usage

The index is **measured**: `checks/index-eval/` asks whether an intent earns its keep over
the bare file name; the index-usage metrics pair asks whether the map is consulted at all.
The three memory channels are measured **only for integrity** (is the entry well-formed, are
its links alive) — never for **utility**: did reading a Feature/Decision/Memory entry change
what the agent did? Save a re-read? Prevent a mistake?

Without that signal, the only possible move on the memory channels is to *add* to them.

The track: an outcome signal for memory, built on the machinery that already exists —
`hooks/memory-graph.py covers <file>` already knows which entry governs a file about to be
edited, and the index-usage tracker already knows what a session consulted. The minimum
viable version is a **consultation-vs-coverage** metric per channel (an entry that covers
files edited N times and was never opened is a candidate for pruning or rewriting), and the
ambitious version reuses the `index-eval` protocol wholesale: an entry has *lift* if an agent
answers a question about the feature correctly with it and wrongly without it.

## 5. `install.py` — the interactive installer

Spec'd and pending: `INSTALL.md §Target shape of install.py` (detect → ask → generate the
glue → write an `install-config`, idempotent, CI-friendly). `INSTALL.md` serves as the
manual guide until it exists; `adapters/claude-code/` is its first brick.

**Prerequisite question, to answer before opening this: who is this for?** With a single
host project, `INSTALL.md` is enough and this track is premature. If the goal is adoption,
this track jumps to **position 1** — and a **second, dissimilar host project** (different
language, different layout) will teach more about the framework's real agnosticism in a week
than any amount of introspection on it.

## 6. Decay — does each channel, check and doc still earn its keep?

Every mechanism in the framework points *outward* (prune a stale entry, delete an intent with
no lift). Nothing points **inward**: no track, no check and no channel has ever been retired,
and none can be, because there is no criterion for it. A memory framework that only grows is
the failure mode it was built to prevent, one level up.

The track: apply the framework's own tools to itself. A periodic, explicit question with a
written verdict — per **check** (has it fired a true positive in the last N months? if never,
it is either perfect or dead weight, and the two are indistinguishable without asking), per
**channel** (is `decisions/` still distinct from the durable doc in practice, or has the
placement router quietly collapsed?), per **doc** (the cross-reference density is deliberate,
but each hop costs an agent context — `WORKFLOW.md §Orients` asks it to read three files
before touching anything; that budget has never been measured).

Deliverable: not a script — a **rubric + a cadence**, in the same tier-2 spirit as
`checks/memory-audit.md`, plus whatever mechanical counter turns out to be cheap (a check's
firing count is one line in the report loop).
