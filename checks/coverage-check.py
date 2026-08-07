#!/usr/bin/env python3
"""A table that claims to cover an enumerated list is recounted against it.

**The failure this exists for.** A document enumerates items — findings, milestones,
decisions — and, higher up in the SAME document, a table says how they are dispatched into
batches, phases, owners. The table is written once, from the list, by hand; then the list
grows, or the dispatch is cut along an axis the list doesn't follow, and one item ends up in
no row at all. Nothing says so: the table is well-formed, the list is well-formed, and every
other check passes. The closure is then signed on the table's authority — "all N handled" —
because recounting by hand is exactly the step a reader skips.

Real incident (the host project that motivated this check): 17 findings, 5 batches cut by
source file, one finding living outside every cited file. It fell through, a later session
wrote "the 17 are handled" on the strength of the table, and a human question caught it. No
script could have: none knew the two sets existed.

**Why it is declarative, not clever.** Guessing which table covers which list would fire on
tables that claim nothing — and a check that cries wrongly is one you learn to ignore, which
is worse than no check. So nothing is inferred: the document DECLARES its two sets with HTML
comments, and this check is silent everywhere the markers are absent. Zero false positives by
construction, not by tuning.

    <!-- coverage-set: findings -->            ← before the enumerated list
    ## Findings
    ### 0. First one …
    ### 0 bis. Variant …

    <!-- coverage-check: findings; column: Findings -->   ← before the table
    | Batch | Subject | Findings | State |
    |---|---|---|---|
    | 1 | The blockers | 0, 0 bis | done |

    <!-- coverage-exempt: findings; ids: 9; reason: out of scope, declared -->

**Markers.** All three take `name` first — the set's identifier, free-form, scoped to its file.
- `coverage-set: <name>[; pattern: <regex>]` — opens the source set. Ids are captured from the
  lines that follow, until the next `coverage-set` or end of file, by `pattern` (one capture
  group). Default: a numbered heading — `### 12. …`, `### 0 bis. …`.
- `coverage-check: <name>; column: <header>` — the NEXT markdown table covers that set. The
  column is found by its header label; each cell is split on `,` `;` `/` and each piece
  trimmed of markdown emphasis. Parsing the table as a table is the point: a naive text scan
  would pick up ids from the Subject column and hide the very gap being looked for.
- `coverage-exempt: <name>; ids: <a, b>[; reason: …]` — items deliberately out of scope. A
  declared exemption is part of the document's claim, so it silences the finding, and `--json`
  reports it separately — never conflated with something covered.

**Beyond a verdict — the sets are the deliverable.** `--json` exposes the parsed sets (items,
per-row coverage, missing, exempt, unknown), because the question that follows "is anything
missing?" is always "what covers what?" — asked by a human, by an agent planning the next
batch, or by another tool. A check that only prints a verdict forces its caller to re-parse
the document it just parsed.

Two rules:
- `R-COVERAGE-GAP` (blocking) — an item of the set appears in no row and is not exempt. It
  cannot be a false positive: both sets are declared, the arithmetic is closed.
- `R-COVERAGE-UNKNOWN` (to-confirm) — a row cites an id absent from the set. Usually a typo or
  a stale row; occasionally a legitimate id the list names differently, hence to-confirm.

A `coverage-check` naming a set the file never declares, a declared set no table covers, an
unreadable pattern, a missing column — each is reported as `R-COVERAGE-DECL` (to-confirm)
rather than passed over: a marker that does nothing is a guard a reader believes is standing.

    python3 checks/coverage-check.py docs/            # a path, a folder
    python3 checks/coverage-check.py --diff --staged  # what changed / is about to land
    python3 checks/coverage-check.py docs/ --json     # the sets, machine-readable
"""
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

BLOCKING = "BLOCKING-AUTO"
CONFIRM = "TO-CONFIRM"
Finding = namedtuple("Finding", "severity rule path line msg")

FRAMEWORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A numbered heading of any level: `### 12. …`, `## 0 bis. …`. Non-greedy up to the first
# dot so a compound id (`0 bis`) survives, and the id may not contain a pipe — that would
# mean a table row was scanned as a heading.
DEFAULT_ITEM_PATTERN = r"^#{1,6}\s+([^.|]+)\."

MARKER_RE = re.compile(
    r"<!--\s*coverage-(set|check|exempt)\s*:\s*(.*?)\s*-->", re.IGNORECASE)
# Markdown emphasis and code ticks around an id in a cell: `**1**`, `` `0 bis` ``.
STRIP_RE = re.compile(r"^[\s*_`~]+|[\s*_`~]+$")
CELL_SPLIT_RE = re.compile(r"[,;/]")


def _args(raw: str) -> tuple:
    """`<name>; key: value; key: value` → (name, {key: value}). Keys are lowercased."""
    parts = [p.strip() for p in raw.split(";")]
    name = parts[0] if parts else ""
    opts = {}
    for p in parts[1:]:
        if ":" in p:
            k, _, v = p.partition(":")
            opts[k.strip().lower()] = v.strip()
    return name, opts


def _clean(cell: str) -> str:
    return STRIP_RE.sub("", cell)


def _split_row(line: str) -> list:
    """Cells of a markdown table row, pipes stripped. `|` inside code spans is not
    supported — no real table needs it, and guessing would defeat zero-FP."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [_clean(c) for c in s.split("|")]


def _is_separator(line: str) -> bool:
    return bool(re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", line)) and "-" in line


def parse_document(lines: list) -> dict:
    """Extracts every declared set and coverage table. Pure — no I/O, so tests call it
    directly. Returns {name: {...}} plus a `_decl` list of declaration problems."""
    sets, checks, exempts, decl = {}, [], {}, []

    # --- pass 1: the sets. A `coverage-set` owns the lines up to the next one.
    open_set = None
    for i, line in enumerate(lines):
        for kind, raw in MARKER_RE.findall(line):
            kind = kind.lower()
            name, opts = _args(raw)
            if kind == "set":
                if not name:
                    decl.append((i + 1, "coverage-set with no name"))
                    open_set = None
                    continue
                pat = opts.get("pattern", DEFAULT_ITEM_PATTERN)
                try:
                    rx = re.compile(pat)
                except re.error as e:
                    decl.append((i + 1, f"coverage-set `{name}`: unreadable pattern ({e})"))
                    open_set = None
                    continue
                if rx.groups < 1:
                    decl.append((i + 1, f"coverage-set `{name}`: pattern has no capture group"))
                    open_set = None
                    continue
                sets[name] = {"line": i + 1, "rx": rx, "items": [], "pattern": pat}
                open_set = name
            elif kind == "check":
                checks.append((i + 1, name, opts))
            elif kind == "exempt":
                ids = [_clean(x) for x in CELL_SPLIT_RE.split(opts.get("ids", "")) if _clean(x)]
                exempts.setdefault(name, []).extend(ids)
        if open_set:
            m = sets[open_set]["rx"].match(line)
            if m:
                item = _clean(m.group(1))
                if item and item not in sets[open_set]["items"]:
                    sets[open_set]["items"].append(item)

    # --- pass 2: each check binds to the NEXT table below its marker.
    for lineno, name, opts in checks:
        entry = {"line": lineno, "name": name, "column": opts.get("column", ""),
                 "rows": {}, "cited": []}
        if not name or name not in sets:
            decl.append((lineno, f"coverage-check `{name or '?'}`: no coverage-set declares "
                                 f"that name in this file"))
            continue
        if not entry["column"]:
            decl.append((lineno, f"coverage-check `{name}`: no `column:` given"))
            continue
        head = next((j for j in range(lineno, len(lines))
                     if lines[j].lstrip().startswith("|")), None)
        if head is None or head + 1 >= len(lines) or not _is_separator(lines[head + 1]):
            decl.append((lineno, f"coverage-check `{name}`: no markdown table follows"))
            continue
        headers = _split_row(lines[head])
        col = next((k for k, h in enumerate(headers)
                    if h.lower() == entry["column"].lower()), None)
        if col is None:
            decl.append((lineno, f"coverage-check `{name}`: no column `{entry['column']}` "
                                 f"(headers: {', '.join(headers)})"))
            continue
        for j in range(head + 2, len(lines)):
            if not lines[j].lstrip().startswith("|"):
                break
            cells = _split_row(lines[j])
            if col >= len(cells):
                continue
            ids = [_clean(x) for x in CELL_SPLIT_RE.split(cells[col]) if _clean(x)]
            entry["rows"][cells[0] or f"row{j - head - 1}"] = ids
            entry["cited"].extend(ids)
        sets[name]["check"] = entry

    for name, s in sets.items():
        s["exempt"] = [e for e in exempts.get(name, [])]
        if "check" not in s:
            decl.append((s["line"], f"coverage-set `{name}`: no coverage-check covers it"))

    for name in exempts:
        if name not in sets:
            decl.append((0, f"coverage-exempt `{name}`: no coverage-set declares that name"))

    return {"sets": sets, "decl": decl}


def rule_coverage(path: str, lines: list) -> list:
    """Pure rule — recounts each declared table against its declared list."""
    doc = parse_document(lines)
    findings = []
    for lineno, msg in doc["decl"]:
        findings.append(Finding(CONFIRM, "R-COVERAGE-DECL", path, lineno, msg))
    for name, s in doc["sets"].items():
        chk = s.get("check")
        if not chk:
            continue
        cited, exempt = set(chk["cited"]), set(s["exempt"])
        missing = [i for i in s["items"] if i not in cited and i not in exempt]
        unknown = [i for i in dict.fromkeys(chk["cited"]) if i not in s["items"]]
        for i in missing:
            findings.append(Finding(
                BLOCKING, "R-COVERAGE-GAP", path, chk["line"],
                f"`{name}`: item {i} is in no row of the table covering it "
                f"(and not declared exempt)"))
        for i in unknown:
            findings.append(Finding(
                CONFIRM, "R-COVERAGE-UNKNOWN", path, chk["line"],
                f"`{name}`: the table cites {i}, absent from the declared set"))
    return findings


def report(path: str, lines: list) -> dict:
    """The parsed sets, for `--json` — what covers what, not just what's missing."""
    doc = parse_document(lines)
    out = {}
    for name, s in doc["sets"].items():
        chk = s.get("check")
        cited = set(chk["cited"]) if chk else set()
        exempt = set(s["exempt"])
        out[name] = {
            "items": s["items"],
            "rows": chk["rows"] if chk else {},
            "covered": [i for i in s["items"] if i in cited],
            "missing": [i for i in s["items"] if i not in cited and i not in exempt],
            "exempt": [i for i in s["items"] if i in exempt] + [
                i for i in exempt if i not in s["items"]],
            "unknown": [i for i in dict.fromkeys(chk["cited"]) if i not in s["items"]]
                       if chk else [],
        }
    return out


def audit_file(path: str) -> list:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    if "coverage-" not in "\n".join(lines):
        return []          # untouched documents cost one substring scan, no parsing
    return rule_coverage(path, lines)


def git_diff_names(staged: bool) -> list:
    cmd = ["git", "diff", "--name-only", "--diff-filter=ACM"]
    if staged:
        cmd.insert(2, "--cached")
    try:
        repo = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=FRAMEWORK,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=10).stdout.strip() or FRAMEWORK
        out = subprocess.run(cmd, cwd=repo, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=30).stdout
    except Exception:
        return []
    return [os.path.join(repo, p.strip()) for p in out.splitlines() if p.strip().endswith(".md")]


def walk(root: str) -> list:
    found = []
    for dpath, dnames, fnames in os.walk(root):
        dnames[:] = [d for d in dnames if not d.startswith(".") and d != "node_modules"]
        found += [os.path.join(dpath, f) for f in fnames if f.endswith(".md")]
    return found


def collect(targets: list, diff: bool, staged: bool) -> list:
    raw = []
    if diff:
        raw += git_diff_names(staged=False)
    if staged:
        raw += git_diff_names(staged=True)
    for t in targets:
        raw += walk(t) if os.path.isdir(t) else [t]
    seen, out = set(), []
    for p in raw:
        rp = os.path.realpath(p)
        if rp not in seen and os.path.isfile(rp) and rp.endswith(".md"):
            seen.add(rp)
            out.append(p)
    return out


def main(argv) -> int:
    as_json = "--json" in argv
    diff = "--diff" in argv
    staged = "--staged" in argv
    targets = [a for a in argv if not a.startswith("--")]
    if not (targets or diff or staged):
        print("usage: coverage-check.py <path...> | --diff | --staged [--json]",
              file=sys.stderr)
        return 0

    paths = collect(targets, diff, staged)
    findings, sets = [], {}
    for path in paths:
        findings += audit_file(path)
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        if "coverage-" in "\n".join(lines):
            r = report(path, lines)
            if r:
                sets[path] = r

    bloq = [f for f in findings if f.severity == BLOCKING]
    conf = [f for f in findings if f.severity == CONFIRM]

    if as_json:
        print(json.dumps({"findings": [f._asdict() for f in findings], "sets": sets},
                         ensure_ascii=False, indent=2))
    else:
        for f in sorted(findings, key=lambda f: (f.severity != BLOCKING, f.path, f.line)):
            print(f"{f.severity:14} {f.path}:{f.line}  {f.rule}  {f.msg}")
        if not findings:
            n = sum(len(v) for v in sets.values())
            print(f"coverage-check: OK — {n} declared set(s) recounted, no gap."
                  if n else "coverage-check: no declared set in scope — nothing verified.")
        else:
            print(f"\n— {len(findings)} finding(s): {len(bloq)} blocking-auto, "
                  f"{len(conf)} to-confirm")

    return 2 if bloq else (1 if conf else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
