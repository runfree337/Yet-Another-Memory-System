# Script reference — intent + parameters

> One script per entry: what it **finds** (never what it fixes, unless explicitly noted),
> its **parameters**, its **exit codes**. The *wiring* patterns (when/where to run them) are
> documented separately — `checks/README.md §To wire` and `hooks/README.md §Wiring per tool` for the
> **how**, `INSTALL.md §Wiring overview` for the decision tree. Here: only the
> script itself, independent of its wiring.

## The global settings file

Optional, at the repo root: `checks-config.json` (canonical schema + defaults: <!-- template -->
[`checks-config.example.json`](checks-config.example.json)). One file, one section per concern:
`audit` (when the deterministic report recommends a tier-2 audit), `sizes` (granularity
signals), `guards` (extension-only surveillance lists), `doc-refs` (R-DEAD-PATH + symbol-rule tuning),
`closure` (the project's answer on the DoD review step). Absent file or key = the built-in
defaults, i.e. the historical behavior. Present but broken, the two families diverge **by
design**: the **checks** surface a blocking `CFG-INVALID` finding (a config the user believes
active is never silently ignored), while the **hooks** fall back to their built-ins without
crashing (a guard in the write path must always answer). Loader:
`entrylib.load_checks_config()` + `cfg_get()`. Method-calibration constants
(`checks/index-eval` scorer/sufficiency thresholds) are deliberately **not** here — they define
what the metric means, not per-project taste.

## `checks/` — method checks (Tier 1, deterministic)

### `backlog-check.py`
**Intent:** integrity of `backlog/` (frontmatter model, Backlog channel of the common
memory entry template) — every doc-backed work item has a `STATE.md` with a complete and
consistent frontmatter (`id/title/status/milestone/after/docs/updated`, validated via `entrylib.validate_entry`)
and a mandatory `## Tasks` section (one line per task, state `todo/in-progress/blocked/done`,
label ≤ 30 words or a `→ working-doc.md` pointer). The size thresholds read the global
settings file: `sizes.backlog-state-max-lines` (default 80),
`sizes.backlog-task-label-max-words` (default 30) and
`sizes.backlog-index-entry-max-words` (default 60) — the last one bounds an `INDEX.md`
entry (bullet + wrapped lines, `[…]` tokens excluded, rule `I-ENTRY-LEN`, to-confirm):
the line is title + target + one-sentence gist, detail and history live in the work
item's folder and `git log`.

`impacts:` is an optional frontmatter key — the **impact ledger**: filled in during work as
soon as a durable doc/memory is known to need updating, consumed at closure instead of relying
on recall. Each entry is either a target path (`WORKFLOW.md`, `features/x.md` — no existence <!-- template -->
check, it may name a doc to create at closure) or one of the channel keywords
`decision | feature | memory`. `E-IMPACT` (blocking) rejects anything outside that closed
vocabulary; `E-IMPACT-EMPTY` (to-confirm) fires only once every task is `done` and the ledger
is still empty ("ready to close with no declared durable impact?") — silent while work is open.

`E-STATE-FRESH` (to-confirm) is the Backlog channel's freshness relay, same form as
`FM-FRESH`: the frontmatter `updated` is older than the last git commit touching the
STATE.md itself — the pre-commit stamp did not run on that commit (hook uninstalled,
`--no-verify`, or absent, e.g. an ephemeral container). Soft by design (a host where part
of the work happens where no hook can run would make a blocking tier noisy by
construction), silent on unversioned files, and it never asks for a hand-bump: a drifted
date self-heals at the next stamped pass.

`closure.review` (global settings file) answers, once and for all or not at all, the **Review**
step of the DoD (step 3): a non-empty string is printed in place of the generic project half
(what "reviewing" means in this project), `false` prints the step as explicitly waived, an
absent key leaves the generic wording, which tells the agent to **ask** the user. The tier-1
half of the step ("run `memory-audit.py --tier1`") is the standard's own and is never
substituted. `--checklist` only ever **prints** — the asking is the agent's job, tier 1 stays
non-interactive.

| Parameter | Effect | Default |
|---|---|---|
| *(none)* | runs the full check, prints the text report | — |
| `--json` | same check, JSON output of findings | disabled |
| `--board` | work-items-by-milestone view with task counts per state (live state pulled from frontmatters + `## Tasks` section) | — |
| `--state <id>` | expands one specific work item (tasks + counts + `impacts:` ledger); without `<id>` lists the valid ids | — |
| `--stamp [files…]` | **writes** `updated: <today>` on the cited `STATE.md` files via `entrylib.stamp_updated`, rewrites the file | paths framework-relative, repo-relative or absolute; one that resolves to no file is named on stderr, never swallowed |
| `--stamp --staged` | same effect as `--stamp`, but scope = `STATE.md` files **staged** in git (`git diff --cached`), and **re-stages** after writing | wired at pre-commit via the stamp home `hooks/stamp-staged.sh` (callers: `adapters/git/pre-commit`, `adapters/claude-code/hooks/pre-commit-stamp.sh`); selection via `entrylib.stamp_targets`, so it holds when the framework is nested |
| `--checklist [id]` | prints the closure checklist (Definition of Done, 6 steps); with `<id>`, the **Durable** step enumerates the item's declared `impacts:` (`update/migrate: … ; record: …`) instead of the generic wording; the **Review** step substitutes the project's half from `closure.review` | — |

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
granularity as a *soft* signal. The `FM-GRAN` threshold reads the global settings file:
`sizes.feature-entry-max-lines` (default 60). An **absent or empty channel is said
explicitly** (text mode): "channel absent — nothing to verify" / "0 entries — … nothing
verified", never a bare `OK.` a reader would take for a verified channel — an index in
another format is invisible to this check, not validated by it.

| Parameter | Effect | Default |
|---|---|---|
| *(none)* | text report, sorted blocking then to-confirm | — |
| `--json` | JSON output of findings (5-field `Finding`) | disabled |
| `--stamp [files…]` | **writes** `updated: <today>` on the cited entries | paths framework-relative, repo-relative or absolute; an unresolved one is named on stderr |
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
`decisions/README.md`) — ten rules, from file↔INDEX concordance to the revocation graph
and the channel's size signals. Imports `entrylib` (frontmatter, `validate_entry`,
`check_index_concordance`, `check_links`, `check_index_entry_len`).

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
| `D9` | *retirée* | remplacée par `D12`. Elle bornait le corps ENTIER, en miroir de `FM-GRAN`/`M-GRAN` — l'instrument juste pour Feature et Memory, dont le corps est libre. Le corps d'une décision ne l'est pas (`D4` impose trois sections, bloquant) : un total sur un corps structuré ignore la structure, et ne désigne rien à couper. Id retiré, jamais réutilisé. |
| `D11` | to-confirm | lignes de bannière (blockquote) > `sizes.decision-banner-max-lines` (défaut 20) — les notes d'amendement et de révocation sont du protocole, mais une bannière qui déborde son budget est de l'analyse déguisée. |
| `D12` | to-confirm | une section canonique > `sizes.decision-section-max-lines` lignes écrites (défaut 20) — le signal NOMME la section, et chacune a son remède : une `**Decision**` trop longue fait du design, un `**Why**` trop long est l'analyse qui appartient à la doc durable. |
| `D10` | to-confirm | `INDEX.md` entry (bullet + wrapped lines, `[…]` tokens excluded) > `sizes.decisions-index-entry-max-words` words (default 80) — the line is id + title + one-line invariant; anything more lives in the `D-….md` file. |
| `CFG-INVALID` | blocking | `checks-config.json` present at the repo root but broken — never silently ignored (same convention as the sibling checks). |

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
blocking, never created = to-confirm; the "existed" lookup runs on **one** cached
`git log --all --name-only` dump per run, never one `git log` per token — hookable even on a
large history. A path to an existing **directory** counts as alive, same reach as a git
pathspec. Backticked spans are scanned **in place**: a fragment that looks dead only because
the real directory name contains a space — `` `Tools/My Dir/file.py` `` fragments to <!-- template -->
`Dir/file.py` — is re-anchored across the span before flagging, existence first, then git <!-- template -->
history for the severity. The final path segment accepts up to 16 chars after the last dot,
with a boundary lookahead: a package id like `com.example.roundedcorners` is one token, never
truncated to a ghost `…rounde`, while a sentence-final dot still ends the token. Tokens
matching a `doc-refs.ignore-prefixes` entry (`checks-config.json`, optional, empty by
default) are skipped — for runtime-API-joined names like `Runtime.dataDir/…`
that look like repo paths but never are); **R-DEAD-DECISION** (a `D-YYYY-MM-DD-NN` id with no
matching `decisions/<id>.md` — blocking; inactive without a `decisions/` folder);
**R-DEAD-SYMBOL** (a backticked composed-PascalCase token, e.g. `` `FooBarManager` ``, found
nowhere under the code roots — to-confirm); **R-GHOST-ABSENCE** (the reverse: prose says a
symbol is missing/not yet built while it *does* exist in code — to-confirm, and deliberately
**not** suppressed by the NEG word list, since it fires exactly on those lines; the ghost word
and the symbol must share a **segment** of the line — split on `|`/`;`/sentence enders, never
`,`/`:` — so a ghost word one table cell or one clause away is not read as a claim about the
symbol, which drops ~two-thirds of the line-cooccurrence noise). The two
symbol rules are agnostic: their code corpus comes from the **dedicated keys**
**`code-roots`** + **`code-extensions`** (`checks-config.json`, dirs resolved from the **repo
root** — git toplevel; set together or not at all, exactly one is a BLOCKING `CFG-INVALID`),
falling back on `roots`/`extensions` from `index/index-config.json` <!-- template -->
(created at install time, schema: `index/index-config.example.json`) when the keys are absent,
and stay silently INACTIVE without either — the framework never hardcodes a project's code
layout. The dedicated keys exist because reusing index-check's file proved a trap on a host
with the framework nested under a subdir (`Docs/`): its `base` resolves against the framework
root in doc-refs but against the cwd in index-check — one file cannot satisfy both — and merely
creating it wakes index-check up against a manifest whose path format the project may not
share. Same
reasoning extends their tuning to three optional, additive `doc-refs` keys (all empty by
default ⇒ today's behavior): **`symbol-suffixes`** — when non-empty, a candidate is kept only
if it ends with a project-declared suffix (`Manager`/`View`/`Registry`…), the lever that
silences a host ecosystem's API cited across the docs since a project's naming conventions are
known only to it; **`ignore-symbols`** — literal candidate exclusions for host-ecosystem API
(`MonoBehaviour`…), additive not substitutive; **`symbol-ignore-dirs`** — doc dirs (relative
to the framework root) where the two symbol rules are muted (transient docs naming not-yet-built
types, e.g. `backlog/`), while R-DEAD-PATH / R-DEAD-DECISION stay active there (a dead path in
a transient doc is a real drift, an unwritten type is not). Two more precision knobs sit outside
the symbol-corpus family: **`neg-words`** appends project-language negation vocabulary (French
`pas d'`, `non retenue`…) to the built-in bilingual NEG list, so a symbol/path the prose itself
says is absent stops being double-reported — declared per project rather than baking broad words
into every default; and the `Xxx` PascalCase placeholder is now recognized built-in alongside
`XXXX`, so fill-in-the-blank names (`CampJournalXxxTab`) are treated as templates, not dead symbols.
Past the segment split, the residual R-GHOST-ABSENCE noise is grammatical — a ghost word bound to
a *neighbouring* noun, the symbol being only its container (`icône absente du SpriteRegistry`
claims the icon is absent, not the registry) — and grammar is a language's own, so it follows the
same route as `neg-words`: **`ghost-exclude-patterns`** holds project-declared regexes
(case-insensitive) matched against the segment the rule is about to flag; a match suppresses the
rule for that segment only. Purely **suppressive** — a pattern can only remove findings, never add
one, so the zero-FP contract is untouched; an invalid regex is a BLOCKING `CFG-INVALID`, never
silently dropped; and the project answers for the precision of what it declares (an over-broad
pattern can mask a genuine ghost). This is a bridge: the code-symbol-graph track (`ROADMAP.md §3`)
is the exact fix, after which a project's patterns simply empty out.

| Parameter | Effect | Default |
|---|---|---|
| `paths…` | limits the scan to these paths/files | whole corpus if omitted and `--staged`/`--diff` also absent → see `gather()` |
| `--staged` | scans **staged** git content instead of disk | disabled |
| `--diff` | scans **modified-but-unstaged** `.md` files | disabled |
| *(settings)* `doc-refs.ignore-prefixes` | token prefixes never treated as repo paths (R-DEAD-PATH only) | `[]` |
| *(settings)* `doc-refs.symbol-suffixes` | keep only PascalCase candidates ending in one of these (R-DEAD-SYMBOL / R-GHOST-ABSENCE); empty ⇒ all | `[]` |
| *(settings)* `doc-refs.ignore-symbols` | literal candidate exclusions, host-ecosystem API (same two rules) | `[]` |
| *(settings)* `doc-refs.symbol-ignore-dirs` | doc dirs (framework-relative) where the two symbol rules are muted | `[]` |
| *(settings)* `doc-refs.neg-words` | extra project-language negation words appended to NEG (suppress R-DEAD-PATH/DECISION/SYMBOL, never R-GHOST-ABSENCE) | `[]` |
| *(settings)* `doc-refs.ghost-exclude-patterns` | case-insensitive segment regexes suppressing R-GHOST-ABSENCE where they match — a project's grammar as config data, suppressive only | `[]` |
| *(settings)* `doc-refs.code-roots` | dedicated corpus dirs for the two symbol rules, resolved from the repo root — set with `code-extensions`, replaces the `index-config.json` fallback | `[]` |
| *(settings)* `doc-refs.code-extensions` | file extensions of the dedicated corpus (e.g. `.cs`) — set with `code-roots` | `[]` |

**Exit codes:** `0` no dead reference · `1` only "to-confirm" · `2` at least one "BLOCKING"
(including `CFG-INVALID` — `checks-config.json` present but broken, same convention as the
channel checks).

**Template exemption:** an example path (never meant to exist — naming template, config not
yet created by the project…) escapes the scan via an explicit **HTML marker in
the text**, never a hidden allowlist in the script. Two forms, handled by `gabarit_span()`:
line — a path on a line containing `<!-- template -->` is ignored; block — paths on the lines
**between** `<!-- template -->` and `<!-- /template -->` are ignored. The marker stays readable
in plain text in the `.md` (HTML comment — invisible when rendered, visible when editing): no
separate list to keep in sync with the docs.

**Ignore pragma:** a second marker, `<!-- doc-refs: ignore -->`, silences **every** doc-refs rule
on its own line (that line only — no block form). Same explicit-marker philosophy, different
*intent*: `<!-- template -->` says "this target is an example, never meant to exist"; the pragma
says "a human reviewed this finding and keeps the prose as-is". Reserve it for the residue no
config key covers cleanly — a config pattern is reread in one place, ten scattered pragmas rot.

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
python3 checks/index-eval/prefilter.py src/orders/ src/ui/    # explicit groups only
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

### `coverage-check.py`
**Intent:** recount a **table** against the **enumerated list it claims to cover**, inside the
same document. The failure it exists for is silent by nature: the table is well-formed, the list
is well-formed, every other check passes, and one item sits in no row — so the closure gets
signed on the table's authority ("all N handled") because recounting by hand is the step a
reader skips. Motivating incident: 17 findings, 5 batches cut by source file, one finding living
outside every cited file; caught by a human question, by no script.

**Declarative, never inferred.** Guessing which table covers which list would fire on tables
claiming nothing, and a check that cries wrongly gets ignored — worse than no check. The document
declares its own sets; the script is silent wherever the markers are absent. A marker **quoted as code** — inside backticks or a fenced block — is a citation, not a declaration, so a document explaining the mechanism never triggers it (found the day the check fired on `checks/README.md`).

| Marker | Where | Effect |
|---|---|---|
| `<!-- coverage-set: <name>[; pattern: <regex>] -->` | before the enumerated list | opens the source set; ids captured from the following lines until the next `coverage-set`. Default pattern = numbered heading (`### 12. …`, `### 0 bis. …`) |
| `<!-- coverage-check: <name>; column: <header> -->` | before the table | the NEXT markdown table covers that set; the column is found by its header label, cells split on `,` `;` `/` |
| `<!-- coverage-exempt: <name>; ids: <a, b>[; reason: …] -->` | anywhere in the file | items deliberately out of scope — silences the finding, reported separately in `--json`, never conflated with covered |

The table is parsed **as a table**, not scanned as text: an id sitting in the Subject column must
not count as coverage, or the gap being looked for is exactly what gets hidden.

| Rule | Severity | What it proves |
|---|---|---|
| `R-COVERAGE-GAP` | blocking | an item of the set is in no row and not exempt — both sets are declared, the arithmetic is closed, it cannot be a false positive |
| `R-COVERAGE-UNKNOWN` | to-confirm | a row cites an id absent from the set (typo, stale row, or an id the list names differently) |
| `R-COVERAGE-DECL` | to-confirm | a marker that does nothing — unknown set name, no table below, missing/unknown column, unreadable pattern, set covered by nothing. A guard the reader believes is standing |

| Parameter | Effect | Default |
|---|---|---|
| `<path…>` | files or folders to scan (`.md` only) | — |
| `--diff` / `--staged` | what changed / what is about to be committed | — |
| `--json` | findings **plus the parsed sets** (`items`, `rows`, `covered`, `missing`, `exempt`, `unknown`) | text report |

**Exit codes:** `0` clean · `1` only TO-CONFIRM · `2` at least one BLOCKING.
**Why `--json` returns the sets and not just a verdict:** the question after "is anything
missing?" is always "what covers what?" — asked by a human, by an agent planning the next batch,
or by another tool. A check that prints only a verdict forces its caller to re-parse the document
it just parsed. Regression suite: `checks/tests/test_coverage_check.py`, including a replay of the
founding incident (must fail on the document as it stood before the gap was caught, pass after).

```bash
python3 checks/coverage-check.py docs/
python3 checks/coverage-check.py --diff --staged
python3 checks/coverage-check.py docs/ --json
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
`check_index_concordance(index_path, entries_dir, id_pattern)`, `stamp_updated(path, date_str)`,
`repo_root(start)` + `stamp_targets(framework, argv, prefix, match)` (the shared `--stamp`
selector, see below), `load_checks_config(root)` + `cfg_get(cfg, path, default)` (the global
settings file loader — absent file = defaults, broken file = an error the caller surfaces as
`CFG-INVALID`).

**`stamp_targets` — why the three `--stamp` commands share one selector.** They differ only by
`(prefix, match)`; everything else was copied three times, and the copy carried a defect none of
the three could see alone. `git diff --cached --name-only` prints **repo-relative** paths, so a
`startswith("backlog/")` filter applied with `cwd=<framework>` **can never match when the
framework is nested** in a host subdirectory — the selector returned nothing, the caller printed
`0 stamped` and exited `0`. A false green, structurally invisible in this repo, where the
framework sits at the root. `stamp_targets` resolves the repo root (`repo_root`, the same
`git rev-parse --show-toplevel` that made `doc-refs-check.py` immune), filters in repo space and
returns **framework-relative** paths for both selectors. It also accepts explicit paths in
framework-relative, repo-relative or absolute form, and returns what it could NOT resolve so the
caller names it on stderr — *a stamp that cannot select its target must never look like a stamp
that found none*. Regression suite: `checks/tests/test_stamp_targets.py`, every case run twice
(framework at the root **and** nested), since a flat-only test passes against the broken code.

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
script calls `entrylib` with the `"memory"` channel and aggregates; its local rules are
the channel's two size signals (to-confirm, never blocking): `M-GRAN` — an entry whose
body exceeds `sizes.memory-entry-max-lines` useful lines (default 40, global settings
file) is flagged as detail to move into the durable doc, keeping the entry as a pointer
— the Memory-channel mirror of `FM-GRAN`; and `M-INDEX-LEN` — a `MEMORY.md` entry
(bullet + wrapped lines, `[…]` tokens excluded) over
`sizes.memory-index-entry-max-words` words (default 60): the index line is a one-line
pointer, the detail lives in `memory/<slug>.md`. An
**absent or empty channel is said explicitly** (text mode), same convention as
`feature-map-check.py` — never a bare 0-finding report on a channel the check couldn't see.

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
| `--stamp [files…]` | **writes** `updated: <today>` on the cited `memory/*.md` files | paths framework-relative, repo-relative or absolute; an unresolved one is named on stderr |
| `--stamp --staged` | same effect, but scope = `memory/*.md` files **staged** in git, and **re-stages** after writing | to be wired at pre-commit |

**Exit codes:** `0` clean · `1` only "to-confirm" · `2` at least one blocking.

```bash
python3 checks/memory-check.py
python3 checks/memory-check.py --json
python3 checks/memory-check.py --stamp --staged   # pre-commit only
```

### `capture-policy-check.py`
**Intent:** deterministic half of the **capture policy** (`knowledge-capture.md §Capture
policy`) — turns the per-channel policy declared in `capture-policy.json` <!-- template -->
(schema: `capture-policy.example.json`; absent = the project has not opted in, exit 0) into
verifiable state invariants. In a channel whose level is `off` or `propose`, **only ratified
entries may exist**: any `confidence: unverified` entry, or `verified` one with no `ratified`
trace, is a BLOCKING `CP-UNRATIFIED` (surfaced by the SessionStart sweep at the next session).
A `draft` channel produces no findings — visibility there is the ratification inbox's job
(`memory-audit --pending`), no double signal. `CP-BAD-LEVEL` / `CP-BAD-CHANNEL` (blocking)
reject typos in the policy file itself. The write-time half is `hooks/normative-write-guard.py`
(below).

| Parameter | Effect | Default |
|---|---|---|
| *(none)* | text report | — |
| `--json` | JSON output | disabled |

**Exit codes:** `0` clean or not opted in · `1` only to-confirm · `2` at least one blocking (or unreadable policy JSON).

```bash
python3 checks/capture-policy-check.py
```

### `decisions-audit.py`
**Intent:** orchestrator for the **decisions journal** — checks nothing itself, chains/aggregates
the 4 scripts above (launched **concurrently**, collected in order: wall time = the slowest
child, not the sum) and drives the Tier 1 → Tier 2 cycle. Renamed from `memory-audit.py`: its
real scope is the decisions journal, not the whole memory — see `memory-audit.py` below
for the multi-channel orchestrator. Four mutually exclusive modes (priority order:
`--report` > `--merge` > `--plan` > `--tier1` > *default = both*).

| Parameter | Effect | Default |
|---|---|---|
| `--tier1` | chains `decisions-check`, `backlog-check`, `doc-refs-check`, `index-check`, prints an aggregated verdict | — |
| `--plan` | splits `decisions/INDEX.md` into balanced batches (offset/limit), one batch per reviewer | — |
| `--stale-first` | (`--plan` only) prioritizes batch ORDER by oldest frontmatter `updated` — each batch's offset/limit stays a contiguous range of lines | disabled |
| `--merge <files…>` | aggregates Tier 2 agent outputs, **coverage check** (each decision audited exactly 1×) | — |
| `--report [dir]` | writes a **deterministic report** (no LLM) — tier 1 + **per-channel volume** (decision INDEX count, `features/` and `memory/` entry counts) + a probe of the **ratification inbox** (`memory-audit.py --pending`); recommends a semantic audit on blocking drift, a channel past its `audit.volume-alert` threshold (defaults 285/150/150), or an inbox too large (`audit.pending-alert-count`, 5) or too stale (`audit.pending-alert-days`, 30d). Meant for a headless OS cron | folder: `$YAMS_MEMORY_REPORT_DIR` or `.memory-reports/` |
| `--batch-size <n>` | batch size for `--plan`; an explicit flag wins over the settings file | `audit.batch-size` (33) |
| `--index <path>` | path to the decisions journal | `decisions/INDEX.md` |
| `--json` | JSON output (`--plan` only) | disabled |
| *(none)* | equivalent to `--tier1` then `--plan` | — |

**Exit codes:** `--tier1` → the worst exit code among the 4 underlying scripts (`0`/`1`/`2`) · `--plan`/`--report` → `0` (never blocking, they produce an artifact — except a broken global settings file: blocking `CFG-INVALID`, exit 2) · `--merge` → `0` full coverage, `1` a decision unaudited or audited twice.

```bash
python3 checks/decisions-audit.py                              # tier1 + plan, common usage
python3 checks/decisions-audit.py --plan --stale-first --batch-size 20
python3 checks/decisions-audit.py --merge batch1_output.txt batch2_output.txt
python3 checks/decisions-audit.py --report                      # OS cron, headless
```

### `memory-audit.py`
**Intent:** **multi-channel** orchestrator (Feature + Decision + Memory, `WORKFLOW.md §The
three memories`) — chains `feature-map-check.py`, `decisions-audit.py --tier1` (which
already covers decisions/doc/index/backlog), `memory-check.py` and `capture-policy-check.py`
(all launched **concurrently**, collected in channel order — wall time = the slowest child),
summarizes per channel. No
`--plan`/`--merge`/`--report` of its own: only the Decision channel accumulates enough to
justify splitting into batches — delegated to `decisions-audit.py`. Feature and Memory are reread
in one single pass (small by construction).

| Parameter | Effect | Default |
|---|---|---|
| `--tier1` | chains the 4 tier-1 lines (feature, decisions, memory, capture-policy), prints one verdict each | — |
| `--pending` | the **ratification inbox**: scans `memory/`, `features/`, `decisions/`, `backlog/<id>/STATE.md` directly (`entrylib.parse_frontmatter`) and lists every entry awaiting a human in one view — **PENDING RATIFICATION** (`confidence: unverified`, oldest `updated` first) and **RATIFICATION NOT TRACKED** (`verified` with no `ratified` field). Entries pending longer than `audit.pending-stale-days` (30d, global settings file) get a `⚠ stale Nd` marker and are counted in the summary. Files with no frontmatter/`confidence` are skipped, never errored on. | — |
| `--json` | JSON output (with `--pending`: flat list of `channel/path/updated/source/kind/age_days/stale`) | disabled |
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
The default no-args watch list (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`,
`.github/copilot-instructions.md`) can be **extended — never reduced** — via <!-- template -->
`guards.extra-watched-files` (global settings file); any config problem (missing, broken,
wrong types) means built-ins only: a guard never crashes or blocks on a bad config.

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
messaging, payment…). The path allowlist can be **extended — never reduced** — via
`guards.extra-secret-allowlist-paths` (global settings file, one regex per entry); an entry
that fails to compile is skipped with a stderr note, and any config problem means built-ins
only — same fail-closed discipline as `poisoning-scan.py`.

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

### `normative-write-guard.py`
**Intent:** harness-level half of the **capture policy** — turns an AI write to a NORMATIVE
path (`capture-policy.json`'s `normative-paths` — instruction files, rules) into an explicit <!-- template -->
human confirmation instead of a silent auto-approval. Complements the deterministic check
(state, post-hoc) with **prevention at write time**; same "ask, never hard-block" philosophy
as `destructive-guard.py`. Portable (stdlib only).

| Parameter | Effect | Default |
|---|---|---|
| `--stdin-json` | Claude Code adapter: on `Write`/`Edit` whose `file_path` matches a normative prefix → emits a `permissionDecision: "ask"` JSON on stdout, exit 0 | disabled |
| `--path <p>` | non-interactive test: exit `2` if `<p>` is normative (git/CI), `0` otherwise | — |

**Exit codes:** `--stdin-json` → always `0` (the "ask" JSON is the decision carrier) ·
`--path` → `2` normative, `0` otherwise. Without a readable `capture-policy.json` carrying <!-- template -->
a non-empty `normative-paths`, the guard is INACTIVE — silent `0` in every mode. Wired into
`adapters/claude-code/hooks/security-guards.sh` on `PreToolUse(Write|Edit)`, after
poisoning-scan and secret-scan.

```bash
python3 hooks/normative-write-guard.py --path CLAUDE.md      # exit 2 if normative
echo '{"tool_name":"Write","tool_input":{"file_path":"CLAUDE.md","content":"…"}}' | python3 hooks/normative-write-guard.py --stdin-json
```

## The framework's own tests

### `run-tests.py` (repo root)
**Intent:** **single entry point for the framework's own test suites** — not a check, and
nothing an adopting project needs (`INSTALL.md §Steps` leaves the test harnesses behind).
Runs the three `unittest` suites plus `entrylib.py --selftest`, prints one line per suite
with its test count, and exits ≠ 0 if any suite fails **or collects nothing**.

Its reason to exist is a discovery trap: the suites have **no common importable root**.
`checks/index-eval/tests/` does `from lib.scorer import …` and resolves only under
`-t checks/index-eval`; `checks/tests/` and `hooks/tests/` load their targets by path and
need `-t <their own dir>` (neither carries an `__init__.py`). So a plain
`python3 -m unittest discover` from the root prints **`Ran 0 tests … OK`** — a silent zero
that is indistinguishable from a green run — and a per-suite discovery that forgets `-t`
drops a whole suite just as quietly. Both under-report coverage while looking healthy. The
runner turns each into an explicit failure.

| Parameter | Effect | Default |
|---|---|---|
| `-v` / `--verbose` | per-test output for every suite | summary only (failing suites always print in full) |

**Exit codes:** `0` every suite green · `1` at least one failed or collected 0 tests.

```bash
python3 run-tests.py         # 95 unit tests / 3 suites + 1 embedded selftest
python3 run-tests.py -v
```

Suites run: `checks/tests/` (doc-refs, decisions) · `hooks/tests/` (memory-graph) ·
`checks/index-eval/tests/` (scorer, lexsim, parse, guard, prefilter, reporter, sufficiency) ·
`checks/entrylib.py --selftest` (the shared validator, one case per rule). Discovery runs
under `-W error::ResourceWarning`, so a file handle left unclosed in a script under test
fails the run rather than printing a warning nobody reads.

## What does NOT belong here

The **tech-specific** scripts of the host project (lint, tests, analyzers…) are not part of this
framework — they stay documented by the project itself. This file only references what
**YAMS** provides. To write one on the project side (like a host project's own
`audit.py`): `checks/TEMPLATE.md` gives the common shape, not the tech-specific content.

> **Watch for homonyms**: a project adopting YAMS may already have its own `manifest.py` /
> `doc-audit.py` scripts (or equivalents), richer and wired to its actual tree — don't confuse
> them with the ones provided here. **This framework's** `index/manifest.py`
> is a distinct script, generalized over `index-config.json` — it has no `check`
> command (delegated to `checks/index-check.py`) nor a dedicated filter (covered by
> `roots`/`extensions`/`ignore` in the config).
