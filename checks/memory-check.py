#!/usr/bin/env python3
r"""Integrity check of the "Memory" channel (preferences), agnostic.

Format: one fact per file + frontmatter (`memory/<slug>.md`), `MEMORY.md` = index (one
line per file) — instance of the `ENTRY-TEMPLATE.md` meta-schema. All the
frontmatter/concordance/links logic lives in the shared library `checks/entrylib.py` (a
single place defines what a valid memory entry is, reused by `decisions-check.py` /
`feature-map-check.py` / `backlog-check.py`) — this script just calls `entrylib` with
the `"memory"` channel and aggregates.

Follows `checks/TEMPLATE.md`: 5-field `Finding` namedtuple, two verdicts, 0/1/2 exit code.

Rule table (id -> severity -> what it proves):

| Rule                         | Severity      | Proves |
|-------------------------------|---------------|--------|
| `CFG-INVALID`                 | BLOCKING-AUTO | `checks-config.json` present at the repo root but broken (unreadable, malformed JSON, non-object top level) — see `entrylib.load_checks_config`. |
| `R-NO-FRONTMATTER`           | BLOCKING-AUTO | `memory/<slug>.md` doesn't start with a `--- … ---` block. |
| `R-MISSING-KEY`               | BLOCKING-AUTO | a required channel key (`id/source/confidence/created/updated`) is missing or empty. |
| `R-BAD-VALUE`                 | BLOCKING-AUTO | `source:` or `confidence:` doesn't respect its closed vocabulary (`inferred\|human\|external:<ref>`, `verified\|unverified`). |
| `R-EXT-NO-CONF`               | BLOCKING-AUTO | `source: external:...` with no `confidence` field at all — an external source MUST carry a confidence. |
| `R-BAD-DATE`                  | BLOCKING-AUTO | `created`/`updated` isn't in `YYYY-MM-DD` format. |
| `R-DEAD-LINK` (blocking)      | BLOCKING-AUTO | `links:` cites a decision id `D-*` or a path that doesn't exist on disk. |
| `R-ORPHAN-FILE`               | BLOCKING-AUTO | `memory/<slug>.md` exists but no line of `MEMORY.md` references it. |
| `R-DEAD-INDEX`                | BLOCKING-AUTO | a line of `MEMORY.md` references `memory/<slug>.md` and the file doesn't exist. |
| `R-UNVERIFIED`                | TO-CONFIRM    | `confidence: unverified` — candidate for semantic audit (tier 2, `memory-audit.md`), not an error in itself. |
| `R-VERIFIED-NOT-RATIFIED`     | TO-CONFIRM    | `confidence: verified` with no `ratified` field — human ratification not tracked. |
| `R-DEAD-LINK` (to-confirm)    | TO-CONFIRM    | `links:` cites an entry slug not found in `memory/`/`features/`/`backlog/` — the target channel might just not be populated yet. |
| `M-GRAN`                      | TO-CONFIRM    | entry body > `sizes.memory-entry-max-lines` useful lines (`checks-config.json`, default 40) — granularity hint: one fact per file, long detail belongs in the durable doc (cf. `MEMORY.md`), never blocking. |

These ids are the channel's API — stable, grep-able, cited by `checks/memory-audit.md`
and the docs. Each rule's detail is defined once in `checks/entrylib.py`; this file never
redefines them (`M-GRAN` is the one rule local to this script — no channel elsewhere had
a size signal on memory entries).

Read-only by default. Fixes nothing — flags. `--stamp` is the only write (see below),
scoped to the `updated` field.

Usage:
  python3 checks/memory-check.py                 # MEMORY.md + memory/ by default
  python3 checks/memory-check.py --json
  python3 checks/memory-check.py --stamp --staged # pre-commit only
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

# Windows consoles default to cp1252: non-cp1252 output (→, ⨯…) would crash print().
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entrylib  # noqa: E402

BLOCKING = entrylib.BLOCKING
TO_CONFIRM = entrylib.TO_CONFIRM
Finding = entrylib.Finding

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # framework root
MEMORY_MD = os.path.join(ROOT, "MEMORY.md")
MEMORY_DIR = os.path.join(ROOT, "memory")

# Global settings (checks-config.json, optional) — loaded once. `_CFG_ERR` is surfaced
# as a BLOCKING CFG-INVALID finding by `check_config()`, never silently ignored.
_CFG, _CFG_ERR = entrylib.load_checks_config(ROOT)
GRAN_MAX_LINES = entrylib.cfg_get(_CFG, ("sizes", "memory-entry-max-lines"), 40)

# A memory entry has no rigid id grammar (unlike `D-YYYY-MM-DD-NN` on the decisions side)
# — a bare `.md` isn't enough to prove a reference (`MEMORY.md` mentions
# `ENTRY-TEMPLATE.md`, `memory-audit.md`… constantly). So we anchor on the template's
# LINK FORM: either a bare file name (`entries_dir`, e.g. `mem-slug.md`), or
# `(memory/<slug>.md)` in the index text — never a `.md` floating in prose.
ID_RE = re.compile(r"(?<=\(memory/)[\w.-]+\.md(?=\))|^[\w.-]+\.md$")


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT)


def check_config() -> list:
    """CFG-INVALID — `checks-config.json` present but broken. Surfaced once per run so
    a broken config (unreadable, malformed JSON, non-object top level) never silently
    falls back to defaults without the team knowing — same convention as
    `feature-map-check.py`/`backlog-check.py`."""
    if _CFG_ERR:
        return [Finding(BLOCKING, "CFG-INVALID", entrylib.CHECKS_CONFIG_NAME, 1, _CFG_ERR)]
    return []


def _useful_body_lines(body: str) -> list[str]:
    """Same filter as `feature-map-check.py`'s FM-GRAN rule: blank lines and Markdown
    table separator rows (`|---`) don't count as "content" — keeps the two channels'
    line count directly comparable."""
    return [l for l in body.splitlines() if l.strip() and not l.strip().startswith("|---")]


# --------------------------------------------------------------------------- #
# Pure rules — delegate to entrylib, this script only aggregates.             #
# --------------------------------------------------------------------------- #

def audit_memory_dir() -> list:
    """Frontmatter + cross-references of every `memory/<slug>.md`, via `entrylib`, plus
    the local `M-GRAN` granularity rule (see file header)."""
    findings: list = []
    if not os.path.isdir(MEMORY_DIR):
        return findings
    for fname in sorted(os.listdir(MEMORY_DIR)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(MEMORY_DIR, fname)
        text = open(fpath, encoding="utf-8").read()
        meta, body, _err = entrylib.parse_frontmatter(text)
        path = rel(fpath)
        findings += entrylib.validate_entry(path, meta, "memory")
        findings += entrylib.check_links(path, meta, ROOT)

        # No frontmatter -> R-NO-FRONTMATTER already fired above; `body` would then be
        # unreliable (raw text or empty depending on the failure) — skip M-GRAN, no
        # double signal on an already-broken file.
        useful = _useful_body_lines(body) if meta else []
        if len(useful) > GRAN_MAX_LINES:
            findings.append(Finding(TO_CONFIRM, "M-GRAN", path, 1,
                f"{len(useful)} useful lines (> {GRAN_MAX_LINES}) — one fact per file; "
                "long detail belongs in the durable doc, cf. MEMORY.md — move the detail "
                "there and keep this entry as a pointer."))
    return findings


def audit_index_concordance() -> list:
    """Concordance `memory/<slug>.md` <=> `MEMORY.md` lines, via `entrylib`."""
    findings = entrylib.check_index_concordance(MEMORY_MD, MEMORY_DIR, ID_RE)
    return [f._replace(path=rel(f.path)) for f in findings]


# --------------------------------------------------------------------------- #
# --stamp — same triple safeguard as backlog-check.py: staged scope,          #
# mechanical field (`updated`) alone, never blocking.                        #
# --------------------------------------------------------------------------- #

def cmd_stamp(argv) -> int:
    """Sets `updated: <today>` on the cited `memory/*.md` files (or staged ones with
    --staged) and re-stages. Meant to be wired to pre-commit — the frontmatter date
    follows the commit date, mechanically (zero rot). Staged scope only: never pulls a
    file outside the commit in progress."""
    import datetime
    today = datetime.date.today().isoformat()
    staged = "--staged" in argv

    if staged:
        # cwd=ROOT + ROOT-joined paths, like the two sibling stamps (backlog-check,
        # feature-map-check) — the script must work from any working directory.
        r = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        files = [f for f in r.stdout.splitlines()
                 if f.replace("\\", "/").startswith("memory/") and f.endswith(".md")]
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
                subprocess.run(["git", "add", "--", f], cwd=ROOT)

    print(f"memory-check: --stamp — {len(changed)} memory/*.md stamped {today}.")
    return 0


# --------------------------------------------------------------------------- #
def main(argv) -> int:
    if "--stamp" in argv:
        return cmd_stamp(argv)

    as_json = "--json" in argv

    findings = check_config() + audit_memory_dir() + audit_index_concordance()

    # Same convention as feature-map-check.py: an empty or absent channel is SAID, never
    # summarized as a bare 0-finding report a reader would take for a verified channel.
    # Text mode only: `--json` keeps printing the (empty) findings array.
    def _entries():
        if not os.path.isdir(MEMORY_DIR):
            return []
        return [f for f in os.listdir(MEMORY_DIR) if f.endswith(".md")]

    if not findings and not _entries() and not as_json:
        if not os.path.isfile(MEMORY_MD) and not os.path.isdir(MEMORY_DIR):
            print("memory-check: no MEMORY.md and no memory/ — Memory channel absent, "
                  "nothing to verify.")
        else:
            print("memory-check: 0 entries — empty Memory channel (or an index not in the "
                  "one-fact-per-file format, which this check cannot see). Nothing verified.")
        return 0

    bloq = [f for f in findings if f.severity == BLOCKING]
    conf = [f for f in findings if f.severity == TO_CONFIRM]

    if as_json:
        print(json.dumps([f._asdict() for f in findings], ensure_ascii=False, indent=2))
    else:
        for f in sorted(findings, key=lambda f: (f.severity != BLOCKING, f.path, f.line)):
            print(f"{f.severity:14} {f.path}:{f.line}  {f.rule}  {f.msg}")
        print(f"\n— {len(findings)} finding(s): {len(bloq)} blocking-auto, {len(conf)} to-confirm")

    return 2 if bloq else (1 if conf else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
