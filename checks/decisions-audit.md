# Decisions journal audit — recipe + rubric (two levels)

> The `decisions-audit.py` **script** (tier 1, mechanical) does not *judge*. This document
> carries the **orchestration recipe** and the **review rubric** (tier 2, semantic) — the
> part no script can settle. Everything is **agnostic**: each tool packages it its own way (see
> "Packaging per tool").
>
> *Equivalent, in Claude Code format, to the `decisions-audit` skill + `decisions-auditor`
> subagent pair.* Scope = the decisions journal only. For the multi-channel audit
> (feature + decision + preferences), see `memory-audit.md`, which delegates its decisions
> part to this recipe.

## When

**"Volume"** trigger of the pruning model (`../decisions/README.md`): the decisions INDEX
swells (proxy: it approaches ~2× the active count), or after a branch merge, or on demand.
**Never by age / TTL alone** ("not used" ≠ "useless").

## The flow

1. **Integrity + plan** (mechanical): `python3 checks/decisions-audit.py` → chains the integrity
   checks (`--tier1`) then **splits the INDEX into balanced batches** (`--plan`: offset/limit/ids
   per batch). Removes the need for manual splitting.
2. **Batch review** (semantic): **one reviewer per batch** applies the rubric below — recoups
   each decision against the **real code** (retrieve-then-verify), outputs the strict format.
3. **Aggregation**: `python3 checks/decisions-audit.py --merge <outputs…>` → classified report +
   **coverage check** (each decision audited **exactly once** — nothing silently skipped).

## The rubric (tier 2)

For every decision: recoup against the repo (**never conclude without grep/read proof**), then
classify — emit **only** the problem entries:

| Verdict | Condition | Proof |
|---|---|---|
| `ARCHIVE-1` | the code subject has **vanished** from the repo | `empty grep: <term>` |
| `ARCHIVE-4` | revoked/replaced entry whose invariant lives **entirely** in the successor | the successor id |
| `REDUNDANT` | invariant **already carried** by a living authority (test, architecture doc, feature entry) | the reference |
| `CODE-DRIFT` | the decision says X, the **code does Y** — **the user decides**, no fix proposed | the divergence |
| `CONFLICT` | contradicts another decision **without** a revocation link | the other id |
| `DOUBT` | suspect, inconclusive | the reason |

**`ARCHIVE-4` is now mechanically pre-filtered.** From the frontmatter (`decisions/README.md
§4-5`), a `status: revoked` entry with a `replaced-by:` that resolves to an id **still
indexed** is already **proven** — `checks/decisions-check.py` (rule `D6`) verifies the target,
the `replaces` reciprocity, the absence of a cycle. The tier 2 reviewer **doesn't rejudge**
this part: it only outputs `ARCHIVE-4` for the residue the mechanical check can't settle —
does the invariant live **entirely** in the successor, or only partly (in which case
it's `DOUBT`, not `ARCHIVE-4`). A dead or non-reciprocal `replaced-by` doesn't even reach
tier 2: `decisions-check.py` blocks it before that.

The reviewer relies on the **frontmatter** to place each decision before judging — `status`
says where it stands (`active`/`revoked`/`archived`), `updated` says its freshness,
`confidence`/`ratified` say whether it's already been ratified. This doesn't change the
substance of the rubric (always recoup against the code), it just avoids rejudging what the
frontmatter already establishes.

**Discernment** (otherwise: false positives): a **process** decision never has a "vanished
subject"; an **enacted removal** (`grep` empty *in line with* the decision) is not a problem;
architecture **yet to be built** (a spec) that the code doesn't have yet is not a drift. Err
toward reporting (`DOUBT` rather than silence), but don't cry wolf.

**Output format** (the aggregator reads it) — one line per problem, nothing before:

```
D-YYYY-MM-DD-NN | VERDICT | gist ≤8 words | proof | confidence:high|medium|low
```

then, as the last line (used by the coverage check): `KEPT: <n> — <ids with no problem>`.

## Safeguard

The mechanism **reports**. No pruning (deletion, archiving, tombstone) nor
**code↔doc** alignment is applied without **human ratification**; a `CODE-DRIFT` / `CONFLICT` is
settled by the user; any retained pruning stays **logged** (successor + reason + history).

## Packaging per tool

The recipe is agnostic; each tool **packages** it its own way (same logic as the
`knowledge-capture.md` table):

| | The flow (recipe) | The rubric (tier 2) |
|---|---|---|
| **Claude Code** | a **skill** (`decisions-audit`) | a **subagent** (`decisions-auditor`), one per batch |
| **Copilot / other** | an instruction / command | a **review prompt** (system prompt) per batch |
| **Any tool** | the `decisions-audit.py` **script** is portable as-is (Python, no dependency) | this rubric, unchanged |

This recipe is the **canonical definition**; **per-tool installers** (Claude Code, Copilot —
to come) will materialize it into concrete artifacts (skill, subagent, hook) without rewriting it.
Embedded Claude Code template: `adapters/claude-code/skills/decisions-audit.md`.
