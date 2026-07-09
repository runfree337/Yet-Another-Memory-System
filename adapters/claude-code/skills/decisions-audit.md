# Claude Code template — skill `decisions-audit` + subagent `decisions-auditor`

> Claude Code packaging of the canonical recipe **`../../../checks/decisions-audit.md`**. This
> template redefines NONE of the scale — it only says: which script to run, which scale to load,
> which output format to render. Any evolution of the flow or the scale happens in
> `checks/decisions-audit.md`, never here (otherwise a duplication that silently drifts).

## Skill `decisions-audit`

**Trigger** — reuse `checks/decisions-audit.md §When`: volume (the decisions INDEX is growing),
after a branch merge, or on demand ("audit the decisions", "do our decisions still hold?").

**Steps** (the full flow stays `checks/decisions-audit.md §The flow` — this is only its tooled
execution):

1. Run `python3 checks/decisions-audit.py` (tier1 + plan). Parameters -> `SCRIPTS.md`.
2. Load the tier 2 scale: `checks/decisions-audit.md §The scale` (verdicts, output format,
   safeguard).
3. For each batch returned by `--plan` (offset/limit), run a `decisions-auditor` subagent
   (below) on that batch.
4. Aggregate: `python3 checks/decisions-audit.py --merge <batch outputs…>` — coverage check
   (every decision audited exactly once).
5. Return the aggregated report to the user. Prune/archive nothing without human ratification
   (`checks/decisions-audit.md §Safeguard`).

## Subagent `decisions-auditor`

**Role** — one reviewer per batch. Cross-checks each decision of the batch against the **actual
code** (retrieve-then-verify, never conclude without grep/read evidence) and renders the strict
format defined by `checks/decisions-audit.md §The scale`:

```
D-YYYY-MM-DD-NN | VERDICT | gist ≤8 words | evidence | confidence:high|medium|low
```

then, on the last line: `KEPT: <n> — <ids with no issue>`.

**Tools** — read-only (file search + read, `grep`/`glob`). Fixes, deletes, archives nothing.

**Output contract** — strictly the format above, nothing before, nothing after: that's what
`decisions-audit.py --merge` parses verbatim for the coverage check.
