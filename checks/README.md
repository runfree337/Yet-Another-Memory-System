# `checks/` — deterministic process controls

> First tier of the **two-level** pattern: a **mechanical, zero-false-positive script** (it *finds*, doesn't judge) **→** a **semantic review** (the judgment, handled by the **project's review**). By default none of them fix anything: they **report** — the one accepted exception is `--stamp` mode (`backlog-check.py`, `feature-map-check.py`, `memory-check.py` — mechanical, bounded to the `updated` field and the staged scope), see "Pre-commit wiring" below.
>
> **Writing a new check** (agnostic here, or tech-specific on the host project side) → follow
> [`TEMPLATE.md`](TEMPLATE.md): the common shape (`Finding`, two verdicts, git-aware `collect()`,
> pure rules, `0/1/2` exit code) that every linter of this kind converges toward, independently.

## Provided (agnostic)

- **`backlog-check.py`** — integrity of `backlog/` (Backlog channel of the entry template, `ENTRY-TEMPLATE.md`): every doc-backed work item = a `<id>/` folder whose `STATE.md` carries a complete frontmatter (`id/title/status/milestone/after/docs/updated`, validated via `entrylib`) **and a `## Tasks` section** (states `todo/in-progress/blocked/done`, label ≤ 30 words or a `→ working-doc` pointer); `milestone`⟺INDEX group, `after`→real id, `docs`⟺companion docs; soft anti-accumulation guard (STATE.md > 80 lines or a section outside the canon → "durable content living in the state file"). `--board` and `--state <id>` views with task counts, `--json` available. **`--stamp --staged`**: sets `updated = today` on staged STATE.md files + re-stages — **to be wired at PRE-COMMIT**. `--checklist` prints the closure Definition of Done (6 steps); its **Review** step (3) wires the two-tier doctrine stated above into the closure — the standard's tier-1 checks always, the project's review asked unless `closure.review` carries a standing answer.
- **`feature-map-check.py`** — integrity of the **Feature** channel (one file per entry `features/<slug>.md` + `FEATURE_MAP.md` as index): file↔index concordance, channel frontmatter (`entrylib`), core body keys (one `**Role` line, ≥ 1 code path, ≥ 1 durable reference), existence of cited `D-*` ids, no transient reference (`backlog/`), freshness (`updated` vs. the last commit of cited paths) and granularity as a **soft** signal. Dead-path delegated to `doc-refs-check.py`. `--stamp --staged` on `updated`.
- **`decisions-check.py`** — integrity of the **Decision** channel: `D-*.md` files ↔ `INDEX.md` lines concordance (D1/D2), channel frontmatter via `entrylib` (D3), canonical body sections (D4), `status` ⟺ Active/Archived section (D5), sound `replaces`/`replaced-by` revocation graph — reciprocity, no cycle (D6), resolved cross-links (D7).
- **`memory-check.py`** — integrity of the **Memory** channel: one fact per file + frontmatter (`memory/<slug>.md`), `MEMORY.md` = index. All the logic lives in `entrylib` (channel frontmatter, file↔index concordance, cross-links); `source: external:` without `confidence` → blocking; `confidence: unverified` or `verified` without `ratified` → tier 2 candidate. `--stamp --staged` on `updated`. Follows `TEMPLATE.md` to the letter.
- **`decisions-audit.py`** — orchestrator for **decisions-journal audits** ("Volume" trigger when the INDEX swells — the only channel that accumulates enough to justify it). `--tier1` chains `decisions-check`/`backlog-check`/`doc-refs-check`/`index-check`; `--plan` splits `decisions/INDEX.md` into balanced batches (offset/limit) to hand a slice to each reviewer; `--merge` aggregates review outputs **with a coverage check** (each decision audited exactly once). Tier 1 (mechanical); tier 2 (judgment: memory↔code drift, redundancy, conflict) follows the review **rubric** in `decisions-audit.md`.
- **`memory-audit.py`** — **multi-channel** orchestrator (Feature + Decision + Memory): `--tier1` chains `feature-map-check` + `decisions-audit --tier1` + `memory-check`, summarizes per channel. No `--plan`/`--merge` of its own — delegated to `decisions-audit.py` for its only channel that needs one. Tier 2 (judgment, all 3 channels): rubric in `memory-audit.md`.
- **`doc-refs-check.py`** — **dead references** in the docs: a file path cited in a `.md` that doesn't/no longer exists. Firm zero-FP tier (git heuristic: existed then vanished → blocking; never created → to-confirm). Space-in-directory-name paths are handled through their backticked span; runtime-API lookalikes (`Runtime.dataDir/…`) are silenced per project via `doc-refs.ignore-prefixes` in `checks-config.json`. Two agnostic symbol rules (**R-DEAD-SYMBOL** / **R-GHOST-ABSENCE**, the latter requiring the ghost word and the symbol to share a line **segment** — `|`/`;`/sentence enders, never `,`/`:`) tunable per project via `doc-refs.symbol-suffixes` (keep only a project's naming conventions), `doc-refs.ignore-symbols` (drop host-ecosystem API), `doc-refs.symbol-ignore-dirs` (mute on transient doc dirs) — all optional and additive, absent ⇒ unchanged. Two more precision knobs: `doc-refs.neg-words` (extra project-language negation vocabulary appended to the bilingual NEG list) and the built-in `Xxx` PascalCase placeholder (recognized like `XXXX`). *Semantic* drift stays with review.
- **`index-check.py`** — **per-file index integrity** (`manifest.tsv` ↔ actual repo files). The **project** defines roots + extensions in `index/index-config.json` (at install time); without config, inactive. See `../index/INDEX.md`. <!-- template -->

Exit code ≠ 0 on drift → usable as a gate. Run by hand:

```bash
python3 checks/backlog-check.py
python3 checks/feature-map-check.py
python3 checks/decisions-check.py
python3 checks/memory-check.py
python3 checks/doc-refs-check.py
python3 checks/index-check.py             # requires index/index-config.json
python3 checks/decisions-audit.py         # decisions tier1 + journal audit plan
python3 checks/memory-audit.py            # multi-channel tier1 (feature + decisions + memory)
```

## To wire — running automatically

**Two natures, two regimes.** The structural (these scripts) is cheap and gets wired to run often; the semantic (the `memory-audit` audit, tier 2) costs an agent and **doesn't get hooked**.

**Structural — deterministic, hookable:**
- **Claude Code**: `SessionStart` (post-merge / inter-session drift — start clean) and/or `Stop` (end of turn).
- **CI**: a job that fails if a check exits ≠ 0.
- **Otherwise**: by hand before closing a work item.

> **The silence rule — otherwise it gets expensive.** A `SessionStart` hook's output is **injected into the context** = tokens, paid for the whole session. A check hook must therefore be **silent on success** (nothing printed → 0 tokens) and emit only **one terse line per drift**. Key off the **exit code** or an **ASCII marker** (not parsing localized/accented headers — fragile across locales), never dump the full report.
>
> ```sh
> # silent structural sweep + pending report (SessionStart) — agnostic skeleton
> PY=$(command -v python3 || command -v python); [ -z "$PY" ] && exit 0
> lines=""
> "$PY" checks/decisions-check.py >/dev/null 2>&1 || lines="${lines}• decisions: drift\n"
> "$PY" checks/backlog-check.py   >/dev/null 2>&1; [ $? -eq 2 ] && lines="${lines}• backlog: error\n"
> "$PY" checks/doc-refs-check.py 2>/dev/null | grep -q BLOCKING && lines="${lines}• doc: dead ref\n"
> [ -n "$lines" ] && printf "⚠️ structural drift at startup:\n%b" "$lines"
> # pending audit report (produced outside the session by the OS cron, see §Semantic) → the agent ASKS
> REPORT="${YAMS_MEMORY_REPORT_DIR:-.memory-reports}/memory-report.md"
> [ -f "$REPORT" ] && printf "📋 pending memory report: %s — ASK the user whether to process it, then delete it.\n" "$REPORT"
> exit 0          # SILENT if neither drift nor report → 0 tokens injected
> ```
>
> This sweep is the **consumer** of the loop; the **producer** is `decisions-audit.py --report` run by the OS cron (§Semantic) — the Decision channel is the only one whose volume justifies this scheduled report. Deterministic producer (no LLM, outside the session) + silent consumer (surfaces, the human decides) = audit while away **without** autonomous LLM spend.

> **`Stop` wiring — the detailed reminder, PER check (gated exit code).** Second read-only
> pattern, distinct from the `SessionStart` sweep: instead of aggregating several checks into one
> global line, **one hook per check**, fired at end of turn, that stays silent on a clean exit
> code and otherwise relays the check's **own report** + the fix command to
> run. More verbose than the `SessionStart` sweep, so reserved for end of
> session (not every turn or every tool) — it's the last gesture before closing,
> when the cost of letting things drift is highest.
>
> ```sh
> # Stop, one hook per check — agnostic skeleton (e.g. for index-check.py)
> PY=$(command -v python3 || command -v python); [ -z "$PY" ] && exit 0
> report=$("$PY" checks/index-check.py 2>&1); code=$?
> [ "$code" -eq 0 ] && exit 0   # silent on a clean state
> printf '[index-check] drift — %s\nFix before closing, or rerun `python3 checks/index-check.py`.\n' "$report"
> exit 0   # never blocking — informs only
> ```
>
> Embedded implementation: `adapters/claude-code/hooks/stop-check.sh` — same pattern,
> parameterized by the check name as an argument (e.g. `stop-check.sh index-check`, `stop-check.sh backlog-check`).
> Generalizable to any check in this folder: one more `Stop` hook per check you want
> recalled in detail before end of session, on top of the `SessionStart` sweep's global line.

> **Pre-commit wiring — the MUTANT case (`--stamp`).** Only one check in this folder
> doesn't just report: `backlog-check.py --stamp --staged` **writes** (freshness
> date `updated`) then **re-stages**, BEFORE `git commit` runs — the frontmatter
> date mechanically becomes the commit date, without a manual bump that rots.
> Three safeguards that make this a safe mutation (not a disguised semantic
> fix): (1) **strictly staged** scope (`--staged`) — never pulls a file
> outside the current commit; (2) the touched field is **mechanical** (a date), never a
> judgment; (3) **never blocking** — if the write fails, the commit still goes through,
> unstamped, to be fixed next turn.
>
> ```sh
> # PreToolUse(Bash), matcher "git commit*", BEFORE the command runs
> PY=$(command -v python3 || command -v python); [ -z "$PY" ] && exit 0
> "$PY" checks/backlog-check.py --stamp --staged >/dev/null 2>&1
> exit 0   # never blocks — the fix is silent, git commit sees the stamp
> ```
>
> Embedded implementation: `adapters/claude-code/hooks/pre-commit-stamp.sh`.
> Generalizable to any check that would gain a `--stamp` mode on a similar
> mechanical field (e.g. an equivalent freshness date elsewhere) — same triple safeguard.

**Semantic — agent, memory↔code:** the `memory-audit` audit (tier 2, all 3 channels) **is not a hook** — it requires *retrieve-then-verify* judgment and can't run silently every session. Its regime: **Volume trigger** (on the Decision side, the only channel that swells enough for it), **or scheduled**, **or on demand**. For scheduled *while away*, the report loop (see `INSTALL.md` step 5): an **OS cron** runs `decisions-audit.py --report` → writes a **deterministic** report (tier 1, **no LLM**, 0 tokens) to `$YAMS_MEMORY_REPORT_DIR` (default `.memory-reports/`, **to be gitignored**); the `SessionStart` sweep above **detects and surfaces** it; the agent **asks**, the user **decides** whether to wake up tier 2 (LLM, on demand — `memory-audit.py --tier1` first if the Feature/Memory channels are also in doubt). In every case it **reports**; pruning stays **ratified by a human** — a cron never fixes anything on its own.

> **Producer variant — a scheduled AGENT session instead of the OS cron.** The report loop
> above assumes a **persistent local machine**: the cron writes a gitignored file, the next
> `SessionStart` sweep on that same disk surfaces it. That assumption breaks for a team that
> works in **ephemeral remote sessions** (a fresh container per session): a report written to a
> gitignored dir dies with the container, and no later session ever sees it. There, the
> producer is a **scheduled agent session** (e.g. a weekly routine on a cheap model) rather
> than the OS cron. It runs the SAME work — tier 1 (`decisions-audit.py --tier1`), then, when
> the **Volume** trigger fires, tier 2 by balanced batches (`--plan` → one sub-reviewer per
> batch → `--merge` with the coverage check) — but its deliverable is a **report plus a
> proposal branch pushed** (never merged, never touching the default branch), not a
> local file surfaced by a hook. The **Safeguard is unchanged**: the agent PRODUCES and
> PROPOSES, a human RATIFIES — the routine merges nothing, deletes nothing, promotes no entry
> to `confidence: verified`. Choice criterion: **persistent local machine → OS cron**
> (deterministic, 0 LLM tokens, silent consumer); **ephemeral remote sessions → scheduled
> agent** (survives the container, hands back a reviewable branch). See
> `adapters/claude-code/routines/audit-decisions.md` for a routine prompt implementing this
> variant.

## The project brings its OWN

**Code** checks (lint, tests, analyzers, style standards) are **tech-specific** → the **project** brings and wires them, along with the **semantic review** (its own review skill). Here, we only provide **method** checks.

## Universal — security + navigation (provided)

**Security — PROVIDED** in `../hooks/` (portable guards): `poisoning-scan` (invisible/bidi
Unicode), `secret-scan` (keys/tokens), `destructive-guard` (broad commands). To be wired at the
right trigger — per-tool table in `../hooks/README.md`.

<!-- template -->
**Navigation / doc freshness — PROVIDED** here: `doc-refs-check.py` (dead references) and
`index-check.py` (per-file index integrity — the project defines roots+extensions in
`index/index-config.json`).
<!-- /template -->
An adopting project keeps the freedom to have its own `manifest.py` / `doc-audit.py`, richer and
wired to its actual tree — see `SCRIPTS.md §Watch for homonyms`.
