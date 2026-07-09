#!/usr/bin/env python3
"""Normative-path write guard (universal, portable) — harness-level half of the capture policy.

The capture policy (`capture-policy.json`, key `normative-paths`) says which paths are
NORMATIVE (instruction files, rules — e.g. `CLAUDE.md`, `.claude/rules/`): writes there
shape how every future agent behaves, so they deserve a human's eyes. A deterministic
**check** elsewhere audits this after the fact (state, post-hoc: did an AI write land on a
normative path without review?). This guard is the other half: **prevention at write time**
— it intercepts the tool call itself, before the write lands, and turns it into an explicit
human confirmation. Enforcement lives in the tool harness, not in the model's goodwill.

Deliberately never a hard block: like `destructive-guard.py`, it asks (`--stdin-json` mode)
or blocks only in the non-interactive test mode (`--path`, for git/CI use) — the human (or
the pre-commit gate) decides, the guard only surfaces the decision point.

Portable (stdlib only). An **installer** wires it in: Claude Code (`PreToolUse` on
`Write`/`Edit` -> "ask" decision), Git (`pre-commit` script), CI.

Modes:
  normative-write-guard.py --path CLAUDE.md   tests a path (BLOCK non-interactively)
  normative-write-guard.py --stdin-json       Claude Code adapter (decision "ask")

Without --stdin-json: exit 2 if the path matches a normative-paths prefix, 0 otherwise
(0 also when no config is found). With --stdin-json: emits an "ask" decision on stdout
and exits 0 when the write matches; silent exit 0 for everything else (other tools, no
match, no config, bad JSON) — the guard is INACTIVE without a readable
`capture-policy.json` carrying a `normative-paths` key.

Config resolution (simplest robust rule — mirrors how Claude Code exposes the project
root): look for `capture-policy.json` first in `$CLAUDE_PROJECT_DIR` (set by Claude Code
for every hook invocation) when that env var is set; otherwise in the current working
directory; otherwise two levels up from this script (`hooks/../..`, this repo's own root,
covering direct/manual invocation from within a checkout of this framework). First
location where the file exists AND parses AND has a non-empty `normative-paths` wins —
no merging across locations.
"""
import argparse
import json
import os
import sys

CONFIG_NAME = "capture-policy.json"


def _candidate_roots():
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        yield env_root
    yield os.getcwd()
    yield os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def load_normative_paths():
    """Return the `normative-paths` list from the first resolvable config, or None."""
    for root in _candidate_roots():
        candidate = os.path.join(root, CONFIG_NAME)
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        paths = data.get("normative-paths")
        if isinstance(paths, list) and paths:
            return [p for p in paths if isinstance(p, str) and p]
    return None


def normalize(path):
    path = (path or "").replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def matched_prefix(path, normative_paths):
    norm = normalize(path)
    for prefix in normative_paths:
        if norm.startswith(normalize(prefix)):
            return prefix
    return None


def reason(prefix):
    return (
        f"Write to a normative path ({prefix}) — the capture policy requires explicit "
        "human confirmation."
    )


def main():
    ap = argparse.ArgumentParser(description="Normative-path write guard (portable).")
    ap.add_argument("--path", default=None)
    ap.add_argument("--stdin-json", action="store_true", help="Claude Code adapter")
    a = ap.parse_args()

    normative_paths = load_normative_paths()

    if a.stdin_json:
        if not normative_paths:
            return 0
        try:
            data = json.load(sys.stdin)
        except Exception:
            return 0
        if data.get("tool_name") not in ("Write", "Edit"):
            return 0
        file_path = (data.get("tool_input") or {}).get("file_path")
        if not file_path:
            return 0
        prefix = matched_prefix(file_path, normative_paths)
        if prefix:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason(prefix),
            }}))
        return 0

    if not normative_paths:
        return 0
    if matched_prefix(a.path, normative_paths):
        print(f"BLOCKED (non-interactive): {reason(matched_prefix(a.path, normative_paths))}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
