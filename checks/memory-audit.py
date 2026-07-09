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
    --pending scans all four channels (memory/, features/, decisions/, backlog/)
              directly via `entrylib.parse_frontmatter` and lists the RATIFICATION
              INBOX: every entry awaiting a human decision — `confidence: unverified`
              (PENDING RATIFICATION) or `confidence: verified` with no `ratified`
              field (RATIFICATION NOT TRACKED). Today this exists only as scattered
              per-file `R-UNVERIFIED`/`R-VERIFIED-NOT-RATIFIED` findings inside each
              channel check — `--pending` is the single "what awaits me?" view.
              Each row also carries its age in days since `updated` (when parseable)
              and is flagged stale past `PENDING_STALE_DAYS` — so the inbox never
              becomes a silent graveyard of entries pending for months.
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
    Detailed scale for all three: see `memory-audit.md`. Before diving into tier 2,
    `--pending` is the fastest way to see everything that's waiting on a human first.

The project brings its own CODE checks and its review. Here: the method, agnostic.

Read-only. Fixes/deletes/archives NOTHING. Ratification stays human.

Global settings — `checks-config.json` at the repo root (optional, cf. `entrylib.py`):
  ("audit", "pending-stale-days")  <- DEFAULT_PENDING_STALE_DAYS (30) — same key drives
                                      `decisions-audit.py`'s `pending-alert-days`, kept
                                      intentionally shared (one "how stale is too stale"
                                      knob across both scripts).
A present-but-broken `checks-config.json` is surfaced as a BLOCKING `CFG-INVALID` line in
`--tier1` (config falls back to the default either way).

Usage:
  python3 checks/memory-audit.py            # --tier1 + instructions
  python3 checks/memory-audit.py --tier1 [--json]
  python3 checks/memory-audit.py --pending [--json]   # ratification inbox, all channels
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import subprocess
import sys

# Windows consoles default to cp1252: non-cp1252 output (→, ⨯…) would crash print().
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

CHECKS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CHECKS)  # framework root
PY = sys.executable or "python3"

sys.path.insert(0, CHECKS)
import entrylib  # noqa: E402

# Soft age threshold for --pending — an entry pending longer than this many days gets
# flagged stale in the inbox (never blocking: age alone is a nudge, not a rule). Keep
# consistent with decisions-audit.py's `pending-alert-days` (same config key,
# `("audit", "pending-stale-days")` here — cf. module docstring).
DEFAULT_PENDING_STALE_DAYS = 30
_CFG, _CFG_ERR = entrylib.load_checks_config(ROOT)
PENDING_STALE_DAYS = entrylib.cfg_get(_CFG, ("audit", "pending-stale-days"),
                                       DEFAULT_PENDING_STALE_DAYS)

TIER1 = [
    ("feature",         [PY, os.path.join(CHECKS, "feature-map-check.py")]),
    ("decisions",       [PY, os.path.join(CHECKS, "decisions-audit.py"), "--tier1"]),
    ("memory",          [PY, os.path.join(CHECKS, "memory-check.py")]),
    ("capture-policy",  [PY, os.path.join(CHECKS, "capture-policy-check.py")]),
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
        proc = subprocess.run(cmd + ["--json"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30)
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
    if _CFG_ERR:
        results.append({"channel": "config", "code": 2, "summary": f"CFG-INVALID: {_CFG_ERR}"})
        worst = 2
    for label, cmd in TIER1:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
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


# --------------------------------------------------------------------------- #
# --pending — the ratification inbox: every entry awaiting a human decision,  #
# across all four channels, in one view. Scans directly via entrylib — no     #
# subprocess, no dependency on the per-channel checks' output format.         #
# --------------------------------------------------------------------------- #

# (channel label, glob pattern from ROOT) — glob rather than os.listdir so the backlog
# channel's `backlog/<id>/STATE.md` layout (one level deeper) is expressed the same way
# as the flat `memory/*.md` / `features/*.md` / `decisions/D-*.md` channels.
PENDING_GLOBS = [
    ("memory",   os.path.join(ROOT, "memory", "*.md")),
    ("feature",  os.path.join(ROOT, "features", "*.md")),
    ("decision", os.path.join(ROOT, "decisions", "D-*.md")),
    ("backlog",  os.path.join(ROOT, "backlog", "*", "STATE.md")),
]


def _pending_entries():
    """Yields `(channel, relpath, meta)` for every entry file across the four channels
    that has a parseable frontmatter AND a `confidence` key. Files with no frontmatter
    block, or with a frontmatter that carries no `confidence` at all, are silently
    skipped — that's the other checks' business (R-NO-FRONTMATTER, R-MISSING-KEY...),
    this view never errors on them."""
    for channel, pattern in PENDING_GLOBS:
        for path in sorted(glob.glob(pattern)):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            meta, _body, err = entrylib.parse_frontmatter(text)
            if err or "confidence" not in meta:
                continue
            yield channel, os.path.relpath(path, ROOT), meta


def _pending_sort_key(row: dict):
    """Oldest `updated` first, missing date last."""
    updated = row.get("updated")
    return (updated is None, updated or "")


def _age_days(updated, today=None) -> int | None:
    """Days elapsed since `updated` (a `YYYY-MM-DD` string). `None` if `updated` is
    missing or unparseable — never raises."""
    if not updated:
        return None
    try:
        then = datetime.date.fromisoformat(str(updated))
    except ValueError:
        return None
    today = today or datetime.date.today()
    return (today - then).days


def collect_pending():
    """Returns `(unverified, not_tracked)` — two lists of `{channel, path, updated,
    source, kind, age_days, stale}` dicts, each sorted oldest `updated` first (missing
    date last). `age_days` is `None` when `updated` is missing/unparseable — `stale` is
    then always `False`."""
    unverified, not_tracked = [], []
    for channel, path, meta in _pending_entries():
        confidence = meta.get("confidence")
        updated = meta.get("updated")
        age = _age_days(updated)
        row = {"channel": channel, "path": path, "updated": updated,
               "source": meta.get("source"), "age_days": age,
               "stale": age is not None and age > PENDING_STALE_DAYS}
        if confidence == "unverified":
            unverified.append({**row, "kind": "unverified"})
        elif confidence == "verified" and not meta.get("ratified"):
            not_tracked.append({**row, "kind": "not-tracked"})
    unverified.sort(key=_pending_sort_key)
    not_tracked.sort(key=_pending_sort_key)
    return unverified, not_tracked


def _print_pending_section(title: str, rows: list) -> None:
    print(f"{title}\n")
    if not rows:
        print("  (none)")
    else:
        for r in rows:
            line = (f"  {r['channel']:8} {r['path']:40} "
                    f"updated={r['updated'] or '?':10} source={r['source'] or '?'}")
            if r["stale"]:
                line += f"  ⚠ stale {r['age_days']}d"
            print(line)
    print()


def run_pending(as_json: bool) -> int:
    unverified, not_tracked = collect_pending()

    if as_json:
        print(json.dumps(unverified + not_tracked, ensure_ascii=False, indent=2))
        return 0 if not (unverified or not_tracked) else 1

    _print_pending_section("PENDING RATIFICATION — confidence: unverified", unverified)
    _print_pending_section("RATIFICATION NOT TRACKED — confidence: verified, no ratified field",
                            not_tracked)

    total = len(unverified) + len(not_tracked)
    stale_count = sum(1 for r in unverified + not_tracked if r["stale"])
    if total == 0:
        print("Ratification inbox empty — nothing awaiting a human decision.")
    else:
        summary = (f"{total} entrie(s) awaiting ratification — {len(unverified)} unverified, "
                   f"{len(not_tracked)} verified-but-untracked")
        if stale_count:
            summary += f", {stale_count} stale (> {PENDING_STALE_DAYS}d)"
        print(summary + ".")
    return 0 if total == 0 else 1


def main(argv) -> int:
    as_json = "--json" in argv
    if "--pending" in argv:
        return run_pending(as_json)
    return run_tier1(as_json)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
