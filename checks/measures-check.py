#!/usr/bin/env python3
"""Measured numbers — flags a number in the docs that no longer matches what it measures.

A number copied from the repo into a doc (a class size, a count of assets, a number of keys)
ages in silence: the code moves, the number stays, and every reader after that trusts a stale
figure. Measured on the reference project: of 13 doc↔code drifts surfaced by one audit, 8 were
such numbers. This check makes them verifiable. The number carries, right after it on the same
line, a marker naming the measure that produces it:

    `Scorer.cs` is 607 lines of code <!-- measure: class-size:src/Scorer.cs -->

The check reads the LAST number before the marker, recomputes the measure, and reports the
gap. The marker is an HTML comment: a reader sees only the number.

What carries NO marker, deliberately: a dated measurement that cannot be reproduced ("measured
in play on …") and a DESIGN value ("reference dose: 2 × 3 turns"). Those are facts or choices,
not copies of the repo — the marker is for numbers the repo can recompute.

The MEASURES are the project's, never the framework's: counting a project's assets or sizing
its classes is tech-specific (`checks/README.md §The project brings its OWN`). The project
declares a Python module in `checks-config.json`:

    "measures": { "module": "tools/measures.py" }     # resolved from the REPO root

That module exports `MEASURES = {"name": fn}`, each `fn(argument: str) -> number`; a marker
`<!-- measure: name:argument -->` calls `MEASURES["name"]("argument")`. The measure is reviewed
code, never a command read from a doc. The first line of each function's docstring is what
`--list` prints. Without the key, there is nothing to measure → one-line message, exit 0 (the
framework repo itself declares none, so the check is inactive on itself by construction).

Rule table:

| Rule              | Severity      | Proves |
|-------------------|---------------|--------|
| `MS-UNKNOWN`      | BLOCKING-AUTO | the marker names a measure the module does not declare — a typo or a removed measure; the number is checked by nothing. |
| `MS-NO-NUMBER`    | BLOCKING-AUTO | a marker with no number before it on its line — it measures nothing. |
| `MS-STALE`        | TO-CONFIRM    | the number differs from the measure. TO-CONFIRM, not blocking: the code moving is normal and must not block an unrelated commit — the doc is due a recount, the human decides whether the new number changes what the doc concludes. |
| `MS-UNMEASURABLE` | TO-CONFIRM    | the measure raised (its target is gone, or its argument is wrong) — the doc likely cites something dead. |
| `CFG-INVALID`     | BLOCKING-AUTO | `measures.module` is set but missing, unloadable, or exports no `MEASURES` dict. |

A marker QUOTED AS CODE — inside a fenced block or a backtick span — documents the mechanism and
declares nothing: it is skipped. Without that, the doc describing the marker would be the check's
first false positive (the lesson `coverage-check.py` learned the same way).

Follows `checks/TEMPLATE.md`: 5-field `Finding`, two verdicts, `collect()`, 0/1/2 exit code.
Read-only. Fixes nothing — flags.

Usage:
  python3 checks/measures-check.py                 # every .md under the framework root
  python3 checks/measures-check.py <file.md|dir>…  # explicit targets
  python3 checks/measures-check.py --diff | --staged
  python3 checks/measures-check.py --value <name[:arg]>   # the current value, to write it
  python3 checks/measures-check.py --list                 # the declared measures
  python3 checks/measures-check.py --json
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import namedtuple

# Windows consoles default to cp1252: non-cp1252 output (→, ⨯…) would crash print().
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entrylib  # noqa: E402

BLOCKING = entrylib.BLOCKING
TO_CONFIRM = entrylib.TO_CONFIRM
Finding = namedtuple("Finding", "severity rule path line msg")

FRAMEWORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # framework root
MARKER = re.compile(r"<!--\s*measure:\s*([^\s>]+)\s*-->")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1")


# --------------------------------------------------------------------------- #
# The project's measures                                                      #
# --------------------------------------------------------------------------- #

def load_measures(cfg: dict, repo: str):
    """Returns `(measures, error)`: `(None, None)` when the project declares no module
    (inactive), `({}, "message")` when it declares one that cannot serve — the caller
    surfaces that as a BLOCKING `CFG-INVALID`, never a silent no-op."""
    rel = entrylib.cfg_get(cfg, ("measures", "module"), "")
    if not rel:
        return None, None
    path = os.path.join(repo, rel)
    if not os.path.isfile(path):
        return {}, f"measures.module: {rel} not found (resolved from the repo root)"
    try:
        spec = importlib.util.spec_from_file_location("project_measures", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:  # the project's code: any failure is a config failure
        return {}, f"measures.module: {rel} failed to load ({type(e).__name__}: {e})"
    measures = getattr(mod, "MEASURES", None)
    if not isinstance(measures, dict) or not all(callable(f) for f in measures.values()):
        return {}, f"measures.module: {rel} must export MEASURES = {{name: callable}}"
    return measures, None


class UnknownMeasure(Exception):
    """The marker names a measure the module does not declare — distinct from any error the
    measure itself raises (a `KeyError` inside a measure is a vanished target, not a typo)."""


def measure(measures: dict, spec: str):
    name, _, arg = spec.partition(":")
    if name not in measures:
        raise UnknownMeasure(name)
    return measures[name](arg)


def same(doc: str, value) -> bool:
    try:
        return float(doc.replace(",", ".")) == float(value)
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------- #
# Rule                                                                        #
# --------------------------------------------------------------------------- #

def declared(lines: list):
    """Yields `(line_no, spec, numbers_before)` for every DECLARED marker — not inside a fence,
    not quoted in a backtick span (a marker quoted as code documents the mechanism)."""
    fenced = False
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        quoted = [c.span() for c in CODE_SPAN.finditer(line)]
        start = 0
        for m in MARKER.finditer(line):
            if any(a <= m.start() < b for a, b in quoted):
                continue
            yield i, m.group(1), NUMBER.findall(line[start:m.start()])
            start = m.end()


def rule_markers(path: str, lines: list, measures: dict) -> list:
    """Every declared marker of the file, checked against its measure. Pure apart from the
    measures, which are the project's own read-only functions."""
    out = []
    for i, spec, before in declared(lines):
        if not before:
            out.append(Finding(BLOCKING, "MS-NO-NUMBER", path, i,
                               f"marker `{spec}` has no number before it on its line"))
            continue
        doc = before[-1]
        try:
            value = measure(measures, spec)
        except UnknownMeasure as e:
            out.append(Finding(BLOCKING, "MS-UNKNOWN", path, i,
                               f"no measure named `{e.args[0]}` (see --list)"))
            continue
        except Exception as e:
            out.append(Finding(TO_CONFIRM, "MS-UNMEASURABLE", path, i,
                               f"`{spec}` could not be measured ({type(e).__name__}: {e})"))
            continue
        if not same(doc, value):
            out.append(Finding(TO_CONFIRM, "MS-STALE", path, i,
                               f"the doc says {doc}, `{spec}` measures {value}"))
    return out


# --------------------------------------------------------------------------- #
# Targets                                                                     #
# --------------------------------------------------------------------------- #

def git_names(repo: str, staged: bool) -> list:
    args = ["git", "diff", "--name-only", "--diff-filter=ACMR"] + (["--cached"] if staged else [])
    out = subprocess.run(args, cwd=repo, env=entrylib.git_env(), capture_output=True,
                         text=True, encoding="utf-8", errors="replace").stdout
    return [os.path.join(repo, p) for p in out.split()]


def walk(d: str) -> list:
    out = []
    for base, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if not x.startswith(".") or x == ".claude"]
        out += [os.path.join(base, f) for f in files]
    return out


def collect(targets: list, diff: bool, staged: bool, repo: str) -> list:
    raw = []
    if diff:
        raw += git_names(repo, staged=False)
    if staged:
        raw += git_names(repo, staged=True)
    for t in targets:
        raw += walk(t) if os.path.isdir(t) else [t]
    seen, out = set(), []
    for p in raw:
        a = os.path.realpath(p)
        if a.endswith(".md") and os.path.isfile(a) and a not in seen:
            seen.add(a)
            out.append(a)
    return out


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

def main(argv) -> int:
    as_json = "--json" in argv
    diff = "--diff" in argv
    staged = "--staged" in argv
    repo = entrylib.repo_root(FRAMEWORK)
    cfg, cfg_err = entrylib.load_checks_config(FRAMEWORK)
    if cfg_err:
        print(f"BLOCKING-AUTO  {entrylib.CHECKS_CONFIG_NAME}:0  CFG-INVALID  {cfg_err}")
        return 2
    measures, err = load_measures(cfg, repo)
    if err:
        print(f"BLOCKING-AUTO  {entrylib.CHECKS_CONFIG_NAME}:0  CFG-INVALID  {err}")
        return 2
    if measures is None:
        print("measures-check: no `measures.module` in checks-config.json — nothing to measure.")
        return 0

    if "--list" in argv:
        for name, fn in sorted(measures.items()):
            doc = (fn.__doc__ or "").strip().splitlines()
            print(f"{name:20} {doc[0] if doc else ''}")
        return 0
    if "--value" in argv:
        i = argv.index("--value")
        if i + 1 >= len(argv):
            print("usage: measures-check.py --value <name[:arg]>", file=sys.stderr)
            return 2
        try:
            print(measure(measures, argv[i + 1]))
        except UnknownMeasure as e:
            print(f"no measure named `{e.args[0]}` (see --list)", file=sys.stderr)
            return 2
        return 0

    targets = [a for a in argv if not a.startswith("--")]
    if not (targets or diff or staged):
        targets = [FRAMEWORK]
    findings = []
    files = collect(targets, diff, staged, repo)
    n_markers = 0
    for path in files:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
        rel = os.path.relpath(path, repo).replace(os.sep, "/")
        n_markers += sum(1 for _ in declared(lines))
        findings += rule_markers(rel, lines, measures)

    bloq = [f for f in findings if f.severity == BLOCKING]
    conf = [f for f in findings if f.severity == TO_CONFIRM]
    if as_json:
        print(json.dumps([f._asdict() for f in findings], ensure_ascii=False, indent=2))
    elif findings:
        for f in sorted(findings, key=lambda f: (f.severity != BLOCKING, f.path, f.line)):
            print(f"{f.severity:14} {f.path}:{f.line}  {f.rule}  {f.msg}")
        print(f"\n— {len(findings)} finding(s): {len(bloq)} blocking-auto, {len(conf)} to-confirm")
    elif n_markers:
        print(f"measures-check: OK — {n_markers} marked number(s) recomputed in {len(files)} file(s).")
    else:
        # A check that read nothing must not answer like one that verified everything:
        # an absent path or an empty folder lands here, never on the OK line above.
        print(f"measures-check: no marked number in scope ({len(files)} .md file(s) read) — nothing verified.")
    return 2 if bloq else (1 if conf else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
