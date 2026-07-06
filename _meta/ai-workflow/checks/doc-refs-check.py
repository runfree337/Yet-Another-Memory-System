#!/usr/bin/env python3
"""Références mortes dans la doc (universel, portable) — moitié MÉCANIQUE de la fraîcheur doc.

Attrape une référence de CHEMIN qui pointe vers du vide : un fichier cité dans un `.md` qui
n'existe pas / plus. La dérive SÉMANTIQUE (la prose décrit-elle le vrai comportement ?) n'est
pas mécanisable → revue du projet (étage 2).

Zéro faux positif sur le tier ferme : on ne signale qu'un token clairement « chemin de fichier »
(au moins un `/` + une extension), hors bloc de code clôturé, hors gabarit (`<…>`, `YYYY`,
`AAAA`…), hors ligne portant un marqueur de négation/planifié (« supprimé », « à créer »,
« à porter », « renommé », « → »…). Sévérité via git : un chemin/basename qui a un historique
= a existé puis disparu → BLOQUANT ; sinon À-CONFIRMER (peut-être planifié, ou coquille).

Modes : doc-refs-check.py [chemins.md…] | --staged | (défaut : les .md du framework)
Exit 2 si ≥1 BLOQUANT, 1 si seulement À-CONFIRMER, 0 sinon. Lecture seule.
"""
import argparse
import os
import re
import subprocess
import sys

FRAMEWORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ai-workflow/
PATH_RE = re.compile(r"(?:[\w.\-]+/)+[\w.\-]+\.[A-Za-z0-9]{1,6}")
TEMPLATE = re.compile(r"[<>{}*…]|YYYY|AAAA|XXXX|MM-|/\.\.\.")
NEG = ("n'existe", "nexiste", "supprim", "à créer", "a creer", "à porter", "a porter",
       "renomm", "à venir", "a venir", "exemple", "example", "template", "gabarit",
       "placeholder", "→", "->", "n'est pas", "plus tard", "déplacé", "deplace", "futur")


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
    # CHEMIN EXACT seulement : un fichier homonyme (même basename) disparu ailleurs ne rend
    # PAS cette référence morte. Le glob `*/basename` produisait des faux BLOQUANT — on l'a
    # retiré pour garder le tier ferme à zéro faux positif. Mort = ce chemin précis a existé.
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
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if any(m in line.lower() for m in NEG):
            continue
        for tok in PATH_RE.findall(line.replace("`", " ")):
            if TEMPLATE.search(tok) or "://" in tok or exists_somewhere(tok, file_dir):
                continue
            sev = "BLOQUANT" if had_history(tok) else "À-CONFIRMER"
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
    ap = argparse.ArgumentParser(description="Références mortes dans la doc (portable).")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--staged", action="store_true")
    a = ap.parse_args()

    findings = []
    for f in gather(a):
        findings += scan_file(f)

    blocking = [x for x in findings if x[0] == "BLOQUANT"]
    for sev, path, line, tok in findings:
        print(f"{sev:11} {path}:{line}  chemin introuvable : {tok}")
    if not findings:
        print("doc-refs : OK — aucune référence morte.")
        return 0
    print(f"\ndoc-refs : {len(blocking)} bloquant(s), {len(findings) - len(blocking)} à-confirmer.")
    return 2 if blocking else 1


if __name__ == "__main__":
    sys.exit(main())
