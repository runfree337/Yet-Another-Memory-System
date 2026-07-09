# ROADMAP — improvement tracks

> The framework's **own** todo. Not to be confused with `backlog/`, which is a **template**
> shipped to host projects (`INSTALL.md §Target shape`), nor with `DASHBOARD.md` (state).
> A track is an **objective**, not a plan: no dates, no task breakdown — it becomes a work
> item (with its own state and tasks) the day someone opens it.

## 1. Deterministic index map — less LLM in the navigation layer

The navigation index (`index/`) currently depends on judgment twice: the **intent phrases**
are written by an LLM/human, and the **coverage** of the map (is every file there? is the
structural part fresh?) rests on the same discipline. The measuring side is already
deterministic (`index/manifest.py` checks presence, `checks/index-eval/` measures whether
intents earn their keep, the index-usage metrics measure consultation) — the missing piece
is deterministic **generation and refresh**: derive the file list and the structural facts
(exports, entry points, per-directory census) mechanically from the repo, so that judgment
is spent **only** where it adds value (the intent phrase), and staleness of everything else
is detected — or repaired — without an LLM call.

## 2. Source-code memory — a structural channel

The three memory channels capture the *why* and the *how we work*; none captures the
**structure of the code itself** (symbols, dependency/call edges, the blast radius of a
change). Today the closest thing is `checks/doc-refs-check.py` grepping a flat code corpus
for dead symbols. The track: a **deterministic, local, parsing-based** code-structure memory
— same tier-1 discipline as everything else (no LLM inference, zero-FP, plain files, no
external service) — that the existing checks could consume (symbol existence, impact of a
rename on docs/entries) and an agent could query instead of re-reading files. Scope choice
to make when opening: build a minimal extractor vs. lean on an existing local indexer.

## 3. `install.py` — the interactive installer

Spec'd and pending: `INSTALL.md §Target shape of install.py` (detect → ask → generate the
glue → write an `install-config`, idempotent, CI-friendly). `INSTALL.md` serves as the
manual guide until it exists; `adapters/claude-code/` is its first brick.

## 4. Memory aging — re-verification beyond the inbox

The ratification inbox (`checks/memory-audit.py --pending`) catches entries that were
**never** ratified. Nothing yet catches a `verified` entry whose **subject moved on**: the
paths it links changed after its `updated` date. The track: a deterministic, git-driven
staleness signal ("the code this entry points to changed since it was last touched —
re-verify or re-stamp"), feeding the same report loop as the rest of tier 1. Complements —
never replaces — the "volume" trigger of the semantic audit.
