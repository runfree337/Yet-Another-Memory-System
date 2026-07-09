# index-eval — per-file index relevance evaluation (recipe + rubric)

> A pure-Python **prefilter** (`prefilter.py`, `lib/*.py`, Tier 0/1 — deterministic,
> zero LLM) does not *judge* on its own: it only flags which groups are worth spending
> an LLM-judged pass on. This document carries the **orchestration recipe** for that
> pass (generator + two routers, protected by a deterministic anti-co-derivation
> guard) and the **scoring rubric** (lift ± confidence interval, per-group verdict) —
> the part no script can settle. Everything below is **agnostic**: each tool packages
> it its own way (see "Packaging per tool").
>
> *Equivalent, in Claude Code format, to the `index-eval` skill* —
> `adapters/claude-code/skills/index-eval.md`.

## Purpose

For each **group** of the per-file index (`index/manifest.tsv`, `path<TAB>intent`, one
line per file — see `index/INDEX.md`), measure whether the **intent** column adds real
semantic **lift** over the bare **file name**, and render a verdict:

**Keep / Marginal / Delete / Undetermined / Not evaluated**, plus a list of entries
**to rewrite** (axis B — the intent hurts routing on specific queries, not that the
whole group should be pruned).

The lift is `diag(name+intent) − diag(names)` — the gain in "queries correctly routed
to the file they came from" when the router also sees the intent — measured under a
**paired confidence interval** (McNemar) so the verdict reflects statistical
confidence, not a single noisy point estimate. A **deterministic guard**
(`lib/guard.py`) keeps the measurement honest: a generated query that recopies the
intent's own vocabulary would let the intent "recognize itself" instead of being
tested on independent ground.

## Architecture — two layers

1. **Prefilter (Tier 0, pure Python, no LLM)** — `prefilter.py` reads the flat
   manifest and computes, per group, the pairwise lexical similarity of its intents
   (`lib/lexsim.py`). A group whose intents are lexically near-duplicates of each
   other (`max_pair_sim >= 0.5`) is `flagged`: a strong signal that at least one
   intent just paraphrases the file name rather than describing what makes that file
   distinct from its neighbors — worth spending an LLM-judged pass on. A group with
   `n_files <= 4` is `too_small` and skips straight to verdict **Not evaluated**, no
   LLM call — too few queries for the confidence interval to mean anything.
2. **LLM-judged routing pass (Tier 1)** — for each *selected* group: a **generator**
   subagent produces "I need the file that…" queries from the **source code**, never
   from the intent (anti-leakage rule below); a deterministic **guard**
   (`lib/guard.py`) rejects any query that leaks the intent's vocabulary; two
   **router** subagents then try to route the (anonymized) queries to the right file —
   one sees file names only, the other sees name+intent. The pure **scorer**
   (`lib/scorer.py`) computes the lift ± McNemar CI from the two routings and classifies
   the verdict. The **reporter** (`lib/reporter.py`) renders the final markdown.

Nothing in this pipeline is Unity- or project-specific: it reads and writes only
`index/manifest.tsv` and `index/index-config.json`, both already generalized by
`checks/index-check.py` / `index/manifest.py`.

**Scope (v1, YAGNI):** no `intent-only` mode, no automatic hook, no auto-rewrite of
intents. This method only **measures and reports** — rewriting an intent stays a
manual, human-reviewed edit via `index/manifest.py set`.

## Configuration — `index/index-config.json`

Same file as `checks/index-check.py` / `index/manifest.py` (schema:
`index/index-config.example.json`), two keys read by `prefilter.py`:

- **`manifest`** (default `index/manifest.tsv`) — same key/default as `index-check.py`.
- **`eval-groups`** (optional array of path prefixes, e.g. `["src/combat/", "src/ui/"]`)
  — the groups prefiltered by default when `prefilter.py` runs with no explicit
  argument. **If absent**, groups are **derived** from the first-level directory
  prefixes actually present in the manifest (`prefilter.derive_groups` — e.g.
  `src/foo/bar.py` yields group `src/`, in first-seen order, deduplicated). A manifest
  with root-level files only (no directory structure) yields no group either way.

Without a config file at all, there is nothing to evaluate (the project hasn't opted
into per-file index evaluation) → `prefilter.py` prints a clear message and exits `0`
— same degradation pattern as `checks/index-check.py`.

## Python API (already delivered — the recipe below only *calls* it)

Imports resolve from `checks/index-eval/` (the scripts' cwd; `lib/` and the package
root are on `sys.path` from there). `prefilter.py` itself runs from **the repo root**
(pass `--config <path>` if `index/index-config.json` isn't at the default location) —
it resolves the manifest relative to the config's `base`.

> **Orchestrator imports.** Any orchestrator code calling `lib.guard.is_contaminated`
> / `lib.scorer.score_group` (steps 6 and 9 below) must run with **cwd =
> `checks/index-eval/`** (or `sys.path.insert(0, "checks/index-eval")`) for
> `from lib.guard import …` / `from lib.scorer import …` to resolve. Only
> `prefilter.py` runs from the repo root.

- **`prefilter.py`** — `load_config(path)` → config dict or `None`.
  `load_manifest(path)` → list of `(path, intent)`.
  `entries_for_prefix(rows, prefix)` → entries `{ "file" (relative to the prefix),
  "intent", "intent_prefixed", "section": None, "dup": False, "raw_line" }`.
  `evaluate_group(prefix, rows, threshold=0.5)` → `{ "group"(=prefix), "n_files",
  "max_pair_sim", "mean_pair_sim", "confusable_pairs", "flagged", "too_small",
  "reason" }`. `derive_groups(rows)` → fallback group list (see Configuration above).
  `main(argv)`: `argv[1:]` (after an optional `--config <path>`) = explicit group
  prefixes, else `eval-groups` from the config, else `derive_groups(rows)`; prints the
  result list as JSON on stdout.
- **`lib/parse.py`** → `parse_subindex(text)` — legacy markdown sub-index parser
  (`- \`path\` — intent`, optionally grouped by `## Section`), still used for ad hoc
  markdown/tests. In flat-manifest mode (the normal path), entries instead come from
  `entries_for_prefix` (no section, `dup` always `False`). `content_tokens(s)` — the
  shared tokenizer (lowercase, drop stopwords, drop tokens <= 2 chars) used by both
  the guard and the lexical similarity.
- **`lib/guard.py`** → `is_contaminated(query, source_intent, threshold=0.5)` → `bool`
  (true if >= 50% of the query's content words are already in the source intent).
- **`lib/scorer.py`** → `score_group(truth, route_names, route_name_intent, n_files,
  qpf=5)`. Inputs = three `{query_id → file}` mappings (the orchestrator has
  **already** de-anonymized `candidate_id → file`). Returns `{ "diag_names",
  "diag_name_intent", "lift", "ci", "n_queries", "verdict", "rewrite", "confusions" }`
  — **not** `group`, `n_files`, or `partial` (the orchestrator adds those, see the
  uniform schema below). If `truth` is empty, returns a neutral dict (`diag_*=None`,
  `ci=[None,None]`, `verdict="Not evaluated"`).
- **`lib/reporter.py`** → `render(results)` → markdown (recap table + per-group
  detail). Tolerant to `None` values; reads `r["partial"]` and `r["rewrite"]`.
- **`lib/sufficiency.py`** (axis B′, optional/complementary) → `score_sufficiency(per_question,
  n_files)` (reuses `scorer.mcnemar_ci`).

Constants (top of the relevant module): guard/flag threshold `0.5`; verdict thresholds
`T_DELETE=0.02` / `T_KEEP=0.10` / `DIAG_FLOOR=0.80` (`lib/scorer.py`); `qpf=5`; **the
per-group sampling cap is `40`** (referenced by the recipe below, not hardcoded in
any module — sampling happens in the orchestrator, see step 3).

## Orchestration recipe

> **`<DATE>`** = today's date, `YYYY-MM-DD`, **supplied by the agent** (the scripts
> have no reliable clock in this harness). Never delegate it to a script.

1. **Prefilter.** From the repo root: `python3 checks/index-eval/prefilter.py [group
   prefix…]` → JSON list, one dict per group. Without arguments, evaluates the
   configured/derived groups (see Configuration); with arguments, only the passed
   prefixes.
2. **Selection.** Keep every group with `flagged == true` **∪** any group named
   explicitly on the command line. Any `too_small == true` group → verdict **Not
   evaluated**, **no LLM call** (neutral dict, see the uniform schema below).
3. **Entries + sample.** For each selected group: `entries_for_prefix(load_manifest(),
   prefix)` → entries (all `dup == False` in flat-manifest mode) as `(file,
   intent_prefixed)` pairs. If `n_files > 40`: take a **representative sample of at
   most 40** — stratify by immediate subdirectory when the group has further nested
   subfolders (at least 1 entry per non-empty subfolder), otherwise a uniform random
   sample — and mark **`partial = true`**. Otherwise `partial = false`.
4. **`role_snippet` (anti-leakage by construction).** For each target file, **read the
   real source file** and extract its **header + public signatures**, capped at **~40
   lines** (absent a doc header, extract the `public`/`class`/`interface`/`def`
   declarations up to ~40 lines). **The intent must never be used as the snippet**:
   the generator has to describe the file's function from its code, never from the
   index phrase. If the source file is missing (an orphan intent), exclude the entry
   and note it in the report.
5. **Generator** (1 subagent, batched input). Feed it `{ id, path, role_snippet }` —
   **with no intent at all**. Contract below (§Generator contract). Output: `{
   "<id>": ["q1"…"q5"] }`.
6. **Deterministic guard.** For each generated query, call
   `lib.guard.is_contaminated(query, source_file_intent)` (run this orchestrator code
   with **cwd = `checks/index-eval/`** or `sys.path.insert(0,
   "checks/index-eval")`, so `from lib.guard import …` resolves). If **true** (the
   query recopies the intent's vocabulary → lexical leak), ask the generator to
   **regenerate** that query (**<= 2 attempts**). After 2 failures, mark the file
   **"vocabulary saturated"**, **exclude all its queries** from this round, and note
   it in the report (it doesn't count towards `n_queries`).
7. **Anonymization.** Build the candidate set (one per retained file), **shuffle**
   queries and candidates, and keep the `candidate_id ↔ file` table and the shuffle
   order **out of every prompt**. Build two candidate views:
   - **`names_only`**: for `C<k>`, the bare **file name** (`file`).
   - **`name+intent`**: for `C<k>`, `file` **+** `intent_prefixed`.
8. **Routers ×2** (2 independent subagents). One receives the `names_only` view, the
   other `name+intent`; **both receive the same query set** (by `qid`, no `path`).
   Contract below (§Router contract). Output of each: `{ "<qid>": "C<k>" }`.
9. **De-anonymization + score.** Via the table kept at step 7, convert the three
   mappings to `{ qid → file }`:
   - `truth` = ground truth (the file the query was derived from),
   - `route_names` = output of the `names_only` router,
   - `route_name_intent` = output of the `name+intent` router.
   Call `lib.scorer.score_group(truth, route_names, route_name_intent, n_files,
   qpf=5)` (same import constraint as step 6: cwd = `checks/index-eval/`, or
   `sys.path.insert(0, "checks/index-eval")`, for `from lib.scorer import …` to
   resolve). **Enrich** the returned dict with `group`, `n_files`, `partial` (the
   scorer doesn't know them).
10. **Report.** Assemble the list of every group's dict (evaluated + neutral "Not
    evaluated"), call `lib.reporter.render(results)`, and **write** the markdown
    wherever the project keeps scratch/report artifacts (e.g. next to the
    `--report`-mode outputs described in `checks/README.md §Semantic`, dated
    `<DATE>`). In the recap, **Not evaluated** groups (`lift=None`) sort first (the
    reporter's own sort key).

## Uniform result schema (guards the reporter against `KeyError`)

Every group — evaluated or not — produces a dict with **always** these keys:

```
group, n_files, partial, verdict,
diag_names, diag_name_intent, lift, ci, n_queries, rewrite, confusions
```

- **Evaluated group:** start from `score_group(...)`'s return (already carries
  `verdict`, `diag_*`, `lift`, `ci`, `n_queries`, `rewrite`, `confusions`) and **add**
  `group`, `n_files`, `partial`.
- **Not evaluated group** (`too_small`, or simply not selected): the orchestrator
  **builds the dict by hand**, neutral values:

  ```
  {
    "group": <prefix>, "n_files": <n>, "partial": False,
    "verdict": "Not evaluated",
    "diag_names": None, "diag_name_intent": None, "lift": None,
    "ci": [None, None], "n_queries": 0,
    "rewrite": [], "confusions": {},
  }
  ```

`render(...)` then handles `None` without raising (tolerant f-strings). **Never omit a
key** — the reporter indexes `r["group"]`, `r["verdict"]`, `r["lift"]`, `r["ci"]`,
`r["diag_names"]`, `r["diag_name_intent"]`, `r["n_queries"]` directly.

## Generator contract (paste verbatim into the subagent prompt)

```
Role: search-need generator.
Input: a list of files `{ id, path, role_snippet }`.
For EACH file, produce 5 "I need the file that…" queries describing its FUNCTION in
business/functional terms. FORBIDDEN: recopying class/method/identifier names from
the snippet — phrase in terms of what it accomplishes, not how it's implemented.
Output STRICT JSON: { "<id>": ["q1","q2","q3","q4","q5"], ... }
```

## Router contract (generic, instantiated twice: `names_only` and `name+intent`)

```
Role: route each query to the candidate that best satisfies it.
Input: candidates `{ Ck: "<candidate text>" }` + queries `{ qid: "<query>" }`.
For each query, pick exactly one Ck. No abstention allowed.
Output STRICT JSON: { "<qid>": "C<k>", ... }
```

The "candidate text" is the bare **file name** for the `names_only` router, and
**name + `intent_prefixed`** for the `name+intent` router.

## Sufficiency mode (axis B′)

**Complementary** axis, run when the question is "does this index save me from
opening the file?" (reading-time economy) rather than "does it help me *choose* the
right file?" (disambiguation, which ceilings out on a repo with descriptive names).
Reuses the prefilter, `entries_for_prefix`, the stratified sample, and `role_snippet`
unchanged. API: `lib/sufficiency.py` → `score_sufficiency(per_question, n_files)`
(reuses `scorer.mcnemar_ci`).

Procedure (parallel to the disambiguation axis, same anti-leakage invariants):
1. **Behavior-question generator.** Per file, from the **`role_snippet` (code, never
   the intent)**: K factual "what this file does" questions + a short reference answer
   derivable from the code. Forbidden to phrase a question whose answer is the file
   name itself.
2. **Two closed-book responders.** Same questions; one receives the **intent alone**
   as context, the other the **file name alone**. No code access. **Abstention is
   mandatory** ("INFORMATION UNAVAILABLE") when the context doesn't carry the answer —
   counted as incorrect (never a guessed answer).
3. **Blind grader.** Receives `{ question, reference, A, B }` where A/B = the two
   answers shuffled (doesn't know which came from the intent). Grades
   `correct`/`incorrect` against the reference. Keep the `A/B ↔ intent/name` table out
   of its prompt.
4. **Score.** De-anonymize A/B, build `per_question = [{qid, file, intent_ok,
   names_ok}]`, call `score_sufficiency` → `suff_intent`, `suff_names`, lift ± paired
   CI, verdict (`Rich intent`/`Useful intent`/`Poor intent`/`Undetermined`/`Not
   evaluated`) and `weak_files` (intent answers 0 of its >= 2 questions → candidate
   for a richer intent).

**Reading the two axes together.** `Poor intent` (B′) **+** `Marginal`/`Delete` (A) =
the intent is genuinely dispensable. `Rich intent` (B′) justifies the intent **even
if** its routing lift (A) is null.

## Anti-leakage rule (non-negotiable invariant)

Two leaks would kill the measurement; the deterministic guard covers one, prompt
discipline the other:

1. **The generator never sees an intent.** It only receives `{ id, path,
   role_snippet }`, the snippet extracted from the **source code** (header +
   signatures, ~40 lines), never from the index phrase. Orchestrator-side guard: any
   query that overlaps the source intent by >= 50% (`lib.guard.is_contaminated`) is
   regenerated (<= 2 attempts); otherwise the file is excluded as "vocabulary
   saturated".
2. **A router never sees the source `path` of a query.** It only receives opaque
   `qid`s and anonymized `C<k>` candidates.
3. **The `candidate_id ↔ file` table and the shuffle order appear in NO prompt** —
   neither the generator's nor the routers'. They stay orchestrator-side, solely for
   the de-anonymization at step 9.

## Notes

- **Paired CI (McNemar).** Both routings share the same queries (positive
  correlation). `lib.scorer.mcnemar_ci` only counts the **discordant** pairs (`b` =
  the intent fixes a names-only error, `c` = the intent introduces one): `lift =
  (b−c)/n`, `var = (b+c − (b−c)²/n)/n²`. Much tighter CI than the independent Wald CI
  (`wald_ci`, kept for diagnostics only).
- **Verdict** rendered by `lib.scorer.classify`, **driven by the CI bounds** (not the
  point estimate alone): `n_files <= 4` → Not evaluated; CI lower bound >= `T_KEEP`
  AND `diag_name_intent >= DIAG_FLOOR` → Keep; CI upper bound < `T_DELETE` → Delete
  (the intent doesn't help, may even hurt); CI strictly positive (lower bound > 0) →
  Marginal (the intent helps, modestly); CI straddling 0 → Undetermined.
- **Ceiling effect (read the verdicts with this in mind).** On a repo with descriptive
  file names, `diag_names` sits close to the ceiling (0.76–0.98) ⇒ the lift margin is
  small and `Keep` (lower bound >= 0.10) stays rare. A `Marginal` with a strictly
  positive CI is therefore already the strong signal "the intent earns its place."
  Possible v1.2 refinement: **relative** lift `lift / (1 − diag_names)` (fraction of
  residual errors fixed), provided the unstable `diag_names → 1` regime (near-zero
  denominator) is handled.
- **Axis B (rewrite).** A file lands in `rewrite` when it misses >= 2 queries
  **concentrated** (>= 2) on the same neighbor under the `name+intent` routing —
  signal to clarify its intent, not to delete it.

## Packaging per tool

The recipe is agnostic; each tool packages it its own way (same logic as
`../../knowledge-capture.md`):

| | The flow (recipe) | The rubric (scoring/verdict) |
|---|---|---|
| **Claude Code** | a **skill** (`index-eval`), orchestrating ad hoc generator/router subagent calls | the verdict grid above, `lib/scorer.py` + `lib/sufficiency.py` |
| **Copilot / other** | an instruction / command | the same generator/router prompts as review/completion prompts |
| **Any tool** | the `prefilter.py` + `lib/*.py` **scripts** are portable as-is (Python, no dependency) | this rubric, unchanged |

This document is the **canonical definition**; per-tool installers materialize it into
concrete artifacts (skill, subagent calls, hook) without rewriting it. Embedded Claude
Code template: `../../adapters/claude-code/skills/index-eval.md`.
