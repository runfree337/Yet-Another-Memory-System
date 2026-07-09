#!/usr/bin/env python3
"""Dead references in the docs (universal, portable) — MECHANICAL half of doc freshness.

Catches a PATH reference that points to nothing: a file cited in a `.md` that does not
exist / no longer exists. SEMANTIC drift (does the prose describe the real behavior?) is
not mechanizable -> project review (tier 2).

Zero false positive on the firm tier: only flags a token that is clearly a "file path"
(at least one `/` + an extension), outside a closed code block, outside a template
(`<…>`, `YYYY`, `AAAA`…), outside a line carrying a negation/planned marker ("deleted",
"to create", "renamed"…). Severity via git: a path/basename with history = existed then
disappeared -> BLOCKING; otherwise TO-CONFIRM (might be planned, or a typo).

Modes: doc-refs-check.py [paths.md…] | --staged | (default: the framework's .md files)
Exit 2 if >=1 BLOCKING, 1 if only TO-CONFIRM, 0 otherwise. Read-only.
"""
import argparse
import os
import re
import subprocess
import sys

FRAMEWORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # framework root
PATH_RE = re.compile(r"(?:[\w.\-]+/)+[\w.\-]+\.[A-Za-z0-9]{1,6}")
TEMPLATE = re.compile(r"[<>{}*…]|YYYY|AAAA|XXXX|MM-|/\.\.\.")
# Prose words that neutralize a path mention — both languages covered (docs may be
# authored in either while the corpus is being translated; keep both sets, never drop
# the French forms even once the English ones land).
NEG = ("n'existe", "nexiste", "supprim", "à créer", "a creer", "à porter", "a porter",
       "renomm", "à venir", "a venir", "exemple", "example", "template", "gabarit",
       "placeholder", "→", "->", "n'est pas", "plus tard", "déplacé", "deplace", "futur",
       "deleted", "removed", "to create", "to port", "renamed", "upcoming", "later",
       "moved", "future", "does not exist", "doesn't exist", "not yet", "not created",
       "planned")

# TEMPLATE exemption — explicit HTML marker, never a hidden allowlist in the script.
# (a) line  : "<!-- template -->" on a line exempts the paths on THAT line.
# (b) block : a "<!-- template -->" / "<!-- /template -->" pair exempts every line
#             (markers included) between the two. An opening marker never closed falls
#             back to case (a) — exempts only its own line.
TEMPLATE_OPEN = "<!-- template -->"
TEMPLATE_CLOSE = "<!-- /template -->"


def template_lines(lines):
    """Line numbers (1-indexed) exempted by the <!-- template --> marker."""
    exempt = set()
    open_at = None
    for i, line in enumerate(lines, 1):
        if TEMPLATE_CLOSE in line and open_at is not None:
            exempt.update(range(open_at, i + 1))
            open_at = None
            continue
        if TEMPLATE_OPEN in line:
            if open_at is not None:
                exempt.add(open_at)  # previous marker never closed -> case (a) only
            open_at = i
    if open_at is not None:
        exempt.add(open_at)  # never closed -> case (a) only
    return exempt


def repo_root():
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return out or os.getcwd()
    except Exception:
        return os.getcwd()


REPO = repo_root()


def exists_somewhere(token, file_dir):
    return any(os.path.isfile(os.path.join(base, token))
               for base in (file_dir, FRAMEWORK, REPO, os.getcwd()))


def had_history(token):
    # EXACT path only: a homonymous file (same basename) that disappeared elsewhere does
    # NOT make this reference dead. The `*/basename` glob produced false BLOCKING — it was
    # removed to keep the firm tier at zero false positives. Dead = this exact path
    # existed.
    try:
        out = subprocess.run(["git", "log", "--all", "--oneline", "-1", "--", token],
                             capture_output=True, text=True, timeout=10, cwd=REPO).stdout
        return bool(out.strip())
    except Exception:
        return False


def scan_file(path):
    findings = []
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except (OSError, UnicodeDecodeError):
        return findings
    fenced = False
    file_dir = os.path.dirname(os.path.abspath(path))
    exempt = template_lines(lines)
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if i in exempt:
            continue
        if any(m in line.lower() for m in NEG):
            continue
        for tok in PATH_RE.findall(line.replace("`", " ")):
            if TEMPLATE.search(tok) or "://" in tok or exists_somewhere(tok, file_dir):
                continue
            sev = "BLOCKING" if had_history(tok) else "TO-CONFIRM"
            findings.append((sev, path, i, tok))
    return findings


def gather(args):
    if args.staged:
        try:
            out = subprocess.run(["git", "diff", "--cached", "--name-only"],
                                 capture_output=True, text=True, timeout=10).stdout
        except Exception:
            return []
        return [f for f in out.splitlines() if f.endswith(".md") and os.path.isfile(f)]
    if args.paths:
        return args.paths
    found = []
    for dpath, _, names in os.walk(FRAMEWORK):
        found += [os.path.join(dpath, n) for n in names if n.endswith(".md")]
    return found


def main():
    ap = argparse.ArgumentParser(description="Dead references in the docs (portable).")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--staged", action="store_true")
    a = ap.parse_args()

    findings = []
    for f in gather(a):
        findings += scan_file(f)

    blocking = [x for x in findings if x[0] == "BLOCKING"]
    for sev, path, line, tok in findings:
        print(f"{sev:11} {path}:{line}  path not found: {tok}")
    if not findings:
        print("doc-refs: OK — no dead references.")
        return 0
    print(f"\ndoc-refs: {len(blocking)} blocking, {len(findings) - len(blocking)} to-confirm.")
    return 2 if blocking else 1


if __name__ == "__main__":
    sys.exit(main())
