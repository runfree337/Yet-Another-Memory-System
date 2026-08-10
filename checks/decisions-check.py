#!/usr/bin/env python3
"""Deterministic check of the "Decision" channel (zero false positive).

The Decision channel is an instance of `ENTRY-TEMPLATE.md` (cf. `decisions/README.md`): a
common frontmatter (`entrylib.CHANNELS["decision"]`) above three prose sections
(Decision/Why/Invariant), one `INDEX.md` line per file, revocation/archival = a `status`
transition + `replaces`/`replaced-by` links. This script verifies the mechanical
invariants — fixes NOTHING, **flags**.

Rules (stable ids — API, do not rename):
  CFG-INVALID  `checks-config.json` present at the repo root but broken (unreadable,
      malformed JSON, non-object top level) — surfaced once per run, never silently
      ignored (same convention as the sibling channel checks).
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
  D8  A decision `status: archived|revoked` is still referenced by a living entry — a
      `links:` entry in `memory/*.md`/`features/*.md`/`backlog/<id>/STATE.md`, or a
      `D-id` mention in a `features/*.md` BODY. To-confirm only (a living historical
      citation can be legitimate): update the reference or reconsider the archival.
      Other decisions (`replaces`/`replaced-by`) and `decisions/INDEX.md` don't count —
      that's the legitimate revocation record / the registry.
  D9  RETIRED — superseded by D12. It bounded the WHOLE body, mirroring `FM-GRAN`/
      `M-GRAN`, which is the right instrument for the Feature and Memory channels
      because their bodies are free prose. A decision's body is NOT free: D4 makes
      three sections mandatory and blocking. Measuring a total over a structured body
      ignores the structure we made compulsory, and the total names nothing to cut —
      measured on a real corpus, 8 flagged decisions survived three agents' worth of
      rewriting. The id is retired, never reused (`sizes.decision-entry-max-lines`
      is now inert; hosts may drop the key).
  D11 Blockquote (banner) lines > `sizes.decision-banner-max-lines` (default 20) —
      to-confirm: the amendment / "what died, what survives" notes are protocol, but a
      banner that outgrows its budget is analysis in disguise.
  D12 One canonical SECTION > `sizes.decision-section-max-lines` written lines
      (default 20) — to-confirm. Successor of the retired D9: a whole-body total names
      nothing to cut; D12 names the section, and each has its own remedy: an oversized
      `**Decision**` is doing design work, an oversized `**Why**` is the analysis that
      belongs in the durable doc it motivates. Only D4-compliant bodies are split
      (the three markers are blocking-mandatory, so the cut is exact, never guessed).
  D10 `INDEX.md` entry (bullet + its wrapped lines, `[…]` tokens excluded) >
      `sizes.decisions-index-entry-max-words` words (default 80) — to-confirm: the
      line is id + title + one-line invariant; anything more lives in the `D-….md`
      file (engine: `entrylib.check_index_entry_len`).

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

# Windows consoles default to cp1252: non-cp1252 output (→, ⨯…) would crash print().
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entrylib
from entrylib import BLOCKING, TO_CONFIRM, Finding

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # …/ai-workflow
DEC = os.path.join(ROOT, "decisions")
INDEX = os.path.join(DEC, "INDEX.md")

ID_RE = re.compile(r"D-\d{4}-\d{2}-\d{2}-\d{2}")
CANONICAL_HEADINGS = ("**Decision**", "**Why**", "**Invariant**")

# Global settings (checks-config.json, optional) — loaded once. `_CFG_ERR` is surfaced
# as a BLOCKING CFG-INVALID finding by `check_config()`, never silently ignored.
_CFG, _CFG_ERR = entrylib.load_checks_config(ROOT)
DECISION_BANNER_MAX_LINES = entrylib.cfg_get(
    _CFG, ("sizes", "decision-banner-max-lines"), 20)
DECISION_SECTION_MAX_LINES = entrylib.cfg_get(
    _CFG, ("sizes", "decision-section-max-lines"), 20)
INDEX_ENTRY_MAX_WORDS = entrylib.cfg_get(_CFG, ("sizes", "decisions-index-entry-max-words"), 80)


def check_config() -> list:
    """CFG-INVALID — `checks-config.json` present but broken. Same convention as the
    sibling channel checks: a broken config never silently falls back to defaults."""
    if _CFG_ERR:
        return [Finding(BLOCKING, "CFG-INVALID", entrylib.CHECKS_CONFIG_NAME, 1, _CFG_ERR)]
    return []


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

def _section_lines(body: str) -> list:
    """`[(marker, written-line count)]` for the three canonical sections.

    Cut on the D4 markers, which are blocking-mandatory — so the split is exact and never
    guessed. Blank lines, table separators and blockquotes are excluded — banner lines
    belong to D11, not to a section's prose budget. Returns `[]` when a marker
    is missing — D4 already reports that, and a second signal on the same cause is noise.
    """
    idx = [(body.find(m), m) for m in CANONICAL_HEADINGS]
    if any(i < 0 for i, _ in idx):
        return []
    idx.sort()
    bounds = [(idx[0][1], idx[0][0], idx[1][0]),
              (idx[1][1], idx[1][0], idx[2][0]),
              (idx[2][1], idx[2][0], len(body))]
    out = []
    for name, a, b in bounds:
        seg = entrylib.useful_body_lines(body[a:b])
        out.append((name, len([l for l in seg if not l.lstrip().startswith(">")])))
    return out


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
    Archived. Only ENTRY lines (`- [<id>](…)`) count as "referenced under" a section:
    an id merely mentioned inline (e.g. a successor cited in an archival gist, or a
    cross-reference in another entry's invariant) is not an index entry and must not
    trip D5."""
    if not os.path.isfile(INDEX):
        return set(), set()
    with open(INDEX, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"(?m)^##\s*Archiv", text)
    actives_text, archived_text = (text[: m.start()], text[m.start():]) if m else (text, "")
    entry_re = re.compile(r"(?m)^-\s*\[(" + ID_RE.pattern + r")\]\(")
    return set(entry_re.findall(actives_text)), set(entry_re.findall(archived_text))


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
# D8 — a retired decision (archived/revoked) still referenced by a living entry. #
# --------------------------------------------------------------------------- #

REFERENCE_CHANNELS = (
    ("memory", False),    # (subdir under ROOT, scan body for D-id mentions too)
    ("features", True),
)


def _reference_files():
    """Yields `(path, scan_body)` for every `memory/*.md`, `features/*.md`, and
    `backlog/<id>/STATE.md` file — the living entries a retired decision could still be
    referenced by. `decisions/` itself (and its `INDEX.md`) is never yielded: the
    revocation graph and the registry are not "references" for D8."""
    for subdir, scan_body in REFERENCE_CHANNELS:
        d = os.path.join(ROOT, subdir)
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            if fname.endswith(".md"):
                yield os.path.join(d, fname), scan_body

    backlog_dir = os.path.join(ROOT, "backlog")
    if os.path.isdir(backlog_dir):
        for entry in sorted(os.listdir(backlog_dir)):
            state = os.path.join(backlog_dir, entry, "STATE.md")
            if os.path.isfile(state):
                yield state, False


def rule_d8(by_id: dict) -> list:
    """`by_id`: `{id: (path, meta)}`. A decision `archived`/`revoked` can still be a
    legitimate historical citation (to-confirm, never blocking) — but a silent dangling
    reference is a memory-maintenance hole worth surfacing. Collects every retired id
    once, then reads each candidate referencing file exactly once (single pass over
    `_reference_files()`) — no re-open per id."""
    retired = {idv for idv, (_, meta) in by_id.items() if meta.get("status") in ("archived", "revoked")}
    if not retired:
        return []

    findings = []
    for fpath, scan_body in _reference_files():
        with open(fpath, encoding="utf-8") as fh:
            text = fh.read()
        meta, body, _ = entrylib.parse_frontmatter(text)

        referenced = set(_as_list(meta.get("links"))) & retired
        if scan_body:
            referenced |= set(ID_RE.findall(body)) & retired

        for idv in sorted(referenced):
            dec_path, dec_meta = by_id[idv]
            findings.append(Finding(TO_CONFIRM, "D8", dec_path, 1,
                                     f"status: {dec_meta.get('status')} but still referenced by "
                                     f"« {rel(fpath)} » — update the reference or reconsider "
                                     "the archival."))
    return findings


# --------------------------------------------------------------------------- #
# Orchestration.                                                              #
# --------------------------------------------------------------------------- #

def audit() -> list:
    findings = check_config() + list(rule_d1_d2())

    files = _decision_files()
    by_id = {}
    loaded = []  # (path, meta, body) in discovery order
    for idv, fname in files.items():
        fpath = os.path.join(DEC, fname)
        with open(fpath, encoding="utf-8") as fh:
            text = fh.read()
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
        # Body granularity. Skipped when the frontmatter is broken (already
        # R-NO-FRONTMATTER; `body` is unreliable then — no double signal).
        if meta:
            # Banner lines (Markdown blockquotes) carry the REVOCATION PROTOCOL — the
            # amendment notes and "what died / what survives" markers that a partially
            # revoked decision MUST keep. Charging them to a prose budget punishes the
            # decisions that were maintained: an untouched one has none, one amended
            # twice carries dozens. They get their own budget, D11.
            banner = [l for l in entrylib.useful_body_lines(body)
                      if l.lstrip().startswith(">")]
            # D12 — per-section granularity. D4 makes the three markers mandatory and
            # BLOCKING, so splitting on them is exact: a body that reached here has them
            # all. The `**Invariant**` segment runs to the end of file — trailing sections
            # (`## Scope`, `## Files`) are prose too and count against it.
            for name, count in _section_lines(body):
                if count > DECISION_SECTION_MAX_LINES:
                    findings.append(Finding(TO_CONFIRM, "D12", p, 1,
                                             f"section {name} is {count} written lines "
                                             f"(> {DECISION_SECTION_MAX_LINES}) — state the "
                                             "decision, keep the reason short, and move the "
                                             "analysis to the durable doc it motivates."))
            if len(banner) > DECISION_BANNER_MAX_LINES:
                findings.append(Finding(TO_CONFIRM, "D11", p, 1,
                                         f"{len(banner)} banner lines "
                                         f"(> {DECISION_BANNER_MAX_LINES}) — amendment and "
                                         "revocation notes are protocol, but a banner that outgrows "
                                         "its budget is analysis in disguise: state what died and "
                                         "what survives, and move the reasoning to the body or to "
                                         "the durable doc."))

    # D6 — revocation graph, cross-file scope.
    findings += rule_d6(by_id)
    # D8 — retired decision still referenced by a living entry, cross-channel scope.
    findings += rule_d8(by_id)
    # D10 — the INDEX line is id + title + one-line invariant, nothing more.
    findings += entrylib.check_index_entry_len(
        INDEX, ROOT, INDEX_ENTRY_MAX_WORDS, "D10",
        "the line is id + title + one-line invariant; anything more lives in the "
        "decision's own `D-….md` file.")

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
