#!/usr/bin/env python3
"""Deterministic DECISION LOG AUDIT orchestrator — agnostic (first tier).

The decision log should be audited periodically — the "Volume" trigger of the pruning
model fires when the INDEX grows large. The audit has TWO natures, handled separately
(same two-tier pattern as the rest of `checks/`):

  Tier 1 — THIS SCRIPT (mechanical, zero judgment, zero false positive):
    --tier1   runs the framework's integrity checks (decisions, backlog) and summarizes.
    --plan    splits `decisions/INDEX.md` into BALANCED batches -> offset/limit/ids per
              batch. (Removes manual splitting — one review per batch.) `--stale-first`
              prioritizes the batches whose frontmatter `updated` is oldest (each batch's
              offset/limit stays a contiguous range of lines — only the ORDER batches are
              presented in changes).
    --merge   aggregates review outputs (strict format `id | VERDICT | … | confidence:…`)
              -> classified report + COVERAGE CHECK (every id audited exactly once).
    (default) --tier1 then --plan + instructions.

  Tier 2 — SEMANTIC REVIEW (judgment): cross-checks each decision against the actual
            CODE (retrieve-then-verify), classifies vanished subject / migrated invariant
            / redundancy / memory<->code drift / conflict. Handled by the project's own
            review (an agent, the review skill, or a human). Scale: see `MEMORY.md` and
            `decisions/README.md`.

Scope = the decision log only. For the multi-channel audit (feature/decision/
preferences), see `memory-audit.py` (orchestrator, calls this one for its decisions
part).

The project brings its own CODE checks and its review. Here: the method, agnostic.

Read-only. Fixes/deletes/archives NOTHING. Ratification stays human — nothing is pruned
silently (cf. `MEMORY.md §Provenance`, `decisions/README.md §pruning`).

--report  writes a deterministic report (OS cron, no LLM): tier 1 + INDEX volume +
          a probe of the RATIFICATION INBOX (entries awaiting a human decision across
          all channels -- `memory-audit.py --pending`). Recommends a semantic audit on
          blocking drift, INDEX volume, inbox size, or inbox staleness -- see
          `PENDING_ALERT_COUNT` / `PENDING_ALERT_DAYS`.

Usage:
  python3 checks/decisions-audit.py                       # tier1 + plan
  python3 checks/decisions-audit.py --plan [--batch-size 33] [--stale-first] [--json]
  python3 checks/decisions-audit.py --merge review1.txt …  # aggregates + coverage
  python3 checks/decisions-audit.py --report [DIR]         # deterministic report (cron)
  python3 checks/decisions-audit.py --index <path/INDEX.md>   # another log
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # …/ai-workflow
CHECKS = os.path.dirname(os.path.abspath(__file__))
INDEX_DEFAULT = os.path.join(ROOT, "decisions", "INDEX.md")

ID_RE = re.compile(r"^(D-\d{4}-\d{2}-\d{2}-\d{2})\b")
# INDEX.md line, uniform entry-template format (`ENTRY-TEMPLATE.md`):
# "- [D-YYYY-MM-DD-NN](D-YYYY-MM-DD-NN.md) — <title> · <invariant>". Distinct from `ID_RE`
# above, which stays the format of REVIEW lines (`decisions-audit.md`), unchanged.
INDEX_LINE_RE = re.compile(r"^-\s*\[(D-\d{4}-\d{2}-\d{2}-\d{2})\]")
ANY_ID_RE = re.compile(r"D-\d{4}-\d{2}-\d{2}-\d{2}")
UPDATED_RE = re.compile(r"(?m)^updated:\s*(\d{4}-\d{2}-\d{2})")
VERDICTS = {"ARCHIVE-1", "ARCHIVE-4", "REDUNDANT", "CODE-DRIFT", "CONFLICT",
            "NOT-A-DECISION", "DOUBT"}

TIER1 = [
    ("decisions (file<->INDEX)",    "decisions-check.py"),
    ("backlog (process integrity)", "backlog-check.py"),
    ("dead doc refs",               "doc-refs-check.py"),
    ("index integrity",             "index-check.py"),
]


def parse_entries(index_path: str):
    if not os.path.isfile(index_path):
        return [], 0
    with open(index_path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    entries = [(i, INDEX_LINE_RE.match(l).group(1)) for i, l in enumerate(lines, 1)
               if INDEX_LINE_RE.match(l)]
    return entries, len(lines)


def _decision_updated(idv: str, decisions_dir: str):
    """`updated` frontmatter field of `decisions/<idv>.md`, or `None` (file/field
    absent). Deliberately lightweight regex (no `entrylib` import) — this script stays
    portable with no dependency, cf. `decisions-audit.md §Per-tool packaging`."""
    fpath = os.path.join(decisions_dir, idv + ".md")
    if not os.path.isfile(fpath):
        return None
    m = UPDATED_RE.search(open(fpath, encoding="utf-8").read())
    return m.group(1) if m else None


def make_batches(entries, total_lines, batch_size):
    batches = []
    for start in range(0, len(entries), batch_size):
        chunk = entries[start:start + batch_size]
        first = chunk[0][0]
        nxt = start + batch_size
        last = entries[nxt][0] - 1 if nxt < len(entries) else total_lines
        batches.append({"batch": len(batches) + 1, "offset": first,
                        "limit": last - first + 1, "count": len(chunk),
                        "ids": [e[1] for e in chunk]})
    return batches


def cmd_plan(index_path, batch_size, as_json, stale_first=False) -> int:
    entries, total = parse_entries(index_path)
    if not entries:
        print(f"PLAN: no decision in {os.path.relpath(index_path, ROOT)} "
              "(empty log — nothing to audit).")
        return 0
    batches = make_batches(entries, total, batch_size)
    if stale_first:
        # Prioritizes the batches containing the decisions with the oldest `updated` —
        # does NOT touch offset/limit (always a CONTIGUOUS range of lines, readable as
        # is): only the presentation ORDER of the batches changes.
        decisions_dir = os.path.dirname(index_path)
        for b in batches:
            dates = [d for d in (_decision_updated(i, decisions_dir) for i in b["ids"]) if d]
            b["oldest_updated"] = min(dates) if dates else None
        batches.sort(key=lambda b: (b["oldest_updated"] is None, b["oldest_updated"] or ""))
    if as_json:
        print(json.dumps({"entries": len(entries), "batches": batches},
                         ensure_ascii=False, indent=2))
        return 0
    print(f"AUDIT PLAN — {len(entries)} decisions, {len(batches)} batch(es) of ~{batch_size}"
          f"{' (sorted from stalest to freshest)' if stale_first else ''}.")
    print("Assign one batch per reviewer, with the given offset/limit:\n")
    for b in batches:
        stale = f"  — oldest: {b['oldest_updated'] or 'unknown'}" if stale_first else ""
        print(f"  Batch {b['batch']} — read offset={b['offset']} limit={b['limit']} "
              f"({b['count']} decisions: {b['ids'][0]} … {b['ids'][-1]}){stale}")
    print("\nThen: python3 checks/decisions-audit.py --merge <batch outputs…>")
    return 0


def cmd_tier1() -> int:
    print("TIER 1 — MEMORY INTEGRITY (mechanical, zero-FP)\n")
    worst = 0
    for label, script in TIER1:
        path = os.path.join(CHECKS, script)
        if not os.path.isfile(path):
            print(f"  ⨯ {label}: {script} missing — skipped")
            continue
        r = subprocess.run([sys.executable, path], cwd=ROOT, capture_output=True, text=True)
        worst = max(worst, r.returncode)
        mark = "OK " if r.returncode == 0 else ("?? " if r.returncode == 1 else "!! ")
        tail = (r.stdout.strip().splitlines() or [""])[-1]
        print(f"  [{mark}] {label}: exit={r.returncode}  {tail}")
    verdict = "OK" if worst == 0 else ("drift(s)" if worst >= 2 else "OK (to confirm)")
    print(f"\nTier 1 verdict: {verdict}.")
    return worst


def parse_review(text: str):
    flagged, kept = [], set()
    for line in text.splitlines():
        s = line.strip()
        if s.upper().startswith("KEPT"):
            kept.update(ANY_ID_RE.findall(s)); continue
        if "|" in s:
            parts = [p.strip() for p in s.split("|")]
            m = ID_RE.match(parts[0])
            if m and len(parts) >= 2 and parts[1] in VERDICTS:
                flagged.append((m.group(1), parts[1], " | ".join(parts[2:])))
    return flagged, kept


def cmd_merge(files, index_path) -> int:
    entries, _ = parse_entries(index_path)
    all_ids = {e[1] for e in entries}
    flagged, seen = [], {}
    for f in files:
        try:
            fl, ga = parse_review(open(f, encoding="utf-8").read())
        except OSError as e:
            print(f"⨯ unreadable: {f} ({e})", file=sys.stderr); continue
        for fid, v, rest in fl:
            flagged.append((fid, v, rest)); seen[fid] = seen.get(fid, 0) + 1
        for gid in ga:
            seen[gid] = seen.get(gid, 0) + 1

    print("AUDIT REPORT — aggregated\n")
    by_v = {}
    for fid, v, rest in flagged:
        by_v.setdefault(v, []).append((fid, rest))
    for v in ["CODE-DRIFT", "CONFLICT", "NOT-A-DECISION", "ARCHIVE-1", "ARCHIVE-4",
              "REDUNDANT", "DOUBT"]:
        if by_v.get(v):
            print(f"## {v}  ({len(by_v[v])})")
            for fid, rest in by_v[v]:
                print(f"  {fid} | {rest}")
            print()

    audited = set(seen)
    missing = sorted(all_ids - audited)
    dups = sorted(i for i, n in seen.items() if n > 1)
    print("## COVERAGE")
    print(f"  decisions in the INDEX: {len(all_ids)}  ·  audited: {len(audited & all_ids)}  "
          f"·  flagged: {len(flagged)}")
    rc = 0
    if missing:
        print(f"  !! NOT AUDITED ({len(missing)}): {' '.join(missing)}"); rc = 1
    if dups:
        print(f"  !! AUDITED >1x ({len(dups)}): {' '.join(dups)}"); rc = 1
    if not missing and not dups and all_ids:
        print("  OK full coverage: every decision audited exactly once.")
    print("\nReminder: this report FLAGS. No pruning without human ratification. "
          "Any pruning stays logged.")
    return rc


VOLUME_ALERTE = 285   # the INDEX is approaching the audit threshold (~300) -> recommend tier 2

# Ratification inbox (`memory-audit.py --pending`) — recommendation thresholds: an inbox
# this large, or this stale, alone justifies a semantic audit even with a clean tier 1.
PENDING_ALERT_COUNT = 5    # >= this many entries awaiting ratification -> recommend tier 2
PENDING_ALERT_DAYS = 30    # oldest pending entry's age (days) >= this -> recommend tier 2


def _report_dir(arg):
    """Report folder: argument > $YAMS_MEMORY_REPORT_DIR > default .memory-reports/ (to gitignore)."""
    d = arg or os.environ.get("YAMS_MEMORY_REPORT_DIR") or os.path.join(ROOT, ".memory-reports")
    return d if os.path.isabs(d) else os.path.join(ROOT, d)


def _pending_inbox():
    """Probes the ratification inbox (`memory-audit.py --pending --json`) via subprocess
    — deliberately, no `entrylib` import here either (cf. `_decision_updated`'s docstring:
    this script stays portable with no dependency). Tolerant like the rest of this file:
    ANY failure (script missing, non-zero exit for a reason other than "entries found",
    timeout, unparseable/non-list JSON) -> `None` (no inbox data) — the report is still
    written, just without a `## Ratification` verdict."""
    path = os.path.join(CHECKS, "memory-audit.py")
    if not os.path.isfile(path):
        return None
    try:
        r = subprocess.run([sys.executable, path, "--pending", "--json"], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30)
        rows = json.loads(r.stdout)
        return rows if isinstance(rows, list) else None
    except Exception:
        return None


def _pending_oldest_age_days(rows, today):
    """Age (days) of the OLDEST parseable `updated` among pending rows, or `None` if
    none is parseable. Rows with no/unparseable date are counted in `n_pending` (by the
    caller) but excluded here."""
    import datetime
    ages = []
    for row in rows:
        updated = row.get("updated")
        if not updated:
            continue
        try:
            d = datetime.date.fromisoformat(updated)
        except (ValueError, TypeError):
            continue
        ages.append((today - d).days)
    return max(ages) if ages else None


def cmd_report(report_dir) -> int:
    """Writes a deterministic report (tier 1 + INDEX volume + ratification inbox).
    Designed for an OS cron job (headless, NO LLM): the host surfaces it at session
    start, the user decides whether to act on it (tier 2)."""
    import datetime
    today_date = datetime.date.today()
    today = today_date.isoformat()
    results, worst = [], 0
    for label, script in TIER1:
        path = os.path.join(CHECKS, script)
        if not os.path.isfile(path):
            results.append((label, None, f"{script} missing")); continue
        r = subprocess.run([sys.executable, path], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        worst = max(worst, r.returncode)
        results.append((label, r.returncode, (r.stdout.strip().splitlines() or [""])[-1]))
    n_dec = len(parse_entries(INDEX_DEFAULT)[0])

    pending_rows = _pending_inbox()
    n_pending = len(pending_rows) if pending_rows is not None else 0
    oldest_age_days = (_pending_oldest_age_days(pending_rows, today_date)
                       if pending_rows else None)

    reasons = []
    if worst >= 2:
        reasons.append("blocking drift")
    if n_dec >= VOLUME_ALERTE:
        reasons.append(f"INDEX volume ({n_dec} >= {VOLUME_ALERTE})")
    if n_pending >= PENDING_ALERT_COUNT:
        reasons.append(f"ratification backlog ({n_pending} >= {PENDING_ALERT_COUNT})")
    if oldest_age_days is not None and oldest_age_days >= PENDING_ALERT_DAYS:
        reasons.append(f"stale ratification (oldest {oldest_age_days}d >= {PENDING_ALERT_DAYS}d)")
    recommend = bool(reasons)

    rdir = _report_dir(report_dir); os.makedirs(rdir, exist_ok=True)
    rpath = os.path.join(rdir, "memory-report.md")
    out = [f"# Memory report — {today}", "",
           "> Produced by the OS cron job (deterministic tier 1, **no LLM**). Handle it in",
           "> session: the agent asks, **the user decides**. Delete once handled.", "",
           "## Tier 1 — integrity", ""]
    for label, code, tail in results:
        mark = "[OK]" if code == 0 else ("[BLOCKING]" if (code or 0) >= 2
               else ("[to confirm]" if code == 1 else "[missing]"))
        out.append(f"- {mark} {label} — {tail}")
    out += ["", "## Decisions", "", f"- {n_dec} in the INDEX (alert >= {VOLUME_ALERTE}).", "",
            "## Ratification", ""]
    if pending_rows is None:
        out.append("- (ratification inbox unavailable — `memory-audit.py --pending` "
                    "could not be probed)")
    elif n_pending == 0:
        out.append("- (inbox empty)")
    else:
        age_txt = f"{oldest_age_days} day(s)" if oldest_age_days is not None else "unknown"
        out.append(f"- {n_pending} entrie(s) awaiting ratification (oldest: {age_txt}; "
                    f"alert >= {PENDING_ALERT_COUNT} entries or >= {PENDING_ALERT_DAYS}d).")
        out.append("- Run: `python3 checks/memory-audit.py --pending`")
    out += ["", "## Verdict", "",
            (f"**Semantic audit recommended** ({', '.join(reasons)}) — run tier 2 "
             "(decision<->code agents) then ratify."
             if recommend else "**Nothing urgent** — an audit is still possible on request."), ""]
    with open(rpath, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    print(f"report written: {rpath} (semantic audit {'recommended' if recommend else 'not required'})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Memory audit orchestrator (tier 1, agnostic).")
    ap.add_argument("--tier1", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--merge", nargs="+", metavar="FILE")
    ap.add_argument("--report", nargs="?", const="", metavar="DIR",
                    help="deterministic report (OS cron); DIR or $YAMS_MEMORY_REPORT_DIR or default .memory-reports/")
    ap.add_argument("--batch-size", type=int, default=33)
    ap.add_argument("--index", default=INDEX_DEFAULT)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stale-first", action="store_true",
                    help="--plan: prioritizes the batches containing the oldest `updated`")
    a = ap.parse_args()
    if a.report is not None:
        return cmd_report(a.report or None)
    if a.merge:
        return cmd_merge(a.merge, a.index)
    if a.plan and not a.tier1:
        return cmd_plan(a.index, a.batch_size, a.json, a.stale_first)
    if a.tier1 and not a.plan:
        return cmd_tier1()
    rc = cmd_tier1(); print(); cmd_plan(a.index, a.batch_size, False, a.stale_first)
    return rc


if __name__ == "__main__":
    sys.exit(main())
