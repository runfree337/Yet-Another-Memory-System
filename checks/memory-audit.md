# Multi-channel memory audit — recipe + rubric (two levels)

> The `memory-audit.py` **script** (tier 1, mechanical) does not *judge* — it chains the
> three integrity checks (`feature-map-check`, `decisions-audit --tier1` — which
> already covers decisions/doc/index/backlog on its own — and `memory-check`) and
> summarizes, without duplicating any of the three. This document carries the **review rubric**
> (tier 2, semantic) for the **three channels** of `WORKFLOW.md §The three memories` —
> the part no script can settle.
>
> *Equivalent, in Claude Code format, to the `memory-audit` skill + `memory-auditor`
> subagent pair.*

## When

- **Volume** — the decisions journal swells (trigger detailed in `decisions-audit.md`).
- **After a branch merge** — possible drift on all three channels at once.
- **On demand** — "does our memory still hold up?"

**Never by age / TTL alone** ("not used" ≠ "useless", `decisions/README.md §pruning`).

## The flow

1. **Integrity** (mechanical): `python3 checks/memory-audit.py --tier1` → one status per channel.
2. **Semantic review, PER CHANNEL** — each has its own pace, no need for a
   single pass across all three:
   - **Decision** — accumulates, so **split into batches**: follow `decisions-audit.md`
     (`decisions-audit.py --plan/--merge`, one reviewer per batch).
   - **Feature** — `FEATURE_MAP.md` is deliberately kept small enough to be **read in
     full** (`WORKFLOW.md`): no splitting, a single pass.
   - **Memory** — only reread the `memory/<slug>.md` files that `memory-check.py` flags
     as candidates: `confidence: unverified` (`R-UNVERIFIED`) OR `confidence: verified` without
     `ratified` (`R-VERIFIED-NOT-RATIFIED`); the rest (`verified` + `ratified` traced) has
     nothing to review.

## The rubric (tier 2)

### Decision channel

Full rubric, output format, coverage check → `decisions-audit.md`. This script
fully delegates this part — it doesn't reimplement it.

### Feature channel

Each entry lives in `features/<slug>.md` (one file per entry, indexed by `FEATURE_MAP.md`):
does it still describe the reality of the code it cites? The mechanical pre-filter has been
enriched with `FM-FRESH` (`feature-map-check.py`: entry `updated` older than the last commit of a
path cited under `**Code:**`) — tier 2 **treats these entries as priority**, without limiting
itself to them (a fresh entry can still have drifted semantically).

| Verdict | Condition | Expected proof |
|---|---|---|
| `STALE` | the **Role** describes a behavior the code no longer does | `file:line` of the diverging code |
| `CODE-MOVED` | a cited path still exists but **elsewhere** — the entry points wrong without being "dead" (dead-path itself is mechanical — `doc-refs-check.py`) | the current real path |
| `UP-TO-DATE` | nothing to report | — |

Only report `STALE` and `CODE-MOVED` — `UP-TO-DATE` doesn't need to be listed.

### Memory (preferences) channel

For every `memory/<slug>.md` flagged by `memory-check.py` (`confidence: unverified` →
`R-UNVERIFIED`, `confidence: verified` without `ratified` → `R-VERIFIED-NOT-RATIFIED`, or
`source: external:...`) — the verdicts now describe the **expected frontmatter
write**, not just a prose judgment:

| Verdict | Condition | Expected proof |
|---|---|---|
| `RATIFY` | recouped against the code/a reliable source, it holds → the agent **proposes** the frontmatter diff that sets `confidence: verified` + `ratified: <who>, <YYYY-MM-DD>` | the recoupment source |
| `REJECT` | recouped, it doesn't hold (stale, contradicted, never verified) → removal of the file + its index line, **logged** (reason + git history) | why it doesn't hold |
| `DOUBT` | inconclusive as-is | 1-sentence reason |

**No write without human ratification** (`MEMORY.md §Provenance`: "nothing gets promoted to
shared memory without going through the traced lifecycle"). `RATIFY` is **never** an
auto-apply: the agent proposes the diff (`confidence: verified` + `ratified:`), the
human applies it.

## Safeguard

The mechanism **reports**, on all three channels. No pruning (deletion, entry
rewritten, entry promoted/removed) is applied without **human ratification**. A
`CODE-DRIFT` (Decision channel) or a `STALE` (Feature channel) is settled by
the user — the AI never silently aligns memory on code, nor the reverse.

## Packaging per tool

| | The flow (recipe) | The rubric (tier 2) |
|---|---|---|
| **Claude Code** | a **skill** (`memory-audit`) | a **subagent** (`memory-auditor`), multi-channel judgment |
| **Copilot / other** | an instruction / command | a **review prompt** (system prompt) per channel |
| **Any tool** | the `memory-audit.py` **script** is portable as-is (Python, no dependency) | this rubric, unchanged |

This recipe is the **canonical definition**; **per-tool installers** will
materialize it into concrete artifacts without rewriting it. Embedded Claude Code template:
`adapters/claude-code/skills/memory-audit.md` (delegates its decisions part to the
`adapters/claude-code/skills/decisions-audit.md` template).
