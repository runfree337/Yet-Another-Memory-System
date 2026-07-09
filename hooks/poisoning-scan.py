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
  poisoning-scan.py --stdin-json  Claude Code adapter (reads tool_input.file_path)

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


def scan_file(path):
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                for col, ch in enumerate(line, 1):
                    if ord(ch) in SUSPECT:
                        out.append((path, i, col, hex(ord(ch))))
    except (OSError, UnicodeDecodeError):
        pass
    return out


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
    files = [n for n in DEFAULT_NAMES if os.path.isfile(n)]
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
        try:
            data = json.load(sys.stdin)
            p = (data.get("tool_input") or {}).get("file_path")
            a.paths = [p] if p else []
        except Exception:
            return 0

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
