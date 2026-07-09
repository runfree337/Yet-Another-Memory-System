#!/usr/bin/env python3
"""Deterministic check of the "Decision" channel (zero false positive).

The Decision channel is an instance of `ENTRY-TEMPLATE.md` (cf. `decisions/README.md`): a
common frontmatter (`entrylib.CHANNELS["decision"]`) above three prose sections
(Decision/Why/Invariant), one `INDEX.md` line per file, revocation/archival = a `status`
transition + `replaces`/`replaced-by` links. This script verifies the SEVEN mechanical
invariants — fixes NOTHING, **flags**.

Rules (stable ids — API, do not rename):
  D1  Every `D-YYYY-MM-DD-NN.md` file has a `D-YYYY-MM-DD-NN` line in INDEX.md.
  D2  Every `D-…` id cited in INDEX.md has a `D-….md` file.
  D3  Complete, valid frontmatter for the "decision" channel (via `entrylib.validate_entry`,
      rules surfaced as-is: R-NO-FRONTMATTER, R-MISSING-KEY, R-BAD-VALUE,
      R-EXT-NO-CONF, R-UNVERIFIED, R-VERIFIED-NOT-RATIFIED, R-BAD-DATE).
  D4  The three canonical sections (**Decision**, **Why**, **Invariant**) are present in
      the body.
  D5  `status` <=> INDEX.md section: an `archived` entry referenced under "## Active", or
      an `active` entry referenced under "## Archived", is blocking (`revoked` is not
      constrained — both sections are legitimate per `decisions/README.md §4-5`).
  D6  Sound revocation graph: `replaced-by`/`replaces` point to existing ids,
      reciprocity (`A.replaced-by = B` => `B.replaces` contains `A`), no cycle.
  D7  Cross-channel references (`links:`) resolved, via `entrylib.check_links` (rule
      surfaced as-is: R-DEAD-LINK).

Exit code (`checks/TEMPLATE.md`): 2 if >=1 blocking, 1 if only to-confirm, 0 otherwise.

Usage:
  python3 checks/decisions-check.py
  python3 checks/decisions-check.py --json
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entrylib
from entrylib import BLOCKING, TO_CONFIRM, Finding

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # …/ai-workflow
DEC = os.path.join(ROOT, "decisions")
INDEX = os.path.join(DEC, "INDEX.md")

ID_RE = re.compile(r"D-\d{4}-\d{2}-\d{2}-\d{2}")
CANONICAL_HEADINGS = ("**Decision**", "**Why**", "**Invariant**")


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT)


def _decision_files() -> dict:
    """`{id: file_name}` for every `D-YYYY-MM-DD-NN.md` under `decisions/`."""
    files = {}
    if not os.path.isdir(DEC):
        return files
    for fname in sorted(os.listdir(DEC)):
        if not fname.endswith(".md"):
            continue
        m = ID_RE.fullmatch(fname[: -len(".md")])
        if m:
            files[m.group(0)] = fname
    return files


def _as_list(v) -> list:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return list(v)


# --------------------------------------------------------------------------- #
# D1 / D2 — file <-> index concordance, via entrylib (direct mapping).        #
# --------------------------------------------------------------------------- #

def rule_d1_d2() -> list:
    """`entrylib.check_index_concordance` scans the index with `pat.finditer(line)` — the
    new index line `- [<id>](<id>.md) — …` repeats the id twice (link text + path), so a
    single `D2` drift can come out twice for one line. Deduplicated by
    `(rule, path, line, msg)` — the same drift must only be reported once. Also
    relativizes the absolute paths embedded in the message (built by `entrylib` from the
    paths passed in, here absolute)."""
    if not os.path.isdir(DEC):
        return []
    raw = entrylib.check_index_concordance(INDEX, DEC, ID_RE)
    renamed = {"R-ORPHAN-FILE": "D1", "R-DEAD-INDEX": "D2"}

    seen = set()
    findings = []
    for f in raw:
        rule = renamed.get(f.rule, f.rule)
        path = rel(f.path)
        msg = f.msg.replace(ROOT + os.sep, "").replace(ROOT, ".")
        key = (rule, path, f.line, msg)
        if key in seen:
            continue
        seen.add(key)
        findings.append(Finding(f.severity, rule, path, f.line, msg))
    return findings


# --------------------------------------------------------------------------- #
# D4 — canonical sections present in the body.                                #
# --------------------------------------------------------------------------- #

def rule_d4(path: str, body: str) -> list:
    missing = [h for h in CANONICAL_HEADINGS if h not in body]
    if not missing:
        return []
    return [Finding(BLOCKING, "D4", path, 1,
                     f"missing canonical section(s) in the body: {', '.join(missing)}")]


# --------------------------------------------------------------------------- #
# D5 — status <-> INDEX.md section.                                           #
# --------------------------------------------------------------------------- #

def _index_sections() -> tuple:
    """`(ids under ## Active, ids under ## Archived)` — splits INDEX.md at the first
    `## Archiv...` line. Everything before = Active, everything after (inclusive) =
    Archived."""
    if not os.path.isfile(INDEX):
        return set(), set()
    text = open(INDEX, encoding="utf-8").read()
    m = re.search(r"(?m)^##\s*Archiv", text)
    actives_text, archived_text = (text[: m.start()], text[m.start():]) if m else (text, "")
    return set(ID_RE.findall(actives_text)), set(ID_RE.findall(archived_text))


def rule_d5(idv: str, path: str, meta: dict, actives_ids: set, archived_ids: set) -> list:
    status = meta.get("status")
    if not idv or not status:
        return []  # frontmatter already reported by D3
    findings = []
    if status == "archived" and idv in actives_ids:
        findings.append(Finding(BLOCKING, "D5", path, 1,
                                 f"status: archived but « {idv} » is referenced under « ## Active » "
                                 f"of {rel(INDEX)}"))
    if status == "active" and idv in archived_ids:
        findings.append(Finding(BLOCKING, "D5", path, 1,
                                 f"status: active but « {idv} » is referenced under « ## Archived » "
                                 f"of {rel(INDEX)}"))
    return findings


# --------------------------------------------------------------------------- #
# D6 — revocation graph: existing targets, reciprocity, no cycle.             #
# --------------------------------------------------------------------------- #

def rule_d6(by_id: dict) -> list:
    """`by_id`: `{id: (path, meta)}`. Pure rule over the whole graph (cross-file scope,
    can't be expressed per-file like D4/D5)."""
    findings = []

    for idv, (path, meta) in sorted(by_id.items()):
        rb = meta.get("replaced-by")
        if isinstance(rb, list):
            # A malformed entry must be FLAGGED, never crash the check (a list is
            # unhashable — it would blow up the by_id lookups below).
            findings.append(Finding(BLOCKING, "D6", path, 1,
                                     f"replaced-by must be a single id, got a list "
                                     f"({', '.join(map(str, rb))}) — chain revocations instead"))
            rb = None
        if rb:
            if rb not in by_id:
                findings.append(Finding(BLOCKING, "D6", path, 1,
                                         f"replaced-by: « {rb} » — no decisions/{rb}.md file"))
            else:
                target_replaces = _as_list(by_id[rb][1].get("replaces"))
                if idv not in target_replaces:
                    findings.append(Finding(BLOCKING, "D6", path, 1,
                                             f"replaced-by: « {rb} » with no reciprocal — "
                                             f"{rb}.replaces does not contain « {idv} »"))
        for r in _as_list(meta.get("replaces")):
            if r not in by_id:
                findings.append(Finding(BLOCKING, "D6", path, 1,
                                         f"replaces: « {r} » — no decisions/{r}.md file"))

    # Cycles on the replaced-by graph (iterative DFS, one finding per distinct cycle).
    reported = set()
    for start in by_id:
        chain = []
        cur = start
        while isinstance(cur, str) and cur in by_id:
            if cur in chain:
                cycle = tuple(sorted(chain[chain.index(cur):]))
                if cycle not in reported:
                    reported.add(cycle)
                    anchor = by_id[cycle[0]][0]
                    findings.append(Finding(BLOCKING, "D6", anchor, 1,
                                             f"cycle detected in the replaced-by graph: "
                                             f"{' → '.join(cycle)}"))
                break
            chain.append(cur)
            cur = by_id[cur][1].get("replaced-by")

    return findings


# --------------------------------------------------------------------------- #
# Orchestration.                                                              #
# --------------------------------------------------------------------------- #

def audit() -> list:
    findings = list(rule_d1_d2())

    files = _decision_files()
    by_id = {}
    loaded = []  # (path, meta, body) in discovery order
    for idv, fname in files.items():
        fpath = os.path.join(DEC, fname)
        text = open(fpath, encoding="utf-8").read()
        meta, body, err = entrylib.parse_frontmatter(text)
        loaded.append((fpath, meta, body))
        if meta.get("id"):
            by_id[meta.get("id")] = (rel(fpath), meta)

    actives_ids, archived_ids = _index_sections()

    for fpath, meta, body in loaded:
        p = rel(fpath)
        # D3 — complete, valid frontmatter (findings surfaced as-is).
        findings += entrylib.validate_entry(p, meta, "decision")
        # D4 — canonical sections.
        findings += rule_d4(p, body)
        # D5 — status <-> INDEX section.
        findings += rule_d5(meta.get("id"), p, meta, actives_ids, archived_ids)
        # D7 — cross-channel references (findings surfaced as-is).
        findings += entrylib.check_links(p, meta, ROOT)

    # D6 — revocation graph, cross-file scope.
    findings += rule_d6(by_id)

    return findings


def main(argv) -> int:
    as_json = "--json" in argv

    if not os.path.isdir(DEC):
        if as_json:
            print(json.dumps([], ensure_ascii=False))
        else:
            print("decisions-check: no decisions/ folder — nothing to verify.")
        return 0

    findings = audit()
    bloq = [f for f in findings if f.severity == BLOCKING]
    conf = [f for f in findings if f.severity == TO_CONFIRM]

    if as_json:
        print(json.dumps([f._asdict() for f in findings], ensure_ascii=False, indent=2))
    else:
        for f in sorted(findings, key=lambda f: (f.severity != BLOCKING, f.path, f.line, f.rule)):
            print(f"{f.severity:14} {f.path}:{f.line}  {f.rule}  {f.msg}")
        if findings:
            print(f"\n— {len(findings)} finding(s): {len(bloq)} blocking-auto, {len(conf)} to-confirm")
        else:
            print("decisions-check: OK.")

    return 2 if bloq else (1 if conf else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
