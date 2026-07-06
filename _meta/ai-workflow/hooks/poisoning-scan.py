#!/usr/bin/env python3
"""Garde anti-empoisonnement (universelle, portable) — Unicode invisible/bidi.

Détecte les caractères invisibles / de bidirectionnalité glissés dans les fichiers
d'**instruction** et de **mémoire partagée** (vecteur « TrapDoor » : un CLAUDE.md /
.cursorrules / règle empoisonné par des chars que l'humain ne voit pas).

Portable (stdlib seule). Un **installeur** la câble dans le mécanisme de hook de
l'outil : Claude Code (`SessionStart` / `PreToolUse`), Git (`pre-commit`), CI.

Modes :
  poisoning-scan.py [chemins…]    scanne les fichiers donnés
  poisoning-scan.py --staged      scanne les .md/.txt git **stagés** (pré-commit / CI)
  poisoning-scan.py               scanne les fichiers d'instruction usuels présents
  poisoning-scan.py --stdin-json  adaptateur Claude Code (lit tool_input.file_path)

Exit 2 = chars suspects détectés (BLOQUER) ; 0 sinon. Lecture seule.
"""
import argparse
import json
import os
import subprocess
import sys

# Plages suspectes par POINTS DE CODE (littéraux hexadécimaux ASCII uniquement — jamais
# de char invisible dans CE fichier, sinon il se signale lui-même). Couvre :
#   200B–200F zéro-largeur + marques LTR/RTL · 2028–202F séparateurs + embeddings/overrides
#   2060–2064 word-joiner + invisibles · 2066–2069 isolates bidi · FEFF BOM
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
    ap = argparse.ArgumentParser(description="Garde anti-empoisonnement (Unicode invisible/bidi).")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--stdin-json", action="store_true", help="adaptateur Claude Code")
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
    print("BLOQUÉ : caractères Unicode invisibles/bidi détectés (empoisonnement possible).",
          file=sys.stderr)
    for path, line, col, code in findings:
        print(f"  {path}:{line}:{col}  {code}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
