#!/usr/bin/env bash
# PostToolUse(Grep|Glob) hook: the ACTIVE half of the index-usage story. The
# tracker/flush pair measures bypasses after the fact; this hook intervenes at the
# exact moment one happens — a BROAD search sweeping a covered zone in a session
# that never consulted the cartography — by injecting `additionalContext` NEXT TO
# the raw results (never instead of them: the search has already run, PostToolUse
# cannot alter its output, only append context).
#
# Fires only when ALL of these hold, otherwise a silent no-op (exit 0, no output):
#   - `index/index-config.json` exists (same opt-in as tracker/flush);
#   - the call is a Grep/Glob whose target is NOT a single existing file — a
#     targeted grep is pre-edit verification territory, nudging there is noise;
#   - the search lands in a covered zone (a configured `root` in path/glob), or is
#     a project-wide sweep (no path), which by definition includes the covered zones;
#   - the session's tracker log (index-usage-tracker.sh) shows NO consultation yet —
#     neither the index dir nor the other channels (FEATURE_MAP.md/features/,
#     MEMORY.md/memory/, decisions/): routing that already happened via another
#     channel needs no reminder;
#   - this zone hasn't been nudged yet this session (once per zone per session,
#     marker file next to the tracker log).
#
# The injected context points to the navigation index and, when the Grep pattern's
# tokens match manifest/FEATURE_MAP.md/MEMORY.md entry lines, lists up to 3 candidate
# entries WITH their `updated` frontmatter date — provenance the agent needs to
# calibrate trust (an entry that lies is worse than none, FEATURE_MAP.md). It never
# claims authority over the raw results.
#
# JSON in/out via python3 (already a hard dependency of every YAMS check) — the
# hook JSON travels through an env var because the heredoc occupies python's stdin.
# Never blocks: any failure inside python is swallowed, the wrapper always exits 0.

set +e

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0

CONFIG="$ROOT/index/index-config.json"
[ -f "$CONFIG" ] || exit 0   # not opted into the per-file index -> nothing to nudge

PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && exit 0

SESSION_ID="${CLAUDE_CODE_SESSION_ID:-unknown}"
TRACKLOG="${TMPDIR:-/tmp}/yams-index-usage-${SESSION_ID}.log"
MARKER="${TMPDIR:-/tmp}/yams-index-nudge-${SESSION_ID}.log"

YAMS_HOOK_JSON="$(cat)" \
  "$PY" - "$ROOT" "$CONFIG" "$TRACKLOG" "$MARKER" <<'PYEOF'
import json
import os
import re
import sys

# The other channels' index files/dirs — framework constants, hardcoded like in
# checks/memory-check.py; reading any of them counts as consulting the cartography.
CHANNEL_PATHS = ("FEATURE_MAP.md", "features/", "MEMORY.md", "memory/", "decisions/")


def main():
    root, config_path, tracklog, marker = sys.argv[1:5]
    root_abs = os.path.abspath(root).replace("\\", "/")

    try:
        data = json.loads(os.environ.get("YAMS_HOOK_JSON", ""))
    except json.JSONDecodeError:
        return
    if data.get("tool_name") not in ("Grep", "Glob"):
        return
    tool_input = data.get("tool_input") or {}

    try:
        with open(config_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return
    roots = [r.rstrip("/") for r in (cfg.get("roots") or []) if r and r.strip("/")]
    if not roots:
        return
    manifest = cfg.get("manifest", "index/manifest.tsv")
    index_dir = (os.path.dirname(manifest) or "index").rstrip("/")
    hub = cfg.get("hub")

    def norm(p):
        """Repo-relative form of a logged/input path (Claude Code often passes absolute)."""
        p = (p or "").replace("\\", "/").rstrip("/")
        if p == root_abs:
            return "."
        if p.startswith(root_abs + "/"):
            return p[len(root_abs) + 1:]
        return p

    path = norm(tool_input.get("path"))
    pattern = tool_input.get("pattern") or ""
    glob = tool_input.get("glob") or ""

    # Targeted search — an existing single file: no nudge, ever.
    if path not in ("", ".") and os.path.isfile(os.path.join(root, path)):
        return

    # Covered zone? Same containment rule as index-usage-flush.sh (a root appearing
    # in the searched path/glob), plus the project-wide case (no path = everything,
    # covered zones included).
    hay = " ".join(x for x in (path, glob) if x)
    if data.get("tool_name") == "Glob":
        hay = " ".join(x for x in (hay, pattern) if x)
    zone = ""
    for r in roots:
        if path == r or path.startswith(r + "/") or (r + "/") in hay:
            zone = r
            break
    if not zone:
        if path in ("", "."):
            zone = "."   # project-wide sweep
        else:
            return

    # Already consulted the cartography this session? (tracker log, when installed)
    consult = tuple(c for c in CHANNEL_PATHS) + (index_dir + "/",)
    try:
        with open(tracklog, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("#") or "|" not in line:
                    continue
                p = norm(line.strip().split("|", 1)[1])
                if any(p == c.rstrip("/") or p.startswith(c) for c in consult):
                    return
    except OSError:
        pass   # tracker not installed -> no consultation info, nudge anyway

    # Once per zone per session.
    try:
        with open(marker, encoding="utf-8") as fh:
            if zone in fh.read().split("\n"):
                return
    except OSError:
        pass
    try:
        with open(marker, "a", encoding="utf-8") as fh:
            fh.write(zone + "\n")
    except OSError:
        return

    # Candidate entries: pattern tokens vs manifest lines (path<TAB>intent) and
    # channel index lines (`- [slug](target) — summary`). Top 3, best score first.
    tokens = {t.lower() for t in re.split(r"[^A-Za-z0-9_]+", pattern) if len(t) >= 3}
    candidates = []

    def score(text):
        low = text.lower()
        return sum(1 for t in tokens if t in low)

    try:
        with open(os.path.join(root, manifest), encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line or line.startswith("#") or "\t" not in line:
                    continue
                p, _, intent = line.partition("\t")
                s = score(line)
                if s:
                    candidates.append((s, p, intent.strip()))
    except OSError:
        pass

    for channel_index in ("FEATURE_MAP.md", "MEMORY.md"):
        try:
            with open(os.path.join(root, channel_index), encoding="utf-8") as fh:
                for line in fh:
                    m = re.match(r"-\s*\[[^\]]+\]\(([^)]+)\)\s*[—-]?\s*(.*)", line.strip())
                    if not m:
                        continue
                    s = score(line)
                    if s:
                        target, summary = m.groups()
                        candidates.append((s, target, summary.strip()))
        except OSError:
            continue

    candidates.sort(key=lambda c: -c[0])

    def updated_of(rel):
        try:
            with open(os.path.join(root, rel), encoding="utf-8") as fh:
                m = re.search(r"^updated:\s*(\S+)", fh.read(2000), re.M)
            return m.group(1) if m else ""
        except OSError:
            return ""

    zone_label = zone + "/" if zone != "." else "the whole project (covered: %s)" % (
        ", ".join(r + "/" for r in roots))
    entry_point = hub or manifest
    lines = [
        "[YAMS index] Broad search over %s — a zone the navigation index maps "
        "file by file. Consulting %s first usually replaces the sweep." % (zone_label, entry_point),
    ]
    if candidates:
        lines.append("Entries matching the search terms (check `updated` before trusting):")
        for s, target, summary in candidates[:3]:
            u = updated_of(target)
            lines.append("- %s%s%s" % (target,
                                       " (updated %s)" % u if u else "",
                                       " — %s" % summary if summary else ""))
    lines.append("The raw results above are complete and untouched; "
                 "this note fires once per zone per session.")

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": "\n".join(lines),
    }}))


try:
    main()
except Exception:
    pass
PYEOF

exit 0
