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
import unicodedata

# The other channels' index files/dirs — framework constants, hardcoded like in
# checks/memory-check.py; reading any of them counts as consulting the cartography.
CHANNEL_PATHS = ("FEATURE_MAP.md", "features/", "MEMORY.md", "memory/", "decisions/")
MAX_ENTRIES = 3


def norm(path, root_abs):
    """Repo-relative form of a logged/input path (hosts often pass absolute).
    Resolves symlinks on both sides (root always, so a tmp dir that's itself a
    symlink — e.g. macOS /tmp -> /private/tmp — doesn't defeat containment
    checks; the value only when it's absolute, since a relative value is
    already repo-relative and must not be resolved against this process's cwd).
    """
    root_r = os.path.realpath(root_abs).replace("\\", "/").rstrip("/")
    p = (path or "").replace("\\", "/").rstrip("/")
    if p.startswith("/"):
        p = os.path.realpath(p).replace("\\", "/").rstrip("/")
    if p == root_r:
        return "."
    if p.startswith(root_r + "/"):
        return p[len(root_r) + 1:]
    return p


def parse_line(line):
    """Parse one tracker log line into (tool, kind, value), or None for a
    comment/blank/malformed line. Tolerates legacy 2-field 'TOOL|value' lines
    (kind defaults to 'path') from a log started before the 3-field format
    landed — a mixed log mid-session should still degrade gracefully."""
    line = line.rstrip("\n")
    if not line or line.startswith("#") or "|" not in line:
        return None
    parts = line.split("|", 2)
    if len(parts) == 2:
        return parts[0], "path", parts[1]
    return parts[0], parts[1], parts[2]


def consulted(track_log, consult_paths, root_abs, current=None):
    """True if the log shows a cartography consultation. Only kind=path lines
    can be one — a glob/pattern can share a channel's name (e.g. a Grep for
    the word "memory") without ever reading it.

    `current`, when given, is the (tool, kind, value) triple identifying the
    call this nudge is evaluating. The tracker's PreToolUse hook logs the
    current call BEFORE this PostToolUse nudge runs, so without discounting it
    a configured root that's also a channel path (e.g. `roots: ["features/"]`)
    would make the nudge see itself as its own consultation and go
    permanently silent. Only the log's very last line is discounted, and only
    when it matches exactly — an older, genuinely prior occurrence of the same
    call still counts as a real consultation.
    """
    try:
        with open(track_log, encoding="utf-8", errors="replace") as fh:
            entries = [e for e in (parse_line(l) for l in fh) if e]
    except OSError:
        return False  # no tracker installed -> no consultation info, nudge anyway

    if current and entries and entries[-1] == current:
        entries = entries[:-1]

    for _tool, kind, value in entries:
        if kind != "path":
            continue
        p = norm(value, root_abs)
        if any(p == c.rstrip("/") or p.startswith(c) for c in consult_paths):
            return True
    return False


def glob_literal_prefix(pattern):
    """Literal (non-wildcard) prefix of a glob pattern, up to the first `*`,
    `?`, `[` or `{`. That prefix is the only part of a glob that's a location."""
    for i, ch in enumerate(pattern or ""):
        if ch in "*?[{":
            return pattern[:i]
    return pattern or ""


def root_of_path(path_n, roots):
    """The configured root containing this already-repo-relative path, if any."""
    return next((r for r in roots if path_n == r or path_n.startswith(r + "/")), "")


def root_of_glob(pattern, path, root_abs, roots):
    """The configured root containing a glob's literal prefix, joined to its
    directory `path` when one was given (a Glob call's `pattern` is a glob
    expression, not a regex — this never does substring matching)."""
    prefix = glob_literal_prefix(pattern)
    joined = (path.rstrip("/") + "/" + prefix) if path else prefix
    return root_of_path(norm(joined, root_abs), roots)


def classify_current(tool, path, pattern, glob):
    """(tool, kind, value) for the call being evaluated, mirroring the
    tracker's own precedence (path > glob > pattern for Grep; path >
    pattern-as-glob for Glob) so this triple matches the log line the tracker
    just wrote for this same call — used by consulted() to recognize (and
    discount) that trace."""
    if tool == "Glob":
        return (tool, "path", path) if path else (tool, "glob", pattern)
    if path:
        return tool, "path", path
    if glob:
        return tool, "glob", glob
    return tool, "pattern", pattern


def sanitize_field(s, limit=160):
    """Form-hygiene for text reflected verbatim into additionalContext (a
    manifest `intent` column, a channel-index summary): strip control
    characters (keep tab/space), collapse whitespace runs, truncate. This
    never inspects *what* the text says — that's not this function's job,
    only how it's shaped once it lands in a note the host may render/log."""
    if not s:
        return s
    s = "".join(ch for ch in s if ch in "\t " or unicodedata.category(ch)[0] != "C")
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > limit:
        s = s[:limit].rstrip() + "…"
    return s


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
        with open(os.path.join(root, manifest), encoding="utf-8",
                  errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line or line.startswith("#") or "\t" not in line:
                    continue
                s = score(line)
                if s:
                    path, _, intent = line.partition("\t")
                    found.append((s, path, sanitize_field(intent.strip())))
    except OSError:
        pass
    for channel_index in ("FEATURE_MAP.md", "MEMORY.md"):
        try:
            with open(os.path.join(root, channel_index), encoding="utf-8",
                      errors="replace") as fh:
                for line in fh:
                    m = re.match(r"-\s*\[[^\]]+\]\(([^)]+)\)\s*[—-]?\s*(.*)",
                                 line.strip())
                    if m and score(line):
                        found.append((score(line), m.group(1),
                                      sanitize_field(m.group(2).strip())))
        except OSError:
            continue
    found.sort(key=lambda e: -e[0])
    return found


def updated_of(root, rel):
    """`updated:` frontmatter date of an entry file, '' when absent (source
    files), when `rel` escapes the repo root (absolute, `../`, a symlink
    resolving outside — manifest/FEATURE_MAP/MEMORY entries are
    user/AI-authored text, not a trusted boundary), or when the date itself
    needs clamping before it's reflected into additionalContext."""
    if not rel or os.path.isabs(rel):
        return ""
    root_r = os.path.realpath(root)
    target = os.path.realpath(os.path.join(root, rel))
    if target != root_r and not target.startswith(root_r + os.sep):
        return ""
    try:
        with open(target, encoding="utf-8", errors="replace") as fh:
            m = re.search(r"^updated:\s*(\S+)", fh.read(2000), re.M)
    except OSError:
        return ""
    if not m:
        return ""
    return re.sub(r"[^A-Za-z0-9:/.\-]", "", m.group(1))[:20]


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

    raw_path = path
    path_n = norm(path, root_abs)
    # Targeted search — an existing single file: no nudge, ever.
    if path_n not in ("", ".") and os.path.isfile(os.path.join(root, path_n)):
        return ""

    # Covered zone? kind-specific containment — no substring matching:
    #  - Glob: its `pattern` IS a glob, always combined with `path` (if any) —
    #    that's the shape a Glob call actually takes (root_of_glob);
    #  - Grep: `path` wins when given, else its `glob` file-type filter (also
    #    via root_of_glob, with no directory to combine), else the search
    #    targets no particular root (a bare regex is never a location) —
    #    project-wide fallback below still applies when path is empty.
    if tool == "Glob":
        zone = root_of_glob(pattern, raw_path, root_abs, roots)
    elif raw_path:
        zone = root_of_path(path_n, roots)
    elif glob:
        zone = root_of_glob(glob, "", root_abs, roots)
    else:
        zone = ""
    if not zone:
        if path_n not in ("", "."):
            return ""
        zone = "."  # project-wide sweep

    if track_log:
        current = classify_current(tool, raw_path, pattern, glob)
        if consulted(track_log, CHANNEL_PATHS + (index_dir + "/",), root_abs, current):
            return ""

    if marker:  # once per zone per session — check only; the append is the
        # very last step below, after the note is fully built. Appending
        # eagerly here would permanently mute the zone for the rest of the
        # session if building the note later raised (e.g. a non-UTF-8
        # manifest) — a lost marker write just means a possible duplicate
        # note, which beats a nudge that never fires again.
        try:
            with open(marker, encoding="utf-8", errors="replace") as fh:
                if zone in fh.read().split("\n"):
                    return ""
        except OSError:
            pass

    tokens = set()
    if tool != "Glob":
        # Glob's `pattern` is a glob expression, not search terms — tokenizing
        # it (e.g. "src", "py" out of "src/**/*.py") would match almost the
        # entire manifest and present arbitrary entries as "matching".
        tokens = {t.lower() for t in re.split(r"[^A-Za-z0-9_]+", pattern or "")
                  if len(t) >= 3}

    if zone == ".":
        lines = ["[YAMS index] Broad search over the whole project — this includes "
                 "%s, which the navigation index maps file by file. Consulting %s "
                 "first can replace part of the sweep."
                 % (", ".join(r + "/" for r in roots), cfg.get("hub") or manifest)]
    else:
        lines = ["[YAMS index] Broad search over %s/ — a zone the navigation index "
                 "maps file by file. Consulting %s first usually replaces the sweep."
                 % (zone, cfg.get("hub") or manifest)]
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
    note = "\n".join(lines)

    if marker:
        try:
            with open(marker, "a", encoding="utf-8") as fh:
                fh.write(zone + "\n")  # single write: as atomic as an append gets
        except OSError:
            pass  # a duplicate note next time beats a lost one now
    return note


def main():
    ap = argparse.ArgumentParser(description="Index nudge (portable).")
    ap.add_argument("--root", default=".", help="project root")
    ap.add_argument("--config", default="", help="default: <root>/index/index-config.json")
    ap.add_argument("--track-log", default="", help="session consultation log (TOOL|KIND|VALUE)")
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
