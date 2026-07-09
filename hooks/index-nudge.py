#!/usr/bin/env python3
"""Index nudge (universal, portable) — the ACTIVE half of the index-usage story.

The tracker/flush metrics pair (adapters) measures index bypasses after the fact;
this script intervenes at the exact moment one happens: a BROAD search sweeping a
zone the navigation index covers, in a session that never consulted the cartography.
It emits ONE short note pointing to the index and to the entries matching the search
terms — each with its `updated` frontmatter date, the provenance a reader needs to
calibrate trust (an entry that lies is worse than none, `FEATURE_MAP.md`).

It NUDGES, it never RAILS: the note goes NEXT TO the raw search results, never
instead of them — the cartography is a derived representation, and a targeted search
is often pre-edit verification where only the real file counts. Hence the strict
conditions; anything else is a silent no-op (empty output, exit 0):
  - `index/index-config.json` exists (same opt-in as the metrics pair);
  - the search target is NOT a single existing file (targeted = never nudged);
  - the search lands in a covered zone (a configured `root`), or is project-wide
    (no path — which by definition includes the covered zones);
  - the consultation log (--track-log, when provided) shows no consultation yet:
    neither the index dir nor the other channels' indexes (FEATURE_MAP.md/features/,
    MEMORY.md/memory/, decisions/);
  - the zone wasn't already nudged (--marker, when provided): once per zone per run.

Portable (stdlib only). An **installer** wires it in: Claude Code (`PostToolUse` on
`Grep|Glob` -> `additionalContext`); other hosts the day they expose an equivalent
post-search injection point — only the envelope below is host-specific, never this
logic.

Modes:
  index-nudge.py --tool Grep --pattern "damage tick" --path src   universal: note on
                                                                  stdout, or nothing
  index-nudge.py --stdin-json                        Claude Code adapter: reads the
                                                     hook JSON, emits the PostToolUse
                                                     `additionalContext` envelope

Always exits 0 — a nudge must never break the host's tool call.
"""
import argparse
import json
import os
import re
import sys

# The other channels' index files/dirs — framework constants, hardcoded like in
# checks/memory-check.py; reading any of them counts as consulting the cartography.
CHANNEL_PATHS = ("FEATURE_MAP.md", "features/", "MEMORY.md", "memory/", "decisions/")
MAX_ENTRIES = 3


def norm(path, root_abs):
    """Repo-relative form of a logged/input path (hosts often pass absolute)."""
    p = (path or "").replace("\\", "/").rstrip("/")
    if p == root_abs:
        return "."
    if p.startswith(root_abs + "/"):
        return p[len(root_abs) + 1:]
    return p


def consulted(track_log, consult_paths, root_abs):
    """True if the log (TOOL|PATH lines) shows a cartography consultation."""
    try:
        with open(track_log, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("#") or "|" not in line:
                    continue
                p = norm(line.strip().split("|", 1)[1], root_abs)
                if any(p == c.rstrip("/") or p.startswith(c) for c in consult_paths):
                    return True
    except OSError:
        pass  # no tracker installed -> no consultation info, nudge anyway
    return False


def matching_entries(root, manifest, tokens):
    """Entries whose line matches the search tokens: manifest (path<TAB>intent)
    + channel indexes (`- [slug](target) — summary`). Best score first."""
    if not tokens:
        return []

    def score(text):
        low = text.lower()
        return sum(1 for t in tokens if t in low)

    found = []
    try:
        with open(os.path.join(root, manifest), encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line or line.startswith("#") or "\t" not in line:
                    continue
                s = score(line)
                if s:
                    path, _, intent = line.partition("\t")
                    found.append((s, path, intent.strip()))
    except OSError:
        pass
    for channel_index in ("FEATURE_MAP.md", "MEMORY.md"):
        try:
            with open(os.path.join(root, channel_index), encoding="utf-8") as fh:
                for line in fh:
                    m = re.match(r"-\s*\[[^\]]+\]\(([^)]+)\)\s*[—-]?\s*(.*)",
                                 line.strip())
                    if m and score(line):
                        found.append((score(line), m.group(1), m.group(2).strip()))
        except OSError:
            continue
    found.sort(key=lambda e: -e[0])
    return found


def updated_of(root, rel):
    """`updated:` frontmatter date of an entry file, '' when absent (source files)."""
    try:
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            m = re.search(r"^updated:\s*(\S+)", fh.read(2000), re.M)
        return m.group(1) if m else ""
    except OSError:
        return ""


def build_note(root, config_path, tool, path, pattern, glob, track_log, marker):
    """The note to inject, or '' when any of the strict conditions fails."""
    try:
        with open(config_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return ""
    roots = [r.rstrip("/") for r in (cfg.get("roots") or []) if r and r.strip("/")]
    if not roots:
        return ""
    manifest = cfg.get("manifest", "index/manifest.tsv")
    index_dir = (os.path.dirname(manifest) or "index").rstrip("/")
    root_abs = os.path.abspath(root).replace("\\", "/")

    path = norm(path, root_abs)
    # Targeted search — an existing single file: no nudge, ever.
    if path not in ("", ".") and os.path.isfile(os.path.join(root, path)):
        return ""

    # Covered zone? Same containment rule as the flush metric (a root in the
    # searched path/glob), plus the project-wide case (no path = everything,
    # covered zones included).
    hay = " ".join(x for x in (path, glob, pattern if tool == "Glob" else "") if x)
    zone = next((r for r in roots
                 if path == r or path.startswith(r + "/") or (r + "/") in hay), "")
    if not zone:
        if path not in ("", "."):
            return ""
        zone = "."  # project-wide sweep

    if track_log and consulted(track_log, CHANNEL_PATHS + (index_dir + "/",), root_abs):
        return ""

    if marker:  # once per zone per session
        try:
            with open(marker, encoding="utf-8") as fh:
                if zone in fh.read().split("\n"):
                    return ""
        except OSError:
            pass
        try:
            with open(marker, "a", encoding="utf-8") as fh:
                fh.write(zone + "\n")
        except OSError:
            return ""

    tokens = {t.lower() for t in re.split(r"[^A-Za-z0-9_]+", pattern or "")
              if len(t) >= 3}
    zone_label = zone + "/" if zone != "." else ("the whole project (covered: %s)"
                                                 % ", ".join(r + "/" for r in roots))
    lines = ["[YAMS index] Broad search over %s — a zone the navigation index maps "
             "file by file. Consulting %s first usually replaces the sweep."
             % (zone_label, cfg.get("hub") or manifest)]
    entries = matching_entries(root, manifest, tokens)
    if entries:
        lines.append("Entries matching the search terms (check `updated` before "
                     "trusting):")
        for _, target, summary in entries[:MAX_ENTRIES]:
            u = updated_of(root, target)
            lines.append("- %s%s%s" % (target, " (updated %s)" % u if u else "",
                                       " — %s" % summary if summary else ""))
    lines.append("The raw results above are complete and untouched; this note fires "
                 "once per zone per session.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Index nudge (portable).")
    ap.add_argument("--root", default=".", help="project root")
    ap.add_argument("--config", default="", help="default: <root>/index/index-config.json")
    ap.add_argument("--track-log", default="", help="session consultation log (TOOL|PATH)")
    ap.add_argument("--marker", default="", help="once-per-zone state file")
    ap.add_argument("--tool", default="", choices=["", "Grep", "Glob"])
    ap.add_argument("--path", default="")
    ap.add_argument("--pattern", default="")
    ap.add_argument("--glob", default="")
    ap.add_argument("--stdin-json", action="store_true", help="Claude Code adapter")
    a = ap.parse_args()

    tool, path, pattern, glob = a.tool, a.path, a.pattern, a.glob
    if a.stdin_json:
        try:
            data = json.load(sys.stdin)
        except Exception:
            return 0
        tool = data.get("tool_name", "")
        tool_input = data.get("tool_input") or {}
        path = tool_input.get("path") or ""
        pattern = tool_input.get("pattern") or ""
        glob = tool_input.get("glob") or ""
    if tool not in ("Grep", "Glob"):
        return 0

    config = a.config or os.path.join(a.root, "index", "index-config.json")
    try:
        note = build_note(a.root, config, tool, path, pattern, glob,
                          a.track_log, a.marker)
    except Exception:
        return 0  # a nudge must never break the host's tool call
    if not note:
        return 0

    if a.stdin_json:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": note,
        }}))
    else:
        print(note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
