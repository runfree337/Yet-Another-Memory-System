# Claude Code template — skill `memory-audit` + subagent `memory-auditor`

> Claude Code packaging of the canonical recipe **`../../../checks/memory-audit.md`**. This
> template redefines NONE of the multi-channel scale — it only says: which script to run, which
> scale to load, which output format to render. The **Decision** part delegates entirely to the
> `decisions-audit.md` template of this same folder — no second definition.

## Skill `memory-audit`

**Trigger** — reuse `checks/memory-audit.md §When`: volume (Decision channel), after a branch
merge, or on demand ("does our memory still hold?").

**Steps** (the full flow stays `checks/memory-audit.md §The flow`):

1. Integrity: `python3 checks/memory-audit.py --tier1` -> one status per channel (Feature,
   Decision, Memory).
2. Semantic review, **per channel**, each at its own pace:
   - **Decision** — accumulated, split into batches -> delegate entirely to the
     `decisions-audit.md` skill of this folder (`decisions-audit.py --plan/--merge`).
   - **Feature** — `FEATURE_MAP.md` reread in a single pass (small by construction): run the
     `memory-auditor` subagent (below) in Feature mode.
   - **Memory** — only reread the `memory/<slug>.md` flagged `confidence: unverified` by
     `memory-check.py`: run the `memory-auditor` subagent in Memory mode.
3. Return the per-channel report. Prune/promote nothing without human ratification
   (`checks/memory-audit.md §Safeguard`).

## Subagent `memory-auditor`

**Role** — semantic judgment on the Feature and Memory channels (the Decision channel stays that
of the `decisions-auditor` subagent, never reimplemented here). Applies the tier 2 scale of
`checks/memory-audit.md §The scale`:

- **Feature**: for each `FEATURE_MAP.md` entry, verdict `STALE` / `CODE-MOVED` / `UP-TO-DATE`
  (only flag the first two) — evidence = `file:line` of the diverging code, or the actual current
  path.
- **Memory**: for each flagged `memory/<slug>.md`, verdict `RATIFY` / `REJECT` / `DOUBT` —
  evidence = the cross-check source, or the reason for the rejection/doubt.

**Tools** — read-only (file search + read). Fixes, deletes, rewrites nothing — proposes, the user
ratifies (**no** promotion to `confidence: verified` without human ratification,
`../../../MEMORY.md §Provenance`).

**Output contract** — one entry per flagged issue, format of the relevant channel's scale;
`UP-TO-DATE` doesn't need to be listed.
