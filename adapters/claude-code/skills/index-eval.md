# Claude Code template — skill `index-eval`

> Claude Code packaging of the canonical recipe **`../../../checks/index-eval/README.md`**. This
> template redefines NONE of the method — it only says: which script to run, which recipe to
> follow, which output format to render. Any evolution of the flow, the verdict thresholds, or
> the anti-leakage guard happens in `checks/index-eval/README.md`, never here (otherwise a
> duplication that silently drifts).

## Skill `index-eval`

**Trigger** — "evaluate the relevance of the per-file index intents", "does this group's intent
earn its keep over the bare file name", measuring the semantic lift of `intent` over `path` for
one or more manifest groups, or producing an index-eval confusion report. Does **not** evaluate
the code itself, nor index coverage (→ `checks/index-check.py`).

**Steps** (the full flow stays `checks/index-eval/README.md §Orchestration recipe` — this is only
its tooled execution):

1. Run the deterministic prefilter from the repo root:
   `python3 checks/index-eval/prefilter.py [group prefix…]`
   → one JSON dict per group. Without arguments, evaluates `eval-groups` from
   `index/index-config.json`, or the groups derived from the manifest's own first-level <!-- template -->
   directories if that key is absent. **Exits 0 with a plain message when there's no
   `index/index-config.json`** — nothing to prefilter, nothing else to do. <!-- template -->
2. Select the groups to evaluate: `flagged == true` ∪ any group named explicitly on the
   command line. Any `too_small == true` group → verdict **Not evaluated** directly, no LLM
   call (`checks/index-eval/README.md §Uniform result schema`).
3. Build the sample and the anti-leakage `role_snippet` for each selected group's files
   (`checks/index-eval/README.md §Orchestration recipe`, steps 3-4) — read the real source
   files, never the intent.
4. Run the ad hoc subagent calls below (generator → guard → two routers) for each selected
   group, exactly as described in `checks/index-eval/README.md §Orchestration recipe`, steps
   5-9. This is the part no script can do — keep the `candidate_id ↔ file` table and the
   shuffle order out of every subagent prompt (§Anti-leakage rule).
5. Score each evaluated group with `lib.scorer.score_group` (cwd = `checks/index-eval/`, or
   `sys.path.insert(0, "checks/index-eval")`, so `from lib.scorer import …` resolves).
6. Render the report: assemble every group's dict (evaluated + neutral "Not evaluated"), call
   `lib.reporter.render(results)`, and write the markdown wherever the project keeps its
   scratch reports (mirrors the report-artifact convention of `checks/README.md §Semantic`).
7. Return the report to the user. Rewriting an intent stays a manual edit
   (`index/manifest.py set <path> <intent>`) — this skill only measures and reports, it never
   rewrites an intent on its own (`checks/index-eval/README.md §Scope`).

**Tools** — `Bash` (running `prefilter.py`), `Read`/`Grep` (reading source files for
`role_snippet` extraction), plus 3 ad hoc subagent calls per evaluated group (below). No
persistent subagent definition backs these — they are one-shot `Task`-style calls scoped to a
single orchestration run, not reusable named agents.

## Ad hoc subagent contracts (per evaluated group)

**Generator** (1 call, batched across the group's files) — sees `{ id, path, role_snippet }`
only, **never the intent**. Produces 5 "I need the file that…" queries per file, phrased in
function/behavior terms. Contract verbatim: `checks/index-eval/README.md §Generator contract`.

**Router × 2** (independent calls) — one sees `names_only` candidates, the other `name+intent`
candidates; both see the same anonymized queries (`qid` only, no `path`). Contract verbatim:
`checks/index-eval/README.md §Router contract`.

**Output contract** — the orchestrator (the skill itself, not a subagent) holds the
`candidate_id ↔ file` table and the shuffle order; it de-anonymizes the three routings and calls
`lib.scorer.score_group` itself. No subagent call ever sees that table
(`checks/index-eval/README.md §Anti-leakage rule`).

## Optional: sufficiency mode (axis B′)

Same packaging pattern, orchestrating `checks/index-eval/README.md §Sufficiency mode` instead of
the disambiguation recipe — a behavior-question generator, two closed-book responders, a blind
grader, then `lib.sufficiency.score_sufficiency`. Run it when the open question is "does the
intent save me from opening the file?" rather than "does it help me pick the right file?".
