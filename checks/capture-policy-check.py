#!/usr/bin/env python3
"""Capture-policy enforcement — turns policy prose into blocking findings.

Capture (knowledge routed to a memory channel at closure, `knowledge-capture.md`) is
today human-gated by PROSE only. This script makes it ENFORCEABLE: the project opts in
by copying `capture-policy.example.json` (repo root) to `capture-policy.json` and
setting a level per channel; this script then checks every existing entry of every
channel against its declared level. AGNOSTIC like `index-check.py`: without
`capture-policy.json` at the repo root, there is nothing to enforce (the project hasn't
opted in) -> exit 0. The framework repo itself carries no real policy file, so this
check stays inactive on itself by construction.

The three levels (`channels.<name>`, see `capture-policy.example.json` `_levels`):
  off      no capture to this channel — only ratified entries may exist, nothing new expected.
  propose  only ratified entries may exist — the human said yes, the trace is the
           `ratified` field (`confidence: verified` + `ratified: <who>, <date>`).
  draft    the AI may write directly — always `confidence: unverified`, tracked by the
           ratification inbox (`memory-audit.py --pending`). Produces NO findings here:
           visibility is already the inbox's job, this check never double-signals it.

Channel -> files mapping: memory -> `memory/*.md`, feature -> `features/*.md`,
decision -> `decisions/D-*.md`. Frontmatter read via `entrylib.parse_frontmatter`; a file
with no frontmatter block, or no `confidence` key at all, is silently skipped — that's
another check's business (`entrylib.validate_entry`'s own `R-NO-FRONTMATTER`/`R-MISSING-KEY`).

Rule table (id -> severity -> what it proves):

| Rule            | Severity      | Proves |
|-----------------|---------------|--------|
| `CP-BAD-LEVEL`  | BLOCKING-AUTO | a `channels.<name>` value outside `off \\| propose \\| draft`. |
| `CP-BAD-CHANNEL`| BLOCKING-AUTO | a `channels` key outside `memory \\| feature \\| decision`. |
| `CP-UNRATIFIED` | BLOCKING-AUTO | a channel at level `off`/`propose` holds an entry with `confidence: unverified`, or `confidence: verified` with no `ratified` field — the policy says nothing lands there unratified. |

Config: `capture-policy.json` at the repo root (schema: `capture-policy.example.json`).
Missing config -> one-line message, exit 0. Unreadable/invalid JSON -> exit 2.

Follows `checks/TEMPLATE.md`: 5-field `Finding` namedtuple, two verdicts, 0/1/2 exit code.
Read-only. Fixes nothing — flags.

Usage:
  python3 checks/capture-policy-check.py
  python3 checks/capture-policy-check.py --json
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entrylib  # noqa: E402

BLOCKING = entrylib.BLOCKING
TO_CONFIRM = entrylib.TO_CONFIRM
Finding = entrylib.Finding

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # framework/project root
CONFIG_PATH = os.path.join(ROOT, "capture-policy.json")

LEVELS = {"off", "propose", "draft"}

# Channel -> glob pattern from ROOT (same flat-file layout as entrylib.CHANNELS'
# memory/feature/decision — backlog is deliberately out of scope, see mission).
CHANNEL_GLOBS = {
    "memory": os.path.join(ROOT, "memory", "*.md"),
    "feature": os.path.join(ROOT, "features", "*.md"),
    "decision": os.path.join(ROOT, "decisions", "D-*.md"),
}


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT)


# --------------------------------------------------------------------------- #
# Pure rules.                                                                  #
# --------------------------------------------------------------------------- #

def audit_bad_channel(channels: dict) -> list:
    """CP-BAD-CHANNEL — a `channels` key outside memory|feature|decision."""
    findings = []
    for key in channels:
        if key not in CHANNEL_GLOBS:
            findings.append(Finding(BLOCKING, "CP-BAD-CHANNEL", rel(CONFIG_PATH), 1,
                                     f"channels.{key} — unknown channel "
                                     f"(expected: {' | '.join(sorted(CHANNEL_GLOBS))})"))
    return findings


def audit_bad_level(channels: dict) -> list:
    """CP-BAD-LEVEL — a channel level outside off|propose|draft."""
    findings = []
    for key, level in channels.items():
        if level not in LEVELS:
            findings.append(Finding(BLOCKING, "CP-BAD-LEVEL", rel(CONFIG_PATH), 1,
                                     f"channels.{key} = « {level} » invalid "
                                     f"(expected: {' | '.join(sorted(LEVELS))})"))
    return findings


def audit_unratified(channels: dict) -> list:
    """CP-UNRATIFIED — an `off`/`propose` channel holds an entry that isn't a ratified,
    verified fact. `draft` produces nothing (the ratification inbox already covers it).
    A channel/level already flagged by CP-BAD-CHANNEL/CP-BAD-LEVEL is skipped here — no
    redundant finding on top of an already-reported misconfiguration."""
    findings = []
    for channel, level in channels.items():
        pattern = CHANNEL_GLOBS.get(channel)
        if pattern is None or level not in ("off", "propose"):
            continue
        for path in sorted(glob.glob(pattern)):
            text = open(path, encoding="utf-8").read()
            meta, _body, err = entrylib.parse_frontmatter(text)
            if err or "confidence" not in meta:
                continue
            confidence = meta.get("confidence")
            if confidence == "unverified":
                findings.append(Finding(BLOCKING, "CP-UNRATIFIED", rel(path), 1,
                                         f"channel « {channel} » is level « {level} » — only "
                                         "ratified entries may exist, but confidence: unverified"))
            elif confidence == "verified" and not meta.get("ratified"):
                findings.append(Finding(BLOCKING, "CP-UNRATIFIED", rel(path), 1,
                                         f"channel « {channel} » is level « {level} » — "
                                         "confidence: verified with no ratified field "
                                         "(ratification not tracked)"))
    return findings


# --------------------------------------------------------------------------- #
def main(argv) -> int:
    as_json = "--json" in argv

    if not os.path.isfile(CONFIG_PATH):
        print("capture-policy-check: no capture-policy.json at the repo root — "
              "the project has not opted into a capture policy.")
        print("  → copy capture-policy.example.json to capture-policy.json and adjust.")
        return 0

    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            policy = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        print(f"capture-policy-check: unreadable capture-policy.json ({e}).", file=sys.stderr)
        return 2

    channels = policy.get("channels") or {}
    findings = audit_bad_channel(channels) + audit_bad_level(channels) + audit_unratified(channels)
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
