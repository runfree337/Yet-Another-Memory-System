#!/usr/bin/env python3
"""Garde des commandes destructrices (universelle, portable).

Sort de l'auto-autorisation les commandes shell à effet de bord large et difficilement
réversible — `find … -delete` et `find … -exec rm …`. Volontairement **étroit** (zéro
faux positif sur un `rm` normal) : on demande confirmation, on ne bloque pas par défaut.

Portable (stdlib seule). Un **installeur** la câble : Claude Code (`PreToolUse` sur `Bash`
→ décision « ask »), Git (`pre-commit` d'un script), CI.

Modes :
  destructive-guard.py --command "find . -delete"   teste une commande
  destructive-guard.py --stdin-json                 adaptateur Claude Code (décision « ask »)

Sans --stdin-json : exit 2 si la commande est destructrice (BLOQUER en non-interactif),
0 sinon. Avec --stdin-json : émet une décision « ask » sur stdout et exit 0.
"""
import argparse
import json
import re
import sys

# `-delete` précédé d'un espace/début (pas `--delete` façon `git branch --delete`),
# ou `-exec … rm`.
DESTRUCTIVE = (re.compile(r"(?<![-\w])-delete\b"), re.compile(r"-exec\s+rm\b"))
REASON = "Commande potentiellement destructive (find -delete / -exec rm) — confirmation requise."


def is_destructive(cmd):
    return any(rx.search(cmd or "") for rx in DESTRUCTIVE)


def main():
    ap = argparse.ArgumentParser(description="Garde des commandes destructrices (portable).")
    ap.add_argument("--command", default="")
    ap.add_argument("--stdin-json", action="store_true", help="adaptateur Claude Code")
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
        print(f"BLOQUÉ (non-interactif) : {REASON}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
