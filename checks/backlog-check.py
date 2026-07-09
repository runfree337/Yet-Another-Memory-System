#!/usr/bin/env python3
"""Deterministic backlog check (zero false positive), agnostic.

Mechanically verifies the invariants of `backlog/README.md` — fixes NOTHING, **flags**.
First tier of the two-tier pattern (script -> semantic review). Format: a doc-backed work
item = a **subfolder** `backlog/<id>/` whose `STATE.md` opens with a **frontmatter** with
English keys (`id/title/status/milestone/after/docs/updated`) — instance of
`ENTRY-TEMPLATE.md` (channel "backlog"), generalized via `entrylib.py` like
`feature-map-check.py`. The `INDEX.md` line of a doc-backed item carries only title +
target + gist (no badge); an inline item (no doc) keeps its `[todo]`/`[in-progress]`
badge. Two tiers: inline / subfolder.

Follows `checks/TEMPLATE.md`: 5-field `Finding` namedtuple, two verdicts, pure rules.

Rules:
  (R-*)          (see entrylib) `entrylib.validate_entry(path, meta, "backlog")` per STATE.md —
                                  `R-NO-FRONTMATTER`, `R-MISSING-KEY`, `R-BAD-VALUE`,
                                  `R-EXT-NO-CONF`, `R-UNVERIFIED`, `R-VERIFIED-NOT-RATIFIED`,
                                  `R-BAD-DATE` ; `entrylib.check_links` for `links:` —
                                  `R-DEAD-LINK`.
  E-STATE-MISSING (BLOCKING)     `backlog/<id>/` subfolder with no STATE.md.
  E-ID           (BLOCKING)      frontmatter `id` != folder name.
  E-ID-KEBAB     (BLOCKING)      frontmatter `id` not kebab-case.
  E-ID-DUP       (BLOCKING)      `id` already used by another work item.
  E-MILESTONE    (BLOCKING)      frontmatter `milestone` != INDEX `### Milestone N` group.
  E-AFTER        (BLOCKING)      `after:` points to a work item id that doesn't exist.
  E-DOCS         (BLOCKING)      `docs:` != exactly the folder's companion `.md` files.
  E-TASK-SECTION (BLOCKING)      `## Tasks` section absent from STATE.md.
  E-TASK-STATE   (BLOCKING)      task state outside `todo|in-progress|blocked|done`.
  E-TASK-LEN     (BLOCKING)      task label > 30 words WITHOUT a referenced working document
                                  (simple word count: the `[state]` badge and `→ doc.md`
                                  excluded).
  E-TASK-REF     (BLOCKING)      referenced working document (`→ doc.md`) not found in the
                                  work item's folder.
  E-TASK-SYNC    (TO-CONFIRM)    work item <-> tasks mismatch: all `done` but work item
                                  `todo`/`in-progress` (a "ready to close" signal) — or the
                                  reverse, work item `in-progress` with no task started at
                                  all.
  E-IMPACT       (BLOCKING)      `impacts:` entry that is neither a target path (contains `/`
                                  or `.`, no existence requirement — it may be a doc to
                                  CREATE at closure) nor one of the channel keywords
                                  `decision | feature | memory` — closed vocabulary.
  E-IMPACT-EMPTY (TO-CONFIRM)    every task `done` and `impacts` absent/empty — "ready to
                                  close with no declared durable impact — really nothing to
                                  migrate?". Never fires while tasks remain open.
  E-STATE-SIZE   (TO-CONFIRM)    STATE.md > 80 lines — candidate for "durable content living
                                  in the state file" (soft anti-accumulation guard, never
                                  blocking).
  E-STATE-SECTION(TO-CONFIRM)    `## …` heading outside the canonical sections
                                  (`Tasks`/`Remaining`) — soft, never blocking.
  I-FLAT         (BLOCKING)      flat `.md` file at the top level of `backlog/` (other than
                                  `INDEX.md`/`README.md`/`STATE.template.md`) — abandoned
                                  tier.
  I-ORPHAN       (BLOCKING)      `backlog/<id>/` folder cited nowhere in `INDEX.md`.
  I-DEAD-POINTER (BLOCKING)      `` `<id>/` `` or `` `<file>.md` `` pointer in `INDEX.md`
                                  that resolves to nothing.
  I-CHECKBOX     (BLOCKING)      Markdown checkbox `- [ ]`/`- [x]` in `INDEX.md` (done =
                                  removed; status = frontmatter for doc-backed items, badge
                                  for the others).

Views: `--board` (work items by milestone, status + task counts by state) · `--state <id>`
(one work item, tasks unrolled, `impacts:` listed). Both accept `--json`. `--checklist [<id>]`
emits the closure template (DoD, `backlog/README.md`) — when `<id>` declares `impacts:`, the
**Durable** step enumerates them instead of the generic wording.

`--stamp [files…]` / `--stamp --staged`: sets `updated: <today>` via
`entrylib.stamp_updated` on the cited `STATE.md` files (or staged ones with `--staged`,
strict `backlog/**/STATE.md` scope, re-stages with git after writing) — same triple
safeguard as `feature-map-check.py --stamp`: strict staged scope, a single mechanical
field, never blocking.

Usage:
  python3 checks/backlog-check.py                     # text report
  python3 checks/backlog-check.py --json               # JSON findings output
  python3 checks/backlog-check.py --board               # overview
  python3 checks/backlog-check.py --state <id>           # one work item, unrolled
  python3 checks/backlog-check.py --stamp --staged        # pre-commit only
  python3 checks/backlog-check.py --checklist [<id>]        # closure template (DoD)
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
BACKLOG = os.path.join(ROOT, "backlog")
INDEX_PATH = os.path.join(BACKLOG, "INDEX.md")

# Structural names at the backlog's top level — never work item pointers.
STRUCTURAL = {"STATE.md", "INDEX.md", "README.md", "STATE.template.md"}

KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

TASK_STATES = {"todo", "in-progress", "blocked", "done"}
TASK_LABEL_MAX_WORDS = 30
STATE_SIZE_MAX_LINES = 80
CANON_SECTIONS = {"Tasks", "Remaining"}

# `impacts:` closed vocabulary — a channel keyword or a target path (see check_impacts).
IMPACT_KEYWORDS = {"decision", "feature", "memory"}

# DoD (cf. backlog/README.md). `{target}` = the work item to remove. Step 1 is a CHECK
# (capitalization already happened task by task), not heavy lifting.
CLOSURE_STEPS = [
    ("Durable", "check that no durable content is left unmigrated (STATE.md never carries "
                "any) — otherwise migrate it now to its home + the affected memories"),
    ("Decision", "log the decision if the closure settles a structural choice"),
    ("Backlog", "delete {target} **+ its line in `INDEX.md`**"),
    ("State", "update `DASHBOARD.md`: progress of the affected milestone, hot spots"),
    ("Capitalization", "ask the question \"reusable method learning?\" and route if so"),
]


def _durable_step_wording(impacts):
    """Enumerates a work item's declared `impacts:` for the closure checklist's Durable
    step — paths to update/migrate, channel keywords to record. `None`/empty -> `None`
    (caller falls back to the generic wording)."""
    if not impacts:
        return None
    paths = [x for x in impacts if x not in IMPACT_KEYWORDS]
    keywords = [x for x in impacts if x in IMPACT_KEYWORDS]
    parts = []
    if paths:
        parts.append("update/migrate: " + ", ".join(paths))
    if keywords:
        parts.append("record: " + ", ".join(keywords))
    return " ; ".join(parts) if parts else None


def closure_checklist(target="the work item's folder", impacts=None):
    head = "Closure checklist (DoD — `backlog/README.md`):"
    rows = []
    for i, (t, d) in enumerate(CLOSURE_STEPS, 1):
        desc = d.format(target=target)
        if t == "Durable":
            desc = _durable_step_wording(impacts) or desc
        rows.append(f"  [ ] {i}. **{t}** — {desc}")
    return "\n".join([head, *rows])


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT)


# --------------------------------------------------------------------------- #
# Parsing the STATE.md body — H2 headings + tasks in the `Tasks` section       #
# --------------------------------------------------------------------------- #

H2 = re.compile(r"^##\s+(.+?)\s*$")
TOP_BULLET = re.compile(r"^-\s+(.*)$")           # top-level bullet (no indent)
TASK_BADGE = re.compile(r"^\[(?P<state>[^\]]*)\]\s*(?P<rest>.*)$")
DOC_REF = re.compile(r"→\s*(\S+)\s*$")


def parse_state(text):
    """Returns (headings: [(lineno, title)], sections: {title: [(lineno, bullet_content)]})."""
    headings, sections, current = [], {}, None
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = H2.match(line)
        if m:
            current = m.group(1).strip()
            headings.append((lineno, current))
            sections.setdefault(current, [])
            continue
        if current is not None:
            bm = TOP_BULLET.match(line)
            if bm:
                sections[current].append((lineno, bm.group(1)))
    return headings, sections


def parse_task(content):
    """A task line (leading `- ` already stripped) -> (state, label, doc_ref|None)."""
    m = TASK_BADGE.match(content)
    state = m.group("state").strip() if m else ""
    rest = m.group("rest").strip() if m else content.strip()
    dm = DOC_REF.search(rest)
    if dm:
        doc = dm.group(1).strip("`")
        label = rest[:dm.start()].strip()
    else:
        doc = None
        label = rest.strip()
    return state, label, doc


# --------------------------------------------------------------------------- #
# Parsing INDEX.md — milestone per work item                                  #
# --------------------------------------------------------------------------- #

H3_MILESTONE = re.compile(r"^###\s+Milestone\s+(\d+)")
H3_ANY = re.compile(r"^###\s+")
H2_ANY = re.compile(r"^##\s+")
ENTRY_TOK = re.compile(r"→\s*`([\w.\-]+)/`")  # canonical entry « → `<id>/` »


def index_milestone_map(index_text):
    """Current group = the last `### Milestone N` seen; any other heading
    (`### Unplanned`, or a higher-level `##`) resets it to `None` — otherwise a work item
    under "Unplanned" would wrongly inherit the last numbered milestone seen earlier in
    the file."""
    mapping, current = {}, None
    for line in index_text.splitlines():
        mj = H3_MILESTONE.match(line)
        if mj:
            current = int(mj.group(1))
            continue
        if H3_ANY.match(line) or H2_ANY.match(line):
            current = None
            continue
        if line.lstrip().startswith("- "):
            m = ENTRY_TOK.search(line)
            if m:
                mapping.setdefault(m.group(1).rstrip("/"), current)
    return mapping


def _norm_milestone(v):
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    return int(s) if re.fullmatch(r"-?\d+", s) else s


# --------------------------------------------------------------------------- #
# `impacts:` — the impact ledger (filled during work, consumed at closure)     #
# --------------------------------------------------------------------------- #

def check_impacts(path: str, meta: dict) -> list[Finding]:
    """Validates the `impacts:` frontmatter entries of a work item.

    Each entry is either a **target path** (contains `/` or `.` — no existence
    requirement, it may be a doc to CREATE at closure) or a **channel keyword** in
    `IMPACT_KEYWORDS`. Anything else is `E-IMPACT` (closed vocabulary, zero-FP)."""
    findings = []
    impacts = meta.get("impacts") or []
    if isinstance(impacts, str):
        impacts = [impacts]
    for imp in impacts:
        imp = str(imp).strip()
        if not imp or "/" in imp or "." in imp or imp in IMPACT_KEYWORDS:
            continue
        findings.append(Finding(BLOCKING, "E-IMPACT", path, 1,
                                 f"unknown impact « {imp} » — a path or one of: "
                                 f"{', '.join(sorted(IMPACT_KEYWORDS))}."))
    return findings


# --------------------------------------------------------------------------- #
# A work item — frontmatter (entrylib) + tasks + safeguards                   #
# --------------------------------------------------------------------------- #

def collect_work_items():
    if not os.path.isdir(BACKLOG):
        return []
    return [(n, os.path.join(BACKLOG, n)) for n in sorted(os.listdir(BACKLOG))
            if os.path.isdir(os.path.join(BACKLOG, n)) and not n.startswith(".")]


def check_work_item(cid, cdir, ids, milestone_map, seen_ids) -> list[Finding]:
    findings: list[Finding] = []
    state_path = os.path.join(cdir, "STATE.md")
    state_rel = rel(state_path)
    if not os.path.isfile(state_path):
        findings.append(Finding(BLOCKING, "E-STATE-MISSING", rel(cdir), 1,
                                 "work item subfolder with no STATE.md."))
        return findings

    with open(state_path, encoding="utf-8") as f:
        text = f.read()

    meta, body, err = entrylib.parse_frontmatter(text)
    findings += entrylib.validate_entry(state_rel, meta, "backlog")
    findings += entrylib.check_links(state_rel, meta, ROOT)
    findings += check_impacts(state_rel, meta)

    headings, sections = parse_state(text)

    # E-ID / E-ID-KEBAB / E-ID-DUP
    fid = meta.get("id")
    if fid != cid:
        findings.append(Finding(BLOCKING, "E-ID", state_rel, 1,
                                 f"frontmatter `id: {fid}` != folder name « {cid} »."))
    if isinstance(fid, str) and not KEBAB.match(fid):
        findings.append(Finding(BLOCKING, "E-ID-KEBAB", state_rel, 1,
                                 f"frontmatter `id: {fid}` is not kebab-case."))
    if fid is not None:
        if fid in seen_ids:
            findings.append(Finding(BLOCKING, "E-ID-DUP", state_rel, 1,
                                     f"id « {fid} » already used by « {seen_ids[fid]} »."))
        else:
            seen_ids[fid] = cid

    # E-MILESTONE
    milestone = _norm_milestone(meta.get("milestone"))
    if cid in milestone_map and milestone != milestone_map[cid]:
        expected = milestone_map[cid]
        a = "null (Unplanned)" if expected is None else str(expected)
        m = "null" if milestone is None else str(milestone)
        findings.append(Finding(BLOCKING, "E-MILESTONE", state_rel, 1,
                                 f"frontmatter `milestone: {m}` but the INDEX files this work "
                                 f"item under « {a} »."))

    # E-AFTER
    for dep in (meta.get("after") or []):
        if dep not in ids:
            findings.append(Finding(BLOCKING, "E-AFTER", state_rel, 1,
                                     f"frontmatter `after` points to « {dep} » — no work item by that name."))

    # E-DOCS
    declared = set(meta.get("docs") or [])
    actual = {fn for fn in os.listdir(cdir) if fn.endswith(".md") and fn != "STATE.md"}
    if declared != actual:
        det = []
        if actual - declared:
            det.append("undeclared: " + ", ".join(sorted(actual - declared)))
        if declared - actual:
            det.append("nonexistent: " + ", ".join(sorted(declared - actual)))
        findings.append(Finding(BLOCKING, "E-DOCS", state_rel, 1,
                                 "frontmatter `docs:` != folder companions (" + " ; ".join(det) + ")."))

    # E-STATE-SECTION (soft) — any heading outside Tasks/Remaining
    for lineno, h in headings:
        if h not in CANON_SECTIONS:
            findings.append(Finding(TO_CONFIRM, "E-STATE-SECTION", state_rel,
                                     lineno, f"heading « ## {h} » outside the canonical sections "
                                     "(Tasks/Remaining) — candidate for \"durable content living "
                                     "in the state file\"."))

    # E-STATE-SIZE (soft)
    nb_lines = len(text.splitlines())
    if nb_lines > STATE_SIZE_MAX_LINES:
        findings.append(Finding(TO_CONFIRM, "E-STATE-SIZE", state_rel, 1,
                                 f"{nb_lines} lines (> {STATE_SIZE_MAX_LINES}) — candidate for "
                                 "\"durable content living in the state file\", should be emptied "
                                 "into its durable home."))

    # E-TASK-SECTION + tasks
    if "Tasks" not in sections:
        findings.append(Finding(BLOCKING, "E-TASK-SECTION", state_rel, 1,
                                 "`## Tasks` section absent (mandatory, `backlog/README.md`)."))
    else:
        counts = {s: 0 for s in TASK_STATES}
        total = 0
        for lineno, raw in sections["Tasks"]:
            state, label, doc = parse_task(raw)
            total += 1
            if state not in TASK_STATES:
                findings.append(Finding(BLOCKING, "E-TASK-STATE", state_rel, lineno,
                                         f"task state « {state or '(absent)'} » outside "
                                         "todo|in-progress|blocked|done."))
            else:
                counts[state] += 1
            if doc is None and len(label.split()) > TASK_LABEL_MAX_WORDS:
                findings.append(Finding(BLOCKING, "E-TASK-LEN", state_rel, lineno,
                                         f"{len(label.split())}-word label (> {TASK_LABEL_MAX_WORDS}) "
                                         "with no referenced working document (`→ doc.md`)."))
            if doc is not None and not os.path.isfile(os.path.join(cdir, doc)):
                findings.append(Finding(BLOCKING, "E-TASK-REF", state_rel, lineno,
                                         f"working document « {doc} » not found in "
                                         f"{rel(cdir)}/."))

        status = meta.get("status")
        started = any(counts[s] for s in ("in-progress", "blocked", "done"))
        all_done = total > 0 and counts["done"] == total
        if all_done and status in ("todo", "in-progress"):
            findings.append(Finding(TO_CONFIRM, "E-TASK-SYNC", state_rel, 1,
                                     f"every task is `done` but work item `status: {status}` "
                                     "— ready to close?"))
        if status == "in-progress" and not started:
            findings.append(Finding(TO_CONFIRM, "E-TASK-SYNC", state_rel, 1,
                                     "work item `status: in-progress` with no task started at all."))
        if all_done and not (meta.get("impacts") or []):
            findings.append(Finding(TO_CONFIRM, "E-IMPACT-EMPTY", state_rel, 1,
                                     "ready to close with no declared durable impact — really "
                                     "nothing to migrate?"))

    return findings


# --------------------------------------------------------------------------- #
# INDEX.md — orphans, dead pointers, Markdown checkboxes                      #
# --------------------------------------------------------------------------- #

def check_index(work_items, index_text) -> list[Finding]:
    findings: list[Finding] = []
    ids = {cid for cid, _ in work_items}

    for name in sorted(os.listdir(BACKLOG)) if os.path.isdir(BACKLOG) else []:
        if name in STRUCTURAL or name.startswith("."):
            continue
        full = os.path.join(BACKLOG, name)
        if os.path.isfile(full) and name.endswith(".md"):
            findings.append(Finding(BLOCKING, "I-FLAT", rel(full), 1,
                                     "flat .md file at the backlog's top level — a work item = "
                                     "a `<id>/` subfolder with STATE.md (abandoned tier)."))

    for cid, cdir in work_items:
        # Substring test on purpose (any mention counts as "cited"). Assumed false
        # negative: an orphan whose id is a prefix of another cited id slips through —
        # zero-FP wins over recall here.
        if (cid + "/") not in index_text and cid not in index_text:
            findings.append(Finding(BLOCKING, "I-ORPHAN", rel(cdir), 1,
                                     f"« {cid}/ » is cited nowhere in INDEX.md."))

    basenames, reldirs = set(), set()
    for _dp, dirs, files in os.walk(BACKLOG):
        basenames.update(files)
        reldirs.update(dirs)
    for lineno, line in enumerate(index_text.splitlines(), start=1):
        for tok in re.findall(r"`([^`]+)`", line):
            tok = tok.strip()
            if "<" in tok or ">" in tok or tok in STRUCTURAL:
                continue
            if re.fullmatch(r"[\w.\-]+\.md", tok) and tok not in basenames:
                findings.append(Finding(BLOCKING, "I-DEAD-POINTER", rel(INDEX_PATH),
                                         lineno, f"pointer « {tok} » resolves to no file "
                                         "in the backlog."))
            elif re.fullmatch(r"[\w.\-]+/", tok):
                name_ = tok.rstrip("/")
                if name_ not in reldirs and name_ not in ids:
                    findings.append(Finding(BLOCKING, "I-DEAD-POINTER", rel(INDEX_PATH),
                                             lineno, f"pointer « {tok} » resolves to no existing "
                                             "folder."))
        if re.match(r"^\s*[-*]\s*\[[ xX]\]", line):
            findings.append(Finding(BLOCKING, "I-CHECKBOX", rel(INDEX_PATH), lineno,
                                     "Markdown checkbox in the INDEX — remove `[ ]`/`[x]` (done = "
                                     "removed; status = frontmatter or inline badge)."))
    return findings


# --------------------------------------------------------------------------- #
# --stamp — sets `updated` alone, never blocking                              #
# --------------------------------------------------------------------------- #

def cmd_stamp(argv: list[str]) -> int:
    """Sets `updated: today` on the cited STATE.md files (or staged ones with `--staged`) +
    re-stages. Same triple safeguard as `feature-map-check.py --stamp`: strict staged
    scope (`backlog/**/STATE.md` only), a single mechanical field
    (`entrylib.stamp_updated` only touches `updated`), never blocking (exit code always 0)."""
    today = datetime.date.today().isoformat()
    staged = "--staged" in argv
    if staged:
        r = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                            cwd=ROOT, capture_output=True, text=True)
        files = [f for f in r.stdout.splitlines()
                 if f.replace("\\", "/").startswith("backlog/")
                 and os.path.basename(f.replace("\\", "/")) == "STATE.md"]
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
    print(f"backlog-check: --stamp — {len(changed)} STATE.md stamped {today}.")
    return 0


# --------------------------------------------------------------------------- #
# --board / --state views                                                     #
# --------------------------------------------------------------------------- #

TASK_STATE_DISPLAY_ORDER = ["done", "in-progress", "blocked", "todo"]


def work_item_ids():
    return [cid for cid, _ in collect_work_items()]


def work_item_state(cid):
    cdir = os.path.join(BACKLOG, cid)
    state_path = os.path.join(cdir, "STATE.md")
    if not os.path.isdir(cdir) or not os.path.isfile(state_path):
        return None
    with open(state_path, encoding="utf-8") as f:
        text = f.read()
    meta, _body, _err = entrylib.parse_frontmatter(text)
    _headings, sections = parse_state(text)
    counts = {s: 0 for s in TASK_STATES}
    tasks = []
    for lineno, raw in sections.get("Tasks", []):
        state, label, doc = parse_task(raw)
        if state in TASK_STATES:
            counts[state] += 1
        tasks.append({"line": lineno, "state": state, "label": label, "doc": doc})
    return {
        "id": meta.get("id", cid), "title": meta.get("title"), "status": meta.get("status"),
        "milestone": _norm_milestone(meta.get("milestone")), "updated": meta.get("updated"),
        "docs": meta.get("docs") or [], "impacts": meta.get("impacts") or [],
        "tasks": tasks, "task_counts": counts,
        "remaining": [content for _, content in sections.get("Remaining", [])],
    }


def _task_counts_suffix(counts):
    parts = [f"{counts[s]} {s}" for s in TASK_STATE_DISPLAY_ORDER if counts.get(s)]
    return " / ".join(parts)


def render_state(cid):
    st = work_item_state(cid)
    if st is None:
        available = ", ".join(work_item_ids()) or "(none)"
        return f"[backlog-check] work item « {cid} » not found (backlog/{cid}/STATE.md).\nWork items: {available}"
    milestone_label = "Unplanned" if st["milestone"] is None else f"Milestone {st['milestone']}"
    lines = [f"Work item {st['id']} — {st['title']}",
             f"  status : {st['status']}   ·   {milestone_label}   ·   updated {st['updated']}"]
    suffix = _task_counts_suffix(st["task_counts"])
    lines.append("  tasks  : " + (suffix if suffix else "—"))
    if st["docs"]:
        lines.append("  docs   : " + ", ".join(st["docs"]))
    if st["impacts"]:
        lines.append("  impacts: " + ", ".join(st["impacts"]))
    lines.append(f"\n## Tasks ({len(st['tasks'])})")
    for t in st["tasks"]:
        tail = f" → {t['doc']}" if t["doc"] else ""
        lines.append(f"  - [{t['state']}] {t['label']}{tail}")
    if st["remaining"]:
        lines.append(f"\n## Remaining ({len(st['remaining'])})")
        lines.extend("  " + it for it in st["remaining"])
    return "\n".join(lines)


def render_board():
    rows = [work_item_state(cid) or {"id": cid} for cid in work_item_ids()]
    if not rows:
        return "[backlog-check] no doc-backed work item."
    rows.sort(key=lambda s: (s.get("milestone") is None,
                              s.get("milestone") if s.get("milestone") is not None else 0, s.get("id")))
    icon = {"todo": "○", "in-progress": "◐"}
    lines, cur = ["Backlog — work items by milestone (live statuses):"], object()
    for s in rows:
        milestone = s.get("milestone")
        grp = "Unplanned" if milestone is None else f"Milestone {milestone}"
        if grp != cur:
            cur = grp
            lines.append(f"\n### {grp}")
        status = s.get("status") or "?"
        line = f"  {icon.get(status, '·')} [{status}] {s.get('id')} — {s.get('title') or s.get('id')}"
        suffix = _task_counts_suffix(s.get("task_counts") or {})
        if suffix:
            line += f"   ({suffix})"
        lines.append(line)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Rendering / CLI                                                              #
# --------------------------------------------------------------------------- #

def run() -> list[Finding]:
    work_items = collect_work_items()
    index_text = ""
    if os.path.isfile(INDEX_PATH):
        with open(INDEX_PATH, encoding="utf-8") as f:
            index_text = f.read()
    ids = {cid for cid, _ in work_items}
    milestone_map = index_milestone_map(index_text)
    seen_ids: dict = {}

    findings: list[Finding] = []
    for cid, cdir in work_items:
        findings += check_work_item(cid, cdir, ids, milestone_map, seen_ids)
    findings += check_index(work_items, index_text)
    return findings


def render_text(findings: list[Finding]) -> str:
    if not findings:
        return "backlog-check: OK."
    bloq = [f for f in findings if f.severity == BLOCKING]
    conf = [f for f in findings if f.severity == TO_CONFIRM]
    lines = [f"{f.severity:14} {f.path}:{f.line}  {f.rule}  {f.msg}"
             for f in sorted(findings, key=lambda f: (f.severity != BLOCKING, f.path, f.line))]
    lines.append(f"\n— {len(findings)} finding(s): {len(bloq)} blocking-auto, {len(conf)} to-confirm")
    return "\n".join(lines)


def main(argv):
    if "--stamp" in argv:
        return cmd_stamp(argv)
    if "--checklist" in argv:
        rest = [a for a in argv[argv.index("--checklist") + 1:] if not a.startswith("-")]
        impacts = None
        if rest:
            cid = rest[0].strip("/")
            target = "`backlog/" + cid + "/`"
            st = work_item_state(cid)
            impacts = st.get("impacts") if st else None
        else:
            target = "the work item's folder"
        print(closure_checklist(target, impacts))
        return 0
    if "--state" in argv:
        rest = [a for a in argv[argv.index("--state") + 1:] if not a.startswith("-")]
        if not rest:
            print("usage: --state <id>   (work items: " + ", ".join(work_item_ids()) + ")")
            return 1
        cid = rest[0].strip("/")
        st = work_item_state(cid)
        print(json.dumps(st, ensure_ascii=False, indent=2) if "--json" in argv else render_state(cid))
        return 0 if st else 1
    if "--board" in argv:
        if "--json" in argv:
            print(json.dumps([work_item_state(c) for c in work_item_ids()], ensure_ascii=False, indent=2))
        else:
            print(render_board())
        return 0

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
