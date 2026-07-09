#!/usr/bin/env python3
"""Deterministic MULTI-CHANNEL MEMORY AUDIT orchestrator — agnostic (tier 1).

Memory lives in three channels (`../WORKFLOW.md §The three memories`: Feature,
Decision, Memory) — each has its own integrity check (feature-map-check,
decisions-audit, memory-check). This script CHAINS them into a single pass and
summarizes, without duplicating their logic — same two-tier pattern as the rest of
`checks/`:

  Tier 1 — THIS SCRIPT (mechanical, zero judgment, zero false positive):
    --tier1   runs feature-map-check + decisions-audit --tier1 (which already covers
              decisions/doc/index/backlog itself) + memory-check, summarizes per
              channel. Replaces NONE of the three — delegates to them.
    (default) --tier1 then tier 2 instructions.

  The Feature/Memory per-channel summary is enriched, when it's simple, with fine
  counters useful for tier 2 (`memory-audit.md §Le flux`) — re-run from the underlying
  check's `--json`: `R-UNVERIFIED` / `R-VERIFIED-NOT-RATIFIED` (Memory channel),
  `FM-FRESH` / `FM-GRAN` (Feature channel). Tolerant by construction: `--json`
  unavailable, unreadable output, or missing field -> no counters, the summary falls
  back to the current count (exit code + last text line) without ever crashing.

  Tier 2 — SEMANTIC REVIEW (judgment), PER CHANNEL:
    - Decision — recipe + scale `decisions-audit.md` (the only channel that accumulates
      enough to justify splitting into batches — `decisions-audit.py --plan/--merge`).
    - Feature — every entry is reread IN FULL (FEATURE_MAP.md stays deliberately small
      enough for that, cf. WORKFLOW.md): does the entry still describe the reality of
      the cited code?
    - Memory — every `to-confirm` entry of MEMORY.md (flagged by memory-check.py) is
      cross-checked against the code/a reliable source, or ratified as is.
    Detailed scale for all three: see `memory-audit.md`.

The project brings its own CODE checks and its review. Here: the method, agnostic.

Read-only. Fixes/deletes/archives NOTHING. Ratification stays human.

Usage:
  python3 checks/memory-audit.py            # --tier1 + instructions
  python3 checks/memory-audit.py --tier1 [--json]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

CHECKS = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python3"

TIER1 = [
    ("feature",   [PY, os.path.join(CHECKS, "feature-map-check.py")]),
    ("decisions", [PY, os.path.join(CHECKS, "decisions-audit.py"), "--tier1"]),
    ("memory",    [PY, os.path.join(CHECKS, "memory-check.py")]),
]

# Optional fine counters per channel — a channel absent from this table (e.g.
# "decisions", already aggregated by decisions-audit.py) is simply not enriched. Keys =
# `entrylib`/channel rule ids, directly grep-able (same ids as `memory-audit.md`).
EXTRA_COUNTS = {
    "memory":  ("R-UNVERIFIED", "R-VERIFIED-NOT-RATIFIED"),
    "feature": ("FM-FRESH", "FM-GRAN"),
}


def _json_findings(cmd: list[str]):
    """Reruns `cmd` + `--json`, returns the `Finding` (dict) list — `None` if the check
    doesn't support `--json`, if the output isn't a JSON list, or on any other error
    (timeout, script missing…). Never raises — this is an enrichment, never a blocking
    path."""
    try:
        proc = subprocess.run(cmd + ["--json"], capture_output=True, text=True, timeout=30)
        data = json.loads(proc.stdout)
        return data if isinstance(data, list) else None
    except Exception:
        return None


def _channel_counts(label: str, cmd: list[str]) -> dict:
    """`{rule: n}` counters for the rules useful to this channel's tier 2 (see
    `EXTRA_COUNTS`). `{}` if the channel has no counters defined, or if
    `_json_findings` fails — then silently falls back to the current count (exit code +
    last line)."""
    rules = EXTRA_COUNTS.get(label)
    if not rules:
        return {}
    findings = _json_findings(cmd)
    if findings is None:
        return {}
    return {
        rule: sum(1 for f in findings if isinstance(f, dict) and f.get("rule") == rule)
        for rule in rules
    }


def run_tier1(as_json: bool) -> int:
    results = []
    worst = 0
    for label, cmd in TIER1:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        code = proc.returncode
        worst = max(worst, code)
        tail = (proc.stdout.strip().splitlines() or [""])[-1]
        entry = {"channel": label, "code": code, "summary": tail}
        counts = _channel_counts(label, cmd)
        if counts:
            entry["counts"] = counts
        results.append(entry)

    if as_json:
        print(json.dumps({"channels": results, "code": worst}, ensure_ascii=False, indent=2))
        return worst

    for r in results:
        mark = "[OK]" if r["code"] == 0 else ("[BLOCKING]" if r["code"] >= 2 else "[to confirm]")
        line = f"{mark} {r['channel']:10} {r['summary']}"
        if r.get("counts"):
            line += "  (" + ", ".join(f"{rule}={n}" for rule, n in r["counts"].items()) + ")"
        print(line)

    print()
    if worst == 0:
        print("Tier 1 clean on all 3 channels. Semantic audit possible on request.")
    elif worst == 1:
        print("To-confirm candidates — not blocking, but a tier 2 pass is recommended.")
    else:
        print("Blocking drift detected — fix before considering tier 2 (memory-audit.md).")
    return worst


def usage() -> int:
    print("usage: memory-audit.py [--tier1] [--json]", file=sys.stderr)
    print("  --tier1  runs the 4 integrity checks (feature, decisions, memory, backlog)", file=sys.stderr)
    print("  (default) equivalent to --tier1", file=sys.stderr)
    return 0


def main(argv) -> int:
    as_json = "--json" in argv
    return run_tier1(as_json)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
