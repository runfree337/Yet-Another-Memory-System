#!/usr/bin/env python3
"""Shared "memory entry" library — NOT a standalone check, stdlib only.

Generalizes the pattern carried by `memory-check.py` (frontmatter + file<->index
concordance) to every memory channel (`ENTRY-TEMPLATE.md`): Memory, Decision, Feature,
Backlog. Channel checks import this lib instead of redefining their own parser/regex —
**a single place** defines what a valid memory entry is.

Follows `checks/TEMPLATE.md`: 5-field `Finding` namedtuple, two verdicts
(`BLOCKING-AUTO` / `TO-CONFIRM`), pure rules, no side effects.

Frontmatter vocabulary — keys/values in ENGLISH by design (machine API, greppable;
the body prose stays in the team's own language, cf. `ENTRY-TEMPLATE.md`):
  id, status, source, confidence, created, updated, links, ratified
  source     : inferred | human | external:<ref>
  confidence : verified | unverified
  ratified   : <who>, <YYYY-MM-DD>  — required to move to confidence: verified

Usage:
  import sys; sys.path.insert(0, "checks"); import entrylib   # from another check
  python3 checks/entrylib.py --selftest                       # only executable mode
"""
from __future__ import annotations

import os
import re
import sys
from collections import namedtuple

# --------------------------------------------------------------------------- #
# The template (checks/TEMPLATE.md) — Finding + two verdicts.                 #
# --------------------------------------------------------------------------- #

BLOCKING = "BLOCKING-AUTO"
TO_CONFIRM = "TO-CONFIRM"

Finding = namedtuple("Finding", "severity rule path line msg")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SOURCE_RE = re.compile(r"^(inferred|human|external:.+)$")
CONFIDENCE_VALUES = {"verified", "unverified"}


# --------------------------------------------------------------------------- #
# Per-channel spec — required/optional keys + channel-specific enums.         #
# Common vocabulary (id/source/confidence/created/updated/links/ratified)     #
# validated by generic rules; `enums` only carries the keys SPECIFIC to the   #
# channel (e.g. `status`) whose values vary from one channel to the next.     #
# --------------------------------------------------------------------------- #

CHANNELS = {
    "memory": {
        "required": ("id", "source", "confidence", "created", "updated"),
        "optional": ("links", "ratified"),
        "enums": {},
        "nullable": (),
    },
    "decision": {
        "required": ("id", "status", "source", "confidence", "created", "updated"),
        "optional": ("links", "replaces", "replaced-by", "ratified"),
        "enums": {"status": {"active", "revoked", "archived"}},
        "nullable": (),
    },
    "feature": {
        "required": ("id", "created", "updated"),
        "optional": ("links", "source", "confidence", "ratified"),
        "enums": {},
        "nullable": (),
    },
    "backlog": {
        "required": ("id", "status", "title", "milestone", "updated"),
        "optional": ("links", "source", "confidence", "ratified", "after", "docs", "created"),
        "enums": {"status": {"todo", "in-progress"}},
        "nullable": ("milestone",),
    },
}


# --------------------------------------------------------------------------- #
# Minimal homegrown frontmatter parser — no yaml dependency.                  #
# --------------------------------------------------------------------------- #

def _parse_scalar(val: str):
    """A scalar value or an inline list `[a, b]`. Never nested YAML."""
    val = val.strip()
    if val in ("", "null", "~"):
        return None
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()] if inner else []
    return val.strip("'\"")


def parse_frontmatter(text: str):
    """`--- … ---` block at the top of the file, scalar `key: value` + inline `[a, b]` lists.

    Returns `(meta, body, error)`: `meta` is `{}` and `error` is not `None` if the block is
    missing or never closed. `body` is the text after the block (empty string if no block).
    Never raises.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, "no frontmatter block (no --- on the first line)"

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, "", "frontmatter block never closed (no second ---)"

    meta = {}
    for line in lines[1:end]:
        raw = line.strip()
        if not raw or raw.startswith("#") or ":" not in raw:
            continue
        key, _, val = line.partition(":")
        meta[key.strip()] = _parse_scalar(val)

    body = "\n".join(lines[end + 1:])
    return meta, body, None


# --------------------------------------------------------------------------- #
# Entry validation — rules common to every channel.                           #
# --------------------------------------------------------------------------- #

def validate_entry(path: str, meta: dict, channel: str) -> list:
    """Validates the `meta` frontmatter of an entry `path` against channel `channel`.

    Rules (stable, grep-able ids — see file header for details):
      R-NO-FRONTMATTER, R-MISSING-KEY, R-BAD-VALUE, R-EXT-NO-CONF, R-UNVERIFIED,
      R-VERIFIED-NOT-RATIFIED, R-BAD-DATE.
    Raises `ValueError` if `channel` is not in `CHANNELS`.
    """
    spec = CHANNELS.get(channel)
    if spec is None:
        raise ValueError(f"unknown channel: {channel!r} (expected: {', '.join(sorted(CHANNELS))})")

    findings = []

    if not meta:
        findings.append(Finding(BLOCKING, "R-NO-FRONTMATTER", path, 1,
                                 "no --- ... --- frontmatter at the top of the file"))
        return findings

    nullable = set(spec.get("nullable", ()))
    for key in spec["required"]:
        val = meta.get(key)
        missing = key not in meta or val == "" or (val is None and key not in nullable)
        if missing:
            findings.append(Finding(BLOCKING, "R-MISSING-KEY", path, 1,
                                     f"required key « {key} » missing or empty for channel « {channel} »"))

    for key, allowed in spec.get("enums", {}).items():
        val = meta.get(key)
        if val is not None and val not in allowed:
            findings.append(Finding(BLOCKING, "R-BAD-VALUE", path, 1,
                                     f"« {key}: {val} » invalid for channel « {channel} » "
                                     f"(expected: {' | '.join(sorted(allowed))})"))

    source = meta.get("source")
    if source is not None and not SOURCE_RE.match(str(source).strip()):
        findings.append(Finding(BLOCKING, "R-BAD-VALUE", path, 1,
                                 f"« source: {source} » invalid (expected: inferred | human | external:<ref>)"))

    confidence = meta.get("confidence")
    if confidence is not None and confidence not in CONFIDENCE_VALUES:
        findings.append(Finding(BLOCKING, "R-BAD-VALUE", path, 1,
                                 f"« confidence: {confidence} » invalid (expected: verified | unverified)"))

    if source and str(source).strip().startswith("external:") and not confidence:
        findings.append(Finding(BLOCKING, "R-EXT-NO-CONF", path, 1,
                                 "source: external:... with no confidence field"))

    if confidence == "unverified":
        findings.append(Finding(TO_CONFIRM, "R-UNVERIFIED", path, 1,
                                 "confidence: unverified — candidate for semantic audit (tier 2)"))

    if confidence == "verified" and not meta.get("ratified"):
        findings.append(Finding(TO_CONFIRM, "R-VERIFIED-NOT-RATIFIED", path, 1,
                                 "confidence: verified with no ratified field — ratification not tracked"))

    for key in ("created", "updated"):
        val = meta.get(key)
        if val is not None and not DATE_RE.match(str(val)):
            findings.append(Finding(BLOCKING, "R-BAD-DATE", path, 1,
                                     f"« {key}: {val} » malformed (expected YYYY-MM-DD)"))

    return findings


# --------------------------------------------------------------------------- #
# File <-> index concordance — generalization of memory-check/decisions-check #
# --------------------------------------------------------------------------- #

def check_index_concordance(index_path: str, entries_dir: str, id_pattern) -> list:
    """Every entry file referenced by the index, every index reference resolved.

    `id_pattern` (str or compiled regex) extracts a comparable identifier from both the
    file names of `entries_dir` (matched against the bare name) and the text of
    `index_path` (matched against each line). Same pattern as `memory-check.py`
    (`memory/<slug>.md` files <=> `MEMORY.md` links) and `decisions-check.py` (`D-*.md`
    files <=> `decisions/INDEX.md` ids), generalized to the channel supplied by the caller.
    """
    pat = re.compile(id_pattern) if isinstance(id_pattern, str) else id_pattern
    findings = []

    files = {}
    if os.path.isdir(entries_dir):
        for fname in sorted(os.listdir(entries_dir)):
            if not fname.endswith(".md"):
                continue
            m = pat.search(fname)
            if m:
                files[m.group(0)] = fname

    indexed = set()
    reported = set()  # a dead id is reported only once, even if repeated (e.g. `[id](id.md)`)
    if os.path.isfile(index_path):
        with open(index_path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                for m in pat.finditer(line):
                    idv = m.group(0)
                    indexed.add(idv)
                    if idv not in files and idv not in reported:
                        reported.add(idv)
                        findings.append(Finding(BLOCKING, "R-DEAD-INDEX", index_path, lineno,
                                                 f"reference « {idv} » — no file found in {entries_dir}"))

    for idv, fname in sorted(files.items()):
        if idv not in indexed:
            findings.append(Finding(BLOCKING, "R-ORPHAN-FILE", os.path.join(entries_dir, fname), 1,
                                     f"exists but is referenced by no line of {index_path}"))

    return findings


# --------------------------------------------------------------------------- #
# Stamp — rewrites `updated` and nothing else.                                #
# --------------------------------------------------------------------------- #

def stamp_updated(path: str, date_str: str) -> bool:
    """Rewrites the `updated` frontmatter field of `path` (and only that field).

    Shared `--stamp` pattern (cf. `backlog-check.py --stamp`). Returns `True` if the file
    was modified, `False` if `updated` was already `date_str` (or the field is absent —
    no-op).
    """
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    new_text = re.sub(r"(?m)^updated:.*$", f"updated: {date_str}", text, count=1)
    if new_text == text:
        return False
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new_text)
    return True


DECISION_ID = re.compile(r"^D-\d{4}-\d{2}-\d{2}-\d{2}$")


def check_links(path: str, meta: dict, root: str) -> list:
    """Resolves the `links:` of an entry — cross-channel references.

    Three recognized forms: a decision id `D-YYYY-MM-DD-NN` (-> `decisions/<id>.md` must
    exist), a path (contains `/` or an extension -> the file/directory must exist from
    `root`), otherwise an entry slug (-> looked up in `memory/`, `features/`,
    `backlog/<slug>/`). A dead id/path = `R-DEAD-LINK` (blocking); a dead slug =
    to-confirm (the target channel might just not be populated yet).
    """
    findings = []
    links = meta.get("links") or []
    if isinstance(links, str):
        links = [links]
    for link in links:
        link = str(link).strip()
        if not link:
            continue
        if DECISION_ID.match(link):
            if not os.path.isfile(os.path.join(root, "decisions", link + ".md")):
                findings.append(Finding(BLOCKING, "R-DEAD-LINK", path, 1,
                                        f"links: decision « {link} » has no decisions/{link}.md file"))
        elif "/" in link or "." in link:
            if not os.path.exists(os.path.join(root, link)):
                findings.append(Finding(BLOCKING, "R-DEAD-LINK", path, 1,
                                        f"links: path « {link} » not found"))
        else:
            candidates = (os.path.join(root, "memory", link + ".md"),
                          os.path.join(root, "features", link + ".md"),
                          os.path.join(root, "backlog", link))
            if not any(os.path.exists(c) for c in candidates):
                findings.append(Finding(TO_CONFIRM, "R-DEAD-LINK", path, 1,
                                        f"links: entry « {link} » not found (memory/, features/, backlog/)"))
    return findings


# --------------------------------------------------------------------------- #
# --selftest — embedded test suite, no effect when imported.                  #
# --------------------------------------------------------------------------- #

def _selftest() -> int:
    import tempfile

    failures = []

    def check(cond, label):
        if not cond:
            failures.append(label)

    # parse_frontmatter — valid block, scalar, inline list, body after the block
    meta, body, err = parse_frontmatter("---\nid: mem-1\nlinks: [a, b]\n---\nbody\n")
    check(err is None, "parse_frontmatter: no error on valid block")
    check(meta.get("id") == "mem-1", "parse_frontmatter: scalar id")
    check(meta.get("links") == ["a", "b"], "parse_frontmatter: inline list")
    check(body.strip() == "body", "parse_frontmatter: body after the block")

    # parse_frontmatter — no block / block never closed
    meta2, _, err2 = parse_frontmatter("no frontmatter\n")
    check(err2 is not None and meta2 == {}, "parse_frontmatter: error + empty meta if no block")
    _, _, err3 = parse_frontmatter("---\nid: x\n")
    check(err3 is not None, "parse_frontmatter: error if block never closed")

    # validate_entry — R-NO-FRONTMATTER
    f = validate_entry("f.md", {}, "memory")
    check(len(f) == 1 and f[0].rule == "R-NO-FRONTMATTER", "validate_entry: R-NO-FRONTMATTER")

    # validate_entry — R-MISSING-KEY
    f = validate_entry("f.md", {"id": "x"}, "memory")
    check(any(x.rule == "R-MISSING-KEY" for x in f), "validate_entry: R-MISSING-KEY")

    # validate_entry — R-BAD-VALUE (status enum specific to the decision channel)
    meta_dec = {"id": "D-2026-01-01-01", "status": "bogus", "source": "human",
                "confidence": "verified", "ratified": "raph, 2026-01-01",
                "created": "2026-01-01", "updated": "2026-01-01"}
    f = validate_entry("d.md", meta_dec, "decision")
    check(any(x.rule == "R-BAD-VALUE" for x in f), "validate_entry: R-BAD-VALUE (status)")

    # validate_entry — R-EXT-NO-CONF
    meta_ext = {"id": "mem-2", "source": "external:https://x", "created": "2026-01-01", "updated": "2026-01-01"}
    f = validate_entry("m.md", meta_ext, "memory")
    check(any(x.rule == "R-EXT-NO-CONF" for x in f), "validate_entry: R-EXT-NO-CONF")

    # validate_entry — R-UNVERIFIED
    meta_unv = {"id": "mem-3", "source": "human", "confidence": "unverified",
                "created": "2026-01-01", "updated": "2026-01-01"}
    f = validate_entry("m.md", meta_unv, "memory")
    check(any(x.rule == "R-UNVERIFIED" and x.severity == TO_CONFIRM for x in f),
          "validate_entry: R-UNVERIFIED")

    # validate_entry — R-VERIFIED-NOT-RATIFIED
    meta_verif = {"id": "mem-4", "source": "human", "confidence": "verified",
                  "created": "2026-01-01", "updated": "2026-01-01"}
    f = validate_entry("m.md", meta_verif, "memory")
    check(any(x.rule == "R-VERIFIED-NOT-RATIFIED" for x in f),
          "validate_entry: R-VERIFIED-NOT-RATIFIED")

    # validate_entry — R-BAD-DATE
    meta_date = {"id": "mem-5", "source": "human", "confidence": "verified",
                 "ratified": "raph, 2026-01-01", "created": "2026/01/01", "updated": "2026-01-01"}
    f = validate_entry("m.md", meta_date, "memory")
    check(any(x.rule == "R-BAD-DATE" for x in f), "validate_entry: R-BAD-DATE")

    # validate_entry — unknown channel
    try:
        validate_entry("m.md", {"id": "x"}, "unknown")
        check(False, "validate_entry: must raise ValueError on unknown channel")
    except ValueError:
        check(True, "validate_entry: raises ValueError on unknown channel")

    # check_index_concordance — orphan + dead link, on tempfile fixtures
    with tempfile.TemporaryDirectory() as td:
        entries_dir = os.path.join(td, "memory")
        os.makedirs(entries_dir)
        with open(os.path.join(entries_dir, "orphan-fact.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nid: orphan-fact\n---\n")
        index_path = os.path.join(td, "MEMORY.md")
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write("- [dead-fact](memory/dead-fact.md) — does not exist\n")
        findings = check_index_concordance(index_path, entries_dir, r"[\w.\-]+\.md")
        check(any(x.rule == "R-ORPHAN-FILE" for x in findings), "check_index_concordance: R-ORPHAN-FILE")
        check(any(x.rule == "R-DEAD-INDEX" for x in findings), "check_index_concordance: R-DEAD-INDEX")

    # stamp_updated — rewrites updated alone, no-op if already up to date
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "entry.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("---\nid: x\nupdated: 2020-01-01\n---\nbody\n")
        ok = stamp_updated(p, "2026-07-09")
        check(ok, "stamp_updated: reports a modification")
        text = open(p, encoding="utf-8").read()
        check("updated: 2026-07-09" in text, "stamp_updated: date rewritten")
        check("id: x" in text, "stamp_updated: other keys untouched")
        check(not stamp_updated(p, "2026-07-09"), "stamp_updated: no-op if already up to date")

    # check_index_concordance — a dead id repeated on the same line doesn't double the finding
    with tempfile.TemporaryDirectory() as td:
        d = os.path.join(td, "entries")
        os.makedirs(d)
        idx = os.path.join(td, "INDEX.md")
        with open(idx, "w", encoding="utf-8") as fh:
            fh.write("- [D-2099-01-01-01](D-2099-01-01-01.md) — ghost\n")
        fs = check_index_concordance(idx, d, r"D-\d{4}-\d{2}-\d{2}-\d{2}")
        check(len(fs) == 1, "concordance: repeated dead id on the line -> a single finding")

    # check_links — decision id, path, slug; dead and alive
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "decisions"))
        os.makedirs(os.path.join(td, "memory"))
        with open(os.path.join(td, "decisions", "D-2026-01-01-01.md"), "w") as fh:
            fh.write("x")
        with open(os.path.join(td, "memory", "rule-a.md"), "w") as fh:
            fh.write("x")
        meta = {"links": ["D-2026-01-01-01", "memory/rule-a.md", "rule-a"]}
        check(check_links("e.md", meta, td) == [], "check_links: alive links -> no finding")
        meta = {"links": ["D-2099-01-01-01", "memory/absent.md", "unknown-slug"]}
        fs = check_links("e.md", meta, td)
        check(len(fs) == 3, "check_links: 3 dead links -> 3 findings")
        check(sum(1 for f in fs if f.severity == BLOCKING) == 2,
              "check_links: dead id/path are blocking")
        check(sum(1 for f in fs if f.rule == "R-DEAD-LINK") == 3, "check_links: R-DEAD-LINK rule")

    if failures:
        print(f"entrylib --selftest: {len(failures)} failure(s):")
        for label in failures:
            print(f"  - {label}")
        return 1
    print("entrylib --selftest: OK.")
    return 0


def main(argv) -> int:
    if "--selftest" in argv:
        return _selftest()
    print("usage: python3 checks/entrylib.py --selftest   "
          "(shared library — imported by channel checks, not a standalone check)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
