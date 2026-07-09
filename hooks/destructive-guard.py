#!/usr/bin/env python3
"""Destructive command guard (universal, portable).

Takes broad, hard-to-reverse shell commands out of auto-approval — `find … -delete` and
`find … -exec rm …`. Deliberately **narrow** (zero false positive on a normal `rm`): asks
for confirmation, doesn't block by default.

Portable (stdlib only). An **installer** wires it in: Claude Code (`PreToolUse` on `Bash`
-> "ask" decision), Git (`pre-commit` script), CI.

Modes:
  destructive-guard.py --command "find . -delete"   tests a command
  destructive-guard.py --stdin-json                 Claude Code adapter (decision "ask")

Without --stdin-json: exit 2 if the command is destructive (BLOCK non-interactively),
0 otherwise. With --stdin-json: emits an "ask" decision on stdout and exits 0.
"""
import argparse
import json
import re
import sys

# Windows consoles default to cp1252: non-cp1252 output (→, ⨯…) would crash print().
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# `-delete` preceded by a space/start (not `--delete` like `git branch --delete`), or
# `-exec … rm`.
DESTRUCTIVE = (re.compile(r"(?<![-\w])-delete\b"), re.compile(r"-exec\s+rm\b"))
REASON = "Potentially destructive command (find -delete / -exec rm) — confirmation required."


def is_destructive(cmd):
    return any(rx.search(cmd or "") for rx in DESTRUCTIVE)


def main():
    ap = argparse.ArgumentParser(description="Destructive command guard (portable).")
    ap.add_argument("--command", default="")
    ap.add_argument("--stdin-json", action="store_true", help="Claude Code adapter")
    a = ap.parse_args()

    if a.stdin_json:
        try:
            data = json.load(sys.stdin)
        except Exception:
            return 0
        if data.get("tool_name") != "Bash":
            return 0
        if is_destructive((data.get("tool_input") or {}).get("command", "")):
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": REASON,
            }}))
        return 0

    if is_destructive(a.command):
        print(f"BLOCKED (non-interactive): {REASON}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
