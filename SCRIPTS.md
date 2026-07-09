# Script reference — intent + parameters

> One script per entry: what it **finds** (never what it fixes, unless explicitly noted),
> its **parameters**, its **exit codes**. The *wiring* patterns (when/where to run them) are
> documented separately — `checks/README.md §To wire` and `hooks/README.md §Wiring per tool` for the
> **how**, `INSTALL.md §Wiring overview` for the decision tree. Here: only the
> script itself, independent of its wiring.

## `checks/` — method checks (Tier 1, deterministic)

### `backlog-check.py`
**Intent:** integrity of `backlog/` (frontmatter model, Backlog channel of the common
memory entry template) — every doc-backed work item has a `STATE.md` with a complete and
consistent frontmatter (`id/title/status/milestone/after/docs/updated`, validated via `entrylib.validate_entry`)
and a mandatory `## Tasks` section (one line per task, state `todo/in-progress/blocked/done`,
label ≤ 30 words or a `→ working-doc.md` pointer).

`impacts:` is an optional frontmatter key — the **impact ledger**: filled in during work as
soon as a durable doc/memory is known to need updating, consumed at closure instead of relying
on recall. Each entry is either a target path (`WORKFLOW.md`, `features/x.md` — no existence <!-- template -->
check, it may name a doc to create at closure) or one of the channel keywords
`decision | feature | memory`. `E-IMPACT` (blocking) rejects anything outside that closed
vocabulary; `E-IMPACT-EMPTY` (to-confirm) fires only once every task is `done` and the ledger
is still empty ("ready to close with no declared durable impact?") — silent while work is open.

| Parameter | Effect | Default |
|---|---|---|
| *(none)* | runs the full check, prints the text report | — |
| `--json` | same check, JSON output of findings | disabled |
| `--board` | work-items-by-milestone view with task counts per state (live state pulled from frontmatters + `## Tasks` section) | — |
| `--state <id>` | expands one specific work item (tasks + counts + `impacts:` ledger); without `<id>` lists the valid ids | — |
| `--stamp [files…]` | **writes** `updated: <today>` on the cited `STATE.md` files via `entrylib.stamp_updated`, rewrites the file | acts on the files passed as arguments |
| `--stamp --staged` | same effect as `--stamp`, but scope = `STATE.md` files **staged** in git (`git diff --cached`), and **re-stages** after writing | to be wired at pre-commit |
| `--checklist [id]` | prints the closure checklist (Definition of Done, 5 steps); with `<id>`, the **Durable** step enumerates the item's declared `impacts:` (`update/migrate: … ; record: …`) instead of the generic wording | — |

**Exit codes:** `0` clean · `1` only TO-CONFIRM (`--state` with no hit also returns `1`) · `2` at least one BLOCKING-AUTO.
**Write (`--stamp` mode):** mutates the `updated` field and nothing else — bounded, mechanical, never blocking (see `checks/README.md §Pre-commit wiring`). Same mode on `feature-map-check.py` and `memory-check.py`.

```bash
python3 checks/backlog-check.py                 # text report
python3 checks/backlog-check.py --board          # overview (with task counts)
python3 checks/backlog-check.py --stamp --staged # pre-commit only
```

### `feature-map-check.py`
**Intent:** integrity of the Feature channel (`entrylib` model) — one file per
entry (`features/<slug>.md`) + `FEATURE_MAP.md` as index. File↔index concordance,
frontmatter of the `feature` channel (`entrylib.validate_entry`), core body keys (Role/Code/durable
reference), existence of cited `D-*` ids, absence of transient references, freshness and
granularity as a *soft* signal.

| Parameter | Effect | Default |
|---|---|---|
| *(none)* | text report, sorted blocking then to-confirm | — |
| `--json` | JSON output of findings (5-field `Finding`) | disabled |
| `--stamp [files…]` | **writes** `updated: <today>` on the cited entries | acts on the files passed as arguments |
| `--stamp --staged` | same effect, but scope = `features/*.md` files **staged** in git, and **re-stages** after writing | to be wired at pre-commit |

**Exit codes:** `0` clean · `1` only TO-CONFIRM (`FM-FRESH`, `FM-GRAN` — soft)
· `2` at least one BLOCKING (`FM-INDEX`, `entrylib` frontmatter, `FM1-*`, `FM-DECISION`,
`FM-TRANSIENT`).
**Write (`--stamp` mode):** mutates the `updated` field and nothing else — bounded, mechanical,
never blocking (same safeguard as `backlog-check.py --stamp`).

```bash
python3 checks/feature-map-check.py
python3 checks/feature-map-check.py --stamp --staged   # pre-commit only
```

### `decisions-check.py`
**Intent:** integrity of the **Decision** channel (instance of `ENTRY-TEMPLATE.md`, see
`decisions/README.md`) — eight rules, from file↔INDEX concordance to the revocation graph.
Imports `entrylib` (frontmatter, `validate_entry`, `check_index_concordance`, `check_links`).

| Rule | Severity | What it proves |
|---|---|---|
| `D1` | blocking | orphan `decisions/D-*.md` (missing from `INDEX.md`) |
| `D2` | blocking | id cited in `INDEX.md` with no `D-….md` file |
| `D3` | blocking/to-confirm | complete and valid frontmatter for the `decision` channel (`entrylib.validate_entry`) |
| `D4` | blocking | canonical sections (`**Decision**`/`**Why**`/`**Invariant**`) present in the body |
| `D5` | blocking | `status` ⟺ `INDEX.md` section (`archived` under `## Active`, or `active` under `## Archived`, is blocking; `revoked` unconstrained) |
| `D6` | blocking | sound revocation graph: `replaced-by`/`replaces` resolved, reciprocal, no cycle |
| `D7` (`R-DEAD-LINK`) | blocking/to-confirm | cross-channel `links:` resolved (`entrylib.check_links`) |
| `D8` | to-confirm | `archived`/`revoked` decision **still referenced** by a living entry — `links:` in `memory/`, `features/`, `backlog/<id>/STATE.md`, or a `D-id` mention in a feature body. One finding per (decision, referencing file) pair; the decisions' own `replaces`/`replaced-by` graph and `INDEX.md` are excluded by construction (archival record, not stale references). Never blocking: a living historical citation can be legitimate — the finding asks a human to update the reference or reconsider the archival. |

| Parameter | Effect | Default |
|---|---|---|
| *(none)* | text report | — |
| `--json` | JSON output | disabled |

**Exit codes:** `0` clean · `1` only to-confirm (`R-UNVERIFIED`,
`R-VERIFIED-NOT-RATIFIED`, `R-DEAD-LINK` not resolved to a slug) · `2` at least one blocking.

```bash
python3 checks/decisions-check.py
python3 checks/decisions-check.py --json
```

### `doc-refs-check.py`
**Intent:** dead/drifted references in the docs. Four rules: **R-DEAD-PATH** (a file path
cited in a `.md` that no longer/never existed — git heuristic: existed then vanished =
blocking, never created = to-confirm); **R-DEAD-DECISION** (a `D-YYYY-MM-DD-NN` id with no
matching `decisions/<id>.md` — blocking; inactive without a `decisions/` folder);
**R-DEAD-SYMBOL** (a backticked composed-PascalCase token, e.g. `` `FooBarManager` ``, found
nowhere under the code roots — to-confirm); **R-GHOST-ABSENCE** (the reverse: prose says a
symbol is missing/not yet built while it *does* exist in code — to-confirm, and deliberately
**not** suppressed by the NEG word list, since it fires exactly on those lines). The two
symbol rules are agnostic: they read `roots`/`extensions` from `index/index-config.json` <!-- template -->
(created at install time, schema: `index/index-config.example.json`) and stay silently
INACTIVE without that config — the framework never hardcodes a project's code layout.

| Parameter | Effect | Default |
|---|---|---|
| `paths…` | limits the scan to these paths/files | whole corpus if omitted and `--staged`/`--diff` also absent → see `gather()` |
| `--staged` | scans **staged** git content instead of disk | disabled |
| `--diff` | scans **modified-but-unstaged** `.md` files | disabled |

**Exit codes:** `0` no dead reference · `1` only "to-confirm" · `2` at least one "BLOCKING".

**Template exemption:** an example path (never meant to exist — naming template, config not
yet created by the project…) escapes the scan via an explicit **HTML marker in
the text**, never a hidden allowlist in the script. Two forms, handled by `gabarit_span()`:
line — a path on a line containing `<!-- template -->` is ignored; block — paths on the lines
**between** `<!-- template -->` and `<!-- /template -->` are ignored. The marker stays readable
in plain text in the `.md` (HTML comment — invisible when rendered, visible when editing): no
separate list to keep in sync with the docs.

```bash
python3 checks/doc-refs-check.py                 # script's default corpus
python3 checks/doc-refs-check.py --staged         # pre-commit
python3 checks/doc-refs-check.py --diff           # pre-review, unstaged working tree
python3 checks/doc-refs-check.py Docs/architecture/  # one subfolder
```

### `checks/index-eval/prefilter.py`
**Intent:** Tier 0 lexical prefilter for the **index-eval** method — per-group evaluation of
whether `manifest.tsv` intent phrases add semantic lift over bare file names (full method +
LLM-judged orchestration recipe: `checks/index-eval/README.md`). Reads `index/index-config.json` <!-- template -->
(`manifest`, optional `eval-groups`, else groups derive from the manifest's own first-level
directories) and flags which groups are lexically confusable — near-duplicate intents
(`checks/index-eval/lib/lexsim.py`, pairwise Jaccard) — worth spending an LLM-judged routing
pass on. **Inactive without configuration**, like `index-check.py`.

| Parameter | Effect | Default |
|---|---|---|
| `group prefix…` | limits the prefilter to these path prefixes | `eval-groups` from the config, else derived from the manifest |
| `--config <path>` | path to the config file | `index/index-config.json` | <!-- template -->

**Exit codes:** `0` ran (or no config / empty manifest — inactive, not an error) · `2` manifest missing or config unreadable.

```bash
python3 checks/index-eval/prefilter.py                       # requires index/index-config.json
python3 checks/index-eval/prefilter.py src/combat/ src/ui/    # explicit groups only
```

The scoring/verdict half (`checks/index-eval/lib/scorer.py`, `checks/index-eval/lib/sufficiency.py`,
`checks/index-eval/lib/reporter.py`) and the LLM-judged orchestration (needs generator + two
routers + deterministic anti-leakage guard, `checks/index-eval/lib/guard.py`) are not standalone
scripts — `checks/index-eval/README.md` is the canonical recipe;
`adapters/claude-code/skills/index-eval.md` is its Claude Code packaging.

### `index-check.py`
<!-- template -->
**Intent:** integrity of the per-file index (`index/manifest.tsv` ↔ actual repo files).
**Inactive without configuration** — the host project must provide `index/index-config.json`.

| Parameter | Effect | Default |
|---|---|---|
| `--config <path>` | path to the config file (`roots`, `extensions`, `ignore`, `base`, `manifest`) | `index/index-config.json` |
| `--base <path>` | repo root to scan | `config.base`, otherwise `cwd` |
<!-- /template -->

**Exit codes:** `0` clean **or** config missing/incomplete (inactive, not an error) · `2` manifest missing, config unreadable, or drift detected (`I1` dead entry, `I2` unindexed file).

```bash
python3 checks/index-check.py                                    # requires index/index-config.json
python3 checks/index-check.py --config index/index-config.json --base .
```

### `entrylib.py`
**Intent:** **shared library**, NOT a standalone check — an in-house minimal frontmatter
parser (no yaml dependency) + validation of the common **memory entry** schema
(`ENTRY-TEMPLATE.md`), plus the file↔index concordance generalized from `memory-check.py` /
`decisions-check.py`. Imported by the **channel** checks (`memory-check.py`, `decisions-check.py`,
`feature-map-check.py`, `backlog-check.py`) — **a single place defines what a valid
entry is**, no more regex duplication between checks.

Public API: `Finding`/`BLOCKING`/`CONFIRM` (the `checks/TEMPLATE.md` template), `CHANNELS`
(required/optional/enum spec per channel), `parse_frontmatter(text)`, `validate_entry(path, meta, channel)`,
`check_index_concordance(index_path, entries_dir, id_pattern)`, `stamp_updated(path, date_str)`.

| Parameter | Effect | Default |
|---|---|---|
| `--selftest` | **only runnable mode** — embedded test suite (string fixtures + tempfile), one per rule | — |

**No effect when imported** — no `main()` triggered on `import`, only definitions.

**Exit codes (`--selftest`):** `0` all tests pass · `1` at least one failure (detail
printed, one per line). Outside `--selftest`, `main()` prints usage and returns `0` (a reminder
that this isn't a check to be wired on its own).

```bash
python3 checks/entrylib.py --selftest
python3 -c "import sys; sys.path.insert(0, 'checks'); import entrylib"   # no side effect
```

### `memory-check.py`
**Intent:** integrity of the **Memory** channel — "one fact per file + frontmatter" format
(`memory/<slug>.md`), `MEMORY.md` = index. Instance of `ENTRY-TEMPLATE.md`: all the logic
(frontmatter, file↔index concordance, cross-links) lives in `checks/entrylib.py` — this
script just calls `entrylib` with the `"memory"` channel and aggregates, it doesn't redefine
any rule locally.

Rules surfaced as-is from `entrylib.validate_entry(..., "memory")`:
`R-NO-FRONTMATTER`, `R-MISSING-KEY`, `R-BAD-VALUE`, `R-EXT-NO-CONF`, `R-BAD-DATE`,
`R-UNVERIFIED` (to-confirm), `R-VERIFIED-NOT-RATIFIED` (to-confirm); plus file↔index concordance
via `entrylib.check_index_concordance` (`R-ORPHAN-FILE`, `R-DEAD-INDEX`) and cross-links
via `entrylib.check_links` (`R-DEAD-LINK`, blocking on id/path, to-confirm on a
slug from a not-yet-populated channel). Follows `TEMPLATE.md` to the letter.

No targeting parameter (like `decisions-check.py`, always compares `MEMORY.md` and
`memory/` in full — a file↔index concordance can't be scoped to a subset).
**Write (`--stamp` mode):** bounded to the `updated` field (same triple safeguard as
`backlog-check.py` — staged scope, mechanical field only, never blocking).

| Parameter | Effect | Default |
|---|---|---|
| `--json` | JSON output | disabled |
| `--stamp [files…]` | **writes** `updated: <today>` on the cited `memory/*.md` files | acts on the files passed as arguments |
| `--stamp --staged` | same effect, but scope = `memory/*.md` files **staged** in git, and **re-stages** after writing | to be wired at pre-commit |

**Exit codes:** `0` clean · `1` only "to-confirm" · `2` at least one blocking.

```bash
python3 checks/memory-check.py
python3 checks/memory-check.py --json
python3 checks/memory-check.py --stamp --staged   # pre-commit only
```

### `decisions-audit.py`
**Intent:** orchestrator for the **decisions journal** — checks nothing itself, chains/aggregates
the 4 scripts above and drives the Tier 1 → Tier 2 cycle. Renamed from `memory-audit.py`: its
real scope is the decisions journal, not the whole memory — see `memory-audit.py` below
for the multi-channel orchestrator. Four mutually exclusive modes (priority order:
`--report` > `--merge` > `--plan` > `--tier1` > *default = both*).

| Parameter | Effect | Default |
|---|---|---|
| `--tier1` | chains `decisions-check`, `backlog-check`, `doc-refs-check`, `index-check`, prints an aggregated verdict | — |
| `--plan` | splits `decisions/INDEX.md` into balanced batches (offset/limit), one batch per reviewer | — |
| `--stale-first` | (`--plan` only) prioritizes batch ORDER by oldest frontmatter `updated` — each batch's offset/limit stays a contiguous range of lines | disabled |
| `--merge <files…>` | aggregates Tier 2 agent outputs, **coverage check** (each decision audited exactly 1×) | — |
| `--report [dir]` | writes a **deterministic report** (no LLM) — meant for a headless OS cron | folder: `$YAMS_MEMORY_REPORT_DIR` or `.memory-reports/` |
| `--batch-size <n>` | batch size for `--plan` | `33` |
| `--index <path>` | path to the decisions journal | `decisions/INDEX.md` |
| `--json` | JSON output (`--plan` only) | disabled |
| *(none)* | equivalent to `--tier1` then `--plan` | — |

**Exit codes:** `--tier1` → the worst exit code among the 4 underlying scripts (`0`/`1`/`2`) · `--plan`/`--report` → `0` (never blocking, they produce an artifact) · `--merge` → `0` full coverage, `1` a decision unaudited or audited twice.

```bash
python3 checks/decisions-audit.py                              # tier1 + plan, common usage
python3 checks/decisions-audit.py --plan --stale-first --batch-size 20
python3 checks/decisions-audit.py --merge batch1_output.txt batch2_output.txt
python3 checks/decisions-audit.py --report                      # OS cron, headless
```

### `memory-audit.py`
**Intent:** **multi-channel** orchestrator (Feature + Decision + Memory, `WORKFLOW.md §The
three memories`) — chains `feature-map-check.py` and `decisions-audit.py --tier1` (which
already covers decisions/doc/index/backlog) and `memory-check.py`, summarizes per channel. No
`--plan`/`--merge`/`--report` of its own: only the Decision channel accumulates enough to
justify splitting into batches — delegated to `decisions-audit.py`. Feature and Memory are reread
in one single pass (small by construction).

| Parameter | Effect | Default |
|---|---|---|
| `--tier1` | chains the 3 channels, prints one verdict per channel | — |
| `--pending` | the **ratification inbox**: scans `memory/`, `features/`, `decisions/`, `backlog/<id>/STATE.md` directly (`entrylib.parse_frontmatter`) and lists every entry awaiting a human in one view — **PENDING RATIFICATION** (`confidence: unverified`, oldest `updated` first) and **RATIFICATION NOT TRACKED** (`verified` with no `ratified` field). Files with no frontmatter/`confidence` are skipped, never errored on. | — |
| `--json` | JSON output (with `--pending`: flat list of `channel/path/updated/source/kind`) | disabled |
| *(none)* | equivalent to `--tier1` | — |

**Exit codes:** `--tier1` → the worst exit code among the 3 underlying channels (`0`/`1`/`2`) ·
`--pending` → `0` inbox empty, `1` otherwise (informational, never `2`).

```bash
python3 checks/memory-audit.py                              # tier1 on the 3 channels
python3 checks/memory-audit.py --pending                     # what awaits my ratification?
python3 checks/memory-audit.py --json
```

---

## `index/` — manifest maintenance (write)

<!-- template -->
Write-side counterpart to `index-check.py` above (which stays read-only). Same
config-agnostic setup (`index/index-config.json`), no verification logic duplicated between the two.

### `manifest.py`
**Intent:** the only way to edit `index/manifest.tsv` — add/remove an entry, keep the
file sorted and deduplicated. **Inactive without configuration**, like `index-check.py`.
<!-- /template -->

| Command | Effect |
|---|---|
| `set <path> <intent>` | upserts the entry (adds or replaces the intent), rewrites the manifest sorted |
| `rm <path>` | removes the entry; no-op if absent |
| `get <path>` | prints the intent of this path (empty if absent) |
| `stamp` | if `hub` is set in the config, updates its `> Last updated: ...` line (date + short commit); **no-op** if `hub` is `null`/absent, or if the file doesn't have that line |

No `check` command here — `checks/index-check.py` is the one that verifies drift; `manifest.py`
only writes what it's given, it doesn't scan the repo to detect drift itself.

**Exit codes:** `0` command executed · `1` config missing/unreadable, or invalid usage (no recognized command, prints help) · `2` `hub` configured but not found on disk.

```bash
python3 index/manifest.py set src/foo.py "parser entry point"
python3 index/manifest.py rm src/old.py
python3 index/manifest.py get src/foo.py
python3 index/manifest.py stamp             # updates index/INDEX.md if `hub` points to it
```

---

## `hooks/` — universal guards (security, portable)

All share the same two-entry contract: a **universal entry** (paths/`--staged`,
for git or manual use) and a **Claude Code adapter entry** (`--stdin-json`, reads the
`tool_name`/`tool_input` JSON of the hook). See `hooks/README.md §Wiring per tool` for the where/when.

### `poisoning-scan.py`
**Intent:** detects invisible/bidi Unicode in instruction and memory files
(poisoning vector — hidden text that fools the AI without being visible to the eye).

| Parameter | Effect | Default |
|---|---|---|
| `paths…` | files/paths to scan | — |
| `--staged` | scans staged git content | disabled |
| `--stdin-json` | reads `{tool_name, tool_input}` on stdin, scans the **incoming content** (`tool_input.content` / `new_string`) — the injection vector, never the stale on-disk file | disabled |

**Exit codes:** `0` clean (or unreadable JSON in `--stdin-json` mode — never fails the hook) · `2` suspicious characters found → **block**.

```bash
python3 hooks/poisoning-scan.py --staged
echo '{"tool_name":"Write","tool_input":{"file_path":"CLAUDE.md","content":"…"}}' | python3 hooks/poisoning-scan.py --stdin-json
```

### `secret-scan.py`
**Intent:** detects committed or written keys/tokens (18 patterns — cloud providers, VCS,
messaging, payment…).

| Parameter | Effect | Default |
|---|---|---|
| `paths…` | files to scan directly | — |
| `--staged` | scans staged git content | default behavior if neither `paths` nor `--stdin-json` |
| `--stdin-json` | Claude Code adapter: on `Bash` with `git commit` → scans staged content; on `Write`/`Edit` → scans written content (allowlisted files/ignored extensions excluded) | disabled |

**Exit codes:** `0` clean · `2` potential secret found → **block**, masked in the report.

```bash
python3 hooks/secret-scan.py --staged
python3 hooks/secret-scan.py path/to/file.env
```

### `destructive-guard.py`
**Intent:** spots broad destructive shell commands (`find … -delete`, `-exec rm`,
etc.) — the only guard that doesn't block but **asks for confirmation**.

| Parameter | Effect | Default |
|---|---|---|
| `--command "<cmd>"` | command to evaluate, universal mode | `""` |
| `--stdin-json` | Claude Code adapter: on a destructive `Bash` command → emits a `permissionDecision: "ask"` response (JSON on stdout) instead of blocking | disabled |

**Exit codes:** universal mode — `0` harmless · `2` destructive → **block** (non-interactive mode can't "ask", so it blocks). `--stdin-json` mode — always `0`, the decision is carried by the emitted JSON (`ask` or nothing).

```bash
python3 hooks/destructive-guard.py --command "find . -name '*.tmp' -delete"
```

---

## What does NOT belong here

The **tech-specific** scripts of the host project (lint, tests, analyzers…) are not part of this
framework — they stay documented by the project itself. This file only references what
**YAMS** provides. To write one on the project side (like the reference host project's
`audit.py`): `checks/TEMPLATE.md` gives the common shape, not the tech-specific content.

> **Watch for homonyms**: a project adopting YAMS may already have its own `manifest.py` /
> `doc-audit.py` scripts (or equivalents), richer and wired to its actual tree — don't confuse
> them with the ones provided here. **This framework's** `index/manifest.py`
> is a distinct script, generalized over `index-config.json` — it has no `check`
> command (delegated to `checks/index-check.py`) nor a dedicated filter (covered by
> `roots`/`extensions`/`ignore` in the config).
