# Template for a deterministic check — how to write a new one

> **Who this is for.** This file does **not** provide a script — it's the **pattern** that every
> mechanical, zero-false-positive check in this framework follows, to be reused when **the host
> project** writes its own tech-specific linter (its own: lint, code standards, analyzers — out
> of the framework's scope, see `checks/README.md §The project brings its OWN`), or when this
> framework itself gains a new agnostic check.
>
> **Provenance:** extracted by observation from the real code of two linters of the original
> project YAMS was extracted from — a C#/Unity code-standards linter (named `audit.py` on the
> project side) and a doc-freshness linter (named `doc-audit.py` on the project side) — that
> independently converged on the same shape. Inferred by the AI, not yet ratified by a human as
> a team rule; recoup it before treating it as an established fact (the original project isn't
> embedded in this repo — those two scripts aren't available to consult here).

## Why a template

Every check in this folder (and the host project's tech-specific linters) answers the same
question: *"is this drift proven, or only probable?"* — and should always answer with the
**same shape**, so any tool (hook, CI, human) can wire any check without learning one
convention per script. Writing a new check without starting from this template means
manually reproducing a choice already settled twice in identical fashion in the reference project.

## The 5 pieces

### 1. Two verdict levels, never more

```python
BLOCKING = "BLOCKING-AUTO"   # zero false positive PROVEN on the repo — firm verdict
CONFIRM = "TO-CONFIRM"       # location pre-filter — the agent or the human decides
```

`BLOCKING-AUTO`: the rule **cannot** be wrong (e.g. a cited path that existed then vanished —
git history proves it). `TO-CONFIRM`: the rule **spots a plausible candidate** but can't rule
out the false positive on its own (e.g. a path never created — could be a typo, could be a
legitimate planned one). Never invent a third level: the script **finds**, it doesn't judge —
fine-grained judgment is tier 2's job (agent/review).

### 2. The `Finding`, a minimal struct

```python
from collections import namedtuple
Finding = namedtuple("Finding", "severity rule path line msg")
```

Always these 5 fields, in this order. `rule` is a stable identifier (`R-DEAD-PATH`,
`FM1`…) — grep-able, cited in the check's docs, stable across script versions (the docs and
tests refer to it).

### 3. Rules are PURE functions

```python
def rule_xxx(path, lines, text) -> list[Finding]:
    ...
```

No side effects, no I/O beyond the reading already done. This makes them **testable in
isolation** (`tests/` can call `rule_xxx` directly without going through `main`) and
**composable** (`RULES = [rule_a, rule_b, ...]`, a simple loop chains them).

### 4. `collect()` — gathering the targets, git-aware

```python
def collect(targets, diff, staged):
    raw = []
    if diff:   raw += git_diff_names(staged=False)   # modified, unstaged
    if staged: raw += git_diff_names(staged=True)    # staged
    for t in targets:
        raw += walk(t) if os.path.isdir(t) else [t]
    return dedupe_existing_files(raw, filtered_by=EXTENSIONS_OR_SUFFIX)
```

Three ways to feed a check, **never mutually exclusive**: explicit paths,
`--diff` (what you just changed), `--staged` (what's about to be committed). Filter by
auditable extension/suffix and dedupe before auditing — a file is never audited twice even
if it comes in through two paths at once.

### 5. `main(argv)` — the same interface for all

```python
def main(argv):
    as_json = "--json" in argv
    diff = "--diff" in argv
    staged = "--staged" in argv
    targets = [a for a in argv if not a.startswith("--")]
    if not (targets or diff or staged):
        print("usage: <script>.py <path...> | --diff | --staged [--json]", file=sys.stderr)
        return 0

    findings = [f for path in collect(targets, diff, staged) for f in audit_file(path)]
    bloq = [f for f in findings if f.severity == BLOCKING]
    conf = [f for f in findings if f.severity == CONFIRM]

    if as_json:
        print(json.dumps([f._asdict() for f in findings], ensure_ascii=False, indent=2))
    else:
        for f in sorted(findings, key=lambda f: (f.severity != BLOCKING, f.path, f.line)):
            print(f"{f.severity:14} {f.path}:{f.line}  {f.rule}  {f.msg}")
        print(f"\n— {len(findings)} finding(s): {len(bloq)} blocking-auto, {len(conf)} to-confirm")

    return 2 if bloq else (1 if conf else 0)
```

**Exit code, the convention never to break** — the same across the 6 checks in this folder AND
the host project's tech-specific linters: `0` clean, `1` only TO-CONFIRM, `2` at least one
BLOCKING. This is what lets `checks/README.md §To wire` gate any check on its exit code
alone, without knowing its internal semantics.

**UTF-8 stdout, unconditionally** — Windows consoles default to cp1252; a report line
containing `→` or `⨯` would crash `print()` with `UnicodeEncodeError`. Every CLI script in
this framework carries, right after its imports:

```python
# Windows consoles default to cp1252: non-cp1252 output (→, ⨯…) would crash print().
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
```

A new check copies this block verbatim.

## What this framework already applies, or doesn't

*(The two linters cited under Provenance above aren't embedded in this repo — they served as
the starting reference to derive the template, not as a line-by-line comparison base.)*

| Script | Finding (namedtuple) | git-aware `collect` (`--diff`+`--staged`) | `--json` | Conforms to template |
|---|---|---|---|---|
| `checks/entrylib.py` (this framework) | provides `Finding`/`BLOCKING`/`CONFIRM` — not a check | n/a — shared library, no target to collect | n/a | **shape mutualization** — the 4 channel checks below import it instead of each redefining their own frontmatter parser |
| `checks/memory-check.py` (this framework) | ✅ (via `entrylib`) | n/a (always compares the index to the whole folder, same pattern as `decisions-check.py` — no subset to target) | ✅ | **conforming** — the first check written from this template, not reverse-engineered |
| `checks/decisions-check.py` (this framework) | ✅ (via `entrylib`) | n/a (same as `memory-check.py` — compares `decisions/` in full) | ✅ | **conforming** — via `entrylib` |
| `checks/feature-map-check.py` (this framework) | ✅ (via `entrylib`) | n/a (same, compares `features/` in full) | ✅ | **conforming** — via `entrylib` |
| `checks/backlog-check.py` (this framework) | ✅ (via `entrylib`) | n/a (scans `backlog/` in full) | ✅ | **conforming** — via `entrylib` |
| `checks/doc-refs-check.py` (this framework) | plain tuple | `--staged` only, no `--diff` | no | **diluted** — to be realigned if the occasion arises |
| `hooks/poisoning-scan.py`, `hooks/secret-scan.py` | plain tuple | `--staged` only | no | diluted — but short guards, simplicity wins here |

**The point is not to retroactively realign everything** — a script that works and whose
drift has never cost anything doesn't deserve a refactor for stylistic consistency alone.
This template serves the **next** check to be written (this framework or the host project): it
starts from the full shape on the first pass, rather than empirically rediscovering the same 5
pieces. `memory-check.py` is the first concrete proof of this; `decisions-check.py`, `feature-map-check.py`
and `backlog-check.py` followed suit by importing the same `entrylib.py` library rather than
each redefining their own frontmatter parser.
