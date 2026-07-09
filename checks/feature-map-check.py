#!/usr/bin/env python3
"""Integrity check of the "Feature" channel (`FEATURE_MAP.md` + `features/`), agnostic.

Format: one file per entry (`features/<slug>.md`, "feature" channel frontmatter) +
`FEATURE_MAP.md` = index (one line per entry) — same pattern as `memory-check.py` /
`decisions-check.py`, generalized via `entrylib.py` (`ENTRY-TEMPLATE.md`, "feature"
channel). Fixes NOTHING — flags.

Follows `checks/TEMPLATE.md`: 5-field `Finding` namedtuple, two verdicts, pure rules.

Rules:
  FM-INDEX       (BLOCKING)      `features/*.md` <-> `FEATURE_MAP.md` concordance, via
                                  `entrylib.check_index_concordance` — surfaces
                                  `R-ORPHAN-FILE` (entry with no index line) and
                                  `R-DEAD-INDEX` (index line with no entry).
  (R-*)          (see entrylib) `entrylib.validate_entry(path, meta, "feature")` per entry —
                                  `R-NO-FRONTMATTER`, `R-MISSING-KEY`, `R-BAD-VALUE`,
                                  `R-EXT-NO-CONF`, `R-UNVERIFIED`, `R-VERIFIED-NOT-RATIFIED`,
                                  `R-BAD-DATE` ; `entrylib.check_links` for `links:` —
                                  `R-DEAD-LINK`.
  FM1-role       (BLOCKING)      no `**Role:**` line in the body.
  FM1-code       (BLOCKING)      no code file path cited in the body.
  FM1-durable    (BLOCKING)      no durable reference: neither a non-empty
                                  `**Doc (durable):**` key, nor a `D-YYYY-MM-DD-NN` id
                                  (body or `links:`).
  FM-DECISION    (BLOCKING)      a `D-*` id cited in the BODY has no
                                  `decisions/D-*.md` file (the `links:` side is covered by
                                  `entrylib.check_links` -> `R-DEAD-LINK`).
  FM-TRANSIENT   (BLOCKING)      transient reference (`backlog/…`) in an entry — durable
                                  only, planned work lives in the backlog (ex-FM5).
  FM-FRESH       (TO-CONFIRM)    entry `updated` older than the last git commit touching
                                  one of the paths cited by `**Code:**` — entry possibly
                                  stale. Soft: an unversioned/nonexistent path is ignored
                                  (already covered by other rules, no double signal).
  FM-GRAN        (TO-CONFIRM)    body > ~60 useful lines -> candidate "two subjects".

Note: `TRANSIENT` (where the host project's backlog lives) depends on layout — the
default below covers THIS repo (`backlog/`).

`--stamp [files…]` / `--stamp --staged`: sets `updated: <today>` via
`entrylib.stamp_updated` on the entries passed as arguments (or staged ones with
`--staged`, strict `features/*.md` scope, re-stages with git after writing) — same triple
safeguard as `backlog-check.py --stamp`: strict staged scope, a single mechanical field,
never blocking.

Usage:
  python3 checks/feature-map-check.py                    # text report
  python3 checks/feature-map-check.py --json              # JSON findings output
  python3 checks/feature-map-check.py --stamp features/x.md
  python3 checks/feature-map-check.py --stamp --staged    # pre-commit
Exit code: 0 clean, 1 only TO-CONFIRM, 2 at least one BLOCKING.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entrylib  # noqa: E402

BLOCKING = entrylib.BLOCKING
TO_CONFIRM = entrylib.TO_CONFIRM
Finding = entrylib.Finding

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # …/ai-workflow
FMAP = os.path.join(ROOT, "FEATURE_MAP.md")
FEATURES_DIR = os.path.join(ROOT, "features")

ROLE_KEY = re.compile(r"^\*\*\s*Role\b", re.IGNORECASE)
DOC_KEY = re.compile(r"^\*\*\s*Doc\b", re.IGNORECASE)
DOC_KEY_VALUE = re.compile(r"^\*\*\s*Doc[^:*]*:?\*{0,2}\s*", re.IGNORECASE)
CODE_PATH = re.compile(r"(?:[\w.\-]+/)+[\w.\-]+\.[A-Za-z0-9]{1,6}")
DECISION_MENTION = re.compile(r"\bD-\d{4}-\d{2}-\d{2}-\d{2}\b")
TRANSIENT = re.compile(r"\bbacklog/")
GRAN_SEUIL = 60


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT)


def list_fiches() -> list[str]:
    if not os.path.isdir(FEATURES_DIR):
        return []
    return sorted(f for f in os.listdir(FEATURES_DIR) if f.endswith(".md"))


# --------------------------------------------------------------------------- #
# FM-INDEX — features/*.md <-> FEATURE_MAP.md concordance                    #
# --------------------------------------------------------------------------- #

INDEX_HEADING = "## Entries"


def _index_section_tempfile() -> str | None:
    """Isolates the `## Entries` section (the actual index) in a temp file — the preceding
    lines are replaced with blank lines to preserve line numbering (findings stay
    `path:line`-addressable on the original). Needed because the rest of the document
    (`§The format`, `§Full example`…) legitimately cites other `.md` files
    (`ENTRY-TEMPLATE.md`, the `null-check-unity.md` example…) unrelated to the index — a
    full-page scan would produce false-positive `R-DEAD-INDEX` on those mentions."""
    if not os.path.isfile(FMAP):
        return None
    with open(FMAP, encoding="utf-8") as fh:
        lines = fh.readlines()
    start = next((i for i, l in enumerate(lines) if l.strip() == INDEX_HEADING), len(lines))
    padded = ["\n"] * start + lines[start:]
    import tempfile
    fd, tmp_path = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.writelines(padded)
    return tmp_path


def check_index() -> list[Finding]:
    tmp = _index_section_tempfile()
    if tmp is None:
        return []
    try:
        findings = entrylib.check_index_concordance(tmp, FEATURES_DIR, r"[\w.\-]+\.md")
    finally:
        os.unlink(tmp)
    fmap_rel = rel(FMAP)
    return [Finding(f.severity, f.rule,
                     fmap_rel if f.path == tmp else rel(f.path),
                     f.line, f.msg.replace(tmp, fmap_rel))
            for f in findings]


# --------------------------------------------------------------------------- #
# Freshness — FM-FRESH (soft)                                                 #
# --------------------------------------------------------------------------- #

def _git_last_commit_date(relpath: str) -> str | None:
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", relpath],
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    out = r.stdout.strip()
    return out or None


def check_freshness(fiche_path: str, meta: dict, body: str) -> list[Finding]:
    """FM-FRESH — `updated` older than the last commit touching a `**Code:**` path.

    Tolerant: a nonexistent path (dead-path, already `doc-refs-check.py`) or unversioned
    (empty git log) -> ignored, no double signal.
    """
    updated = meta.get("updated")
    if not updated or not entrylib.DATE_RE.match(str(updated)):
        return []
    findings: list[Finding] = []
    seen = set()
    for m in CODE_PATH.finditer(body):
        p = m.group(0)
        if p in seen:
            continue
        seen.add(p)
        if not os.path.exists(os.path.join(ROOT, p)):
            continue
        commit_date = _git_last_commit_date(p)
        if commit_date and commit_date > str(updated):
            findings.append(Finding(TO_CONFIRM, "FM-FRESH", rel(fiche_path), 1,
                f"« {p} » modified on {commit_date}, entry « updated: {updated} » "
                "— entry possibly stale."))
    return findings


# --------------------------------------------------------------------------- #
# One entry — frontmatter (entrylib) + core body keys + safeguards            #
# --------------------------------------------------------------------------- #

def check_fiche(fname: str) -> list[Finding]:
    path = os.path.join(FEATURES_DIR, fname)
    findings: list[Finding] = []
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    meta, body, err = entrylib.parse_frontmatter(text)
    if err:
        findings.append(Finding(BLOCKING, "R-NO-FRONTMATTER", rel(path), 1, err))
        return findings  # no usable body without a closed frontmatter

    findings += entrylib.validate_entry(rel(path), meta, "feature")
    findings += entrylib.check_links(rel(path), meta, ROOT)

    body_lines = body.splitlines()

    if not any(ROLE_KEY.match(l.strip()) for l in body_lines):
        findings.append(Finding(BLOCKING, "FM1-role", rel(path), 1,
                                 "no `**Role:**` core key."))

    if not CODE_PATH.search(body):
        findings.append(Finding(BLOCKING, "FM1-code", rel(path), 1,
                                 "no code file path cited."))

    doc_nonempty = any(
        DOC_KEY.match(l.strip()) and DOC_KEY_VALUE.sub("", l.strip()).strip()
        for l in body_lines
    )
    links_meta = meta.get("links") or []
    if isinstance(links_meta, str):
        links_meta = [links_meta]
    has_decision_link = any(entrylib.DECISION_ID.match(str(x).strip()) for x in links_meta)
    has_decision_mention = bool(DECISION_MENTION.search(body))
    if not (doc_nonempty or has_decision_link or has_decision_mention):
        findings.append(Finding(BLOCKING, "FM1-durable", rel(path), 1,
                                 "no durable reference (`**Doc**` key non-empty, or a `D-*` id)."))

    for m in TRANSIENT.finditer(body):
        findings.append(Finding(BLOCKING, "FM-TRANSIENT", rel(path), 1,
                                 f"transient reference « {m.group(0)}… » — durable only, "
                                 "planned work lives in the backlog."))

    for d in sorted(set(DECISION_MENTION.findall(body))):
        if not os.path.isfile(os.path.join(ROOT, "decisions", d + ".md")):
            findings.append(Finding(BLOCKING, "FM-DECISION", rel(path), 1,
                                     f"id « {d} » cited in the body but decisions/{d}.md not found."))

    useful = [l for l in body_lines if l.strip() and not l.strip().startswith("|---")]
    if len(useful) > GRAN_SEUIL:
        findings.append(Finding(TO_CONFIRM, "FM-GRAN", rel(path), 1,
                                 f"{len(useful)} useful lines (> {GRAN_SEUIL}) -> consider "
                                 "splitting (two subjects?)."))

    findings += check_freshness(path, meta, body)
    return findings


# --------------------------------------------------------------------------- #
# --stamp — sets `updated` alone, never blocking                              #
# --------------------------------------------------------------------------- #

def cmd_stamp(argv: list[str]) -> int:
    """Sets `updated: today` on the cited entries (or staged ones with `--staged`) +
    re-stages. Pattern shared with `backlog-check.py --stamp`: strict staged scope
    (`features/*.md` only), a single mechanical field (`entrylib.stamp_updated` only
    touches `updated`), never blocking (exit code always 0)."""
    today = datetime.date.today().isoformat()
    staged = "--staged" in argv
    if staged:
        r = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                            cwd=ROOT, capture_output=True, text=True)
        files = [f for f in r.stdout.splitlines()
                 if f.replace("\\", "/").startswith("features/") and f.endswith(".md")]
    else:
        files = [a for a in argv[argv.index("--stamp") + 1:] if not a.startswith("-")]

    changed = []
    for f in files:
        full = f if os.path.isabs(f) else os.path.join(ROOT, f)
        if not os.path.isfile(full):
            continue
        if entrylib.stamp_updated(full, today):
            changed.append(f)
            if staged:
                subprocess.run(["git", "add", f], cwd=ROOT)
    print(f"feature-map-check: --stamp — {len(changed)} entrie(s) stamped {today}.")
    return 0


# --------------------------------------------------------------------------- #
# Rendering / CLI                                                             #
# --------------------------------------------------------------------------- #

def run() -> list[Finding]:
    findings = list(check_index())
    for fname in list_fiches():
        findings += check_fiche(fname)
    return findings


def render_text(findings: list[Finding]) -> str:
    if not findings:
        return "feature-map-check: OK."
    bloq = [f for f in findings if f.severity == BLOCKING]
    conf = [f for f in findings if f.severity == TO_CONFIRM]
    lines = [f"{f.severity:14} {f.path}:{f.line}  {f.rule}  {f.msg}"
             for f in sorted(findings, key=lambda f: (f.severity != BLOCKING, f.path, f.line))]
    lines.append(f"\n— {len(findings)} finding(s): {len(bloq)} blocking-auto, {len(conf)} to-confirm")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if "--stamp" in argv:
        return cmd_stamp(argv)

    findings = run()
    if "--json" in argv:
        print(json.dumps([f._asdict() for f in findings], ensure_ascii=False, indent=2))
    else:
        print(render_text(findings))

    if any(f.severity == BLOCKING for f in findings):
        return 2
    if any(f.severity == TO_CONFIRM for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
