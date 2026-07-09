#!/usr/bin/env python3
"""Anti-poisoning guard (universal, portable) — invisible/bidi Unicode.

Detects invisible / bidirectional characters slipped into **instruction** and **shared
memory** files (the "TrapDoor" vector: a CLAUDE.md / .cursorrules / rule poisoned with
chars the human can't see).

Portable (stdlib only). An **installer** wires it into the tool's hook mechanism: Claude
Code (`SessionStart` / `PreToolUse`), Git (`pre-commit`), CI.

Modes:
  poisoning-scan.py [paths…]      scans the given files
  poisoning-scan.py --staged      scans the git-**staged** .md/.txt (pre-commit / CI)
  poisoning-scan.py               scans the usual instruction files present
  poisoning-scan.py --stdin-json  Claude Code adapter (PreToolUse Write/Edit): scans the
                                  INCOMING content (tool_input.content / new_string) —
                                  the injection vector — never the stale on-disk file.

The no-args mode ("usual instruction files") seeds its file list from DEFAULT_NAMES (plus
a walk of the framework's own .md/.txt). DEFAULT_NAMES can be EXTENDED (never replaced)
with repo-relative paths from an optional `checks-config.json` at the repo root, key
`guards.extra-watched-files` — see `checks-config.example.json`. Extension-only,
fail-closed: a missing/unreadable/malformed config, or a malformed key (not a list of
strings), means DEFAULT_NAMES alone — today's behavior, byte-identical. A guard must
never crash or block because of a bad config. (`--staged` and explicit `paths…` do not
consume DEFAULT_NAMES at all, so the extension is a no-op there.)

Exit 2 = suspect chars detected (BLOCK); 0 otherwise. Read-only.
"""
import argparse
import json
import os
import subprocess
import sys

# Suspect ranges by CODE POINT (ASCII hex literals only — never an invisible char in
# THIS file, or it would flag itself). Covers:
#   200B–200F zero-width + LTR/RTL marks · 2028–202F separators + embeddings/overrides
#   2060–2064 word-joiner + invisibles · 2066–2069 bidi isolates · FEFF BOM
_RANGES = [(0x200B, 0x200F), (0x2028, 0x202F), (0x2060, 0x2064), (0x2066, 0x2069), (0xFEFF, 0xFEFF)]
SUSPECT = {cp for lo, hi in _RANGES for cp in range(lo, hi + 1)}

DEFAULT_NAMES = ["CLAUDE.md", "AGENTS.md", ".cursorrules",
                 os.path.join(".github", "copilot-instructions.md")]

CONFIG_NAME = "checks-config.json"

_config_cache = None  # lazy, loaded at most once per process


def _candidate_roots():
    # Mirrors normative-write-guard.py's resolution: $CLAUDE_PROJECT_DIR (set by Claude
    # Code for every hook invocation) -> cwd -> this repo's own root (hooks/../..), for
    # direct/manual invocation from within a checkout of this framework.
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        yield env_root
    yield os.getcwd()
    yield os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def _load_config():
    """Return the parsed `checks-config.json` dict, or {} if missing/unreadable/broken —
    fail-closed: extension features are then treated as absent, DEFAULT_NAMES alone.
    First candidate root where the file exists AND parses wins; no merging."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    data = {}
    for root in _candidate_roots():
        try:
            with open(os.path.join(root, CONFIG_NAME), "r", encoding="utf-8") as f:
                data = json.load(f)
            break
        except Exception:
            continue
    if not isinstance(data, dict):
        data = {}
    _config_cache = data
    return data


def extra_watched_files():
    """Repo-relative paths from `guards.extra-watched-files`, or [] if the file/key is
    absent, unreadable, or malformed (not a list of strings) — never removes/replaces
    DEFAULT_NAMES, only appends."""
    guards = _load_config().get("guards")
    if not isinstance(guards, dict):
        return []
    extra = guards.get("extra-watched-files")
    if not isinstance(extra, list) or not all(isinstance(p, str) for p in extra):
        return []
    return extra


def watched_names():
    """DEFAULT_NAMES, extended with the (validated) config extension."""
    return DEFAULT_NAMES + extra_watched_files()


def scan_text(text, label):
    out = []
    for i, line in enumerate(text.split("\n"), 1):
        for col, ch in enumerate(line, 1):
            if ord(ch) in SUSPECT:
                out.append((label, i, col, hex(ord(ch))))
    return out


def scan_file(path):
    # Read as BYTES then decode with surrogateescape: an invalid UTF-8 byte must NOT
    # silently skip the whole file (that would let an attacker bypass the scan by
    # appending one stray byte). Escaped bytes land in U+DC80–DCFF — outside SUSPECT —
    # so the real invisible chars are still caught.
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return []
    return scan_text(raw.decode("utf-8", errors="surrogateescape"), path)


def staged_text_files():
    try:
        res = subprocess.run(["git", "diff", "--cached", "--name-only"],
                             capture_output=True, text=True, timeout=10)
    except Exception:
        return []
    return [f for f in res.stdout.splitlines() if f.endswith((".md", ".txt"))]


def gather(args):
    if args.staged:
        return [f for f in staged_text_files() if os.path.isfile(f)]
    if args.paths:
        return args.paths
    files = [n for n in watched_names() if os.path.isfile(n)]
    framework = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ai-workflow/
    for root, _, names in os.walk(framework):
        files += [os.path.join(root, n) for n in names if n.endswith((".md", ".txt"))]
    return files


def main():
    ap = argparse.ArgumentParser(description="Anti-poisoning guard (invisible/bidi Unicode).")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--stdin-json", action="store_true", help="Claude Code adapter")
    a = ap.parse_args()

    if a.stdin_json:
        # PreToolUse Write/Edit: the poisoned payload is the INCOMING content
        # (tool_input.content / new_string), not the on-disk file — which still holds
        # the PRE-write state (or nothing at all for a new file). Scanning the disk
        # here would miss exactly the injection this guard exists to block.
        try:
            data = json.load(sys.stdin)
        except Exception:
            return 0
        ti = data.get("tool_input") or {}
        content = ti.get("content") or ti.get("new_string") or ""
        findings = scan_text(content, ti.get("file_path") or "(tool_input)")
    else:
        findings = []
        for f in gather(a):
            findings += scan_file(f)
    if not findings:
        return 0
    print("BLOCKED: invisible/bidi Unicode characters detected (possible poisoning).",
          file=sys.stderr)
    for path, line, col, code in findings:
        print(f"  {path}:{line}:{col}  {code}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
