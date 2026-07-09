#!/usr/bin/env python3
"""Contrôle déterministe des décisions (zéro faux positif).

Vérifie la concordance entre les fichiers `decisions/D-*.md` et leurs lignes
dans `decisions/INDEX.md`, par identifiant. NE corrige rien, **signale**.

Vérifs :
  D1  Tout fichier `D-AAAA-MM-JJ-NN.md` a une ligne `D-AAAA-MM-JJ-NN` dans INDEX.md.
  D2  Tout identifiant `D-…` cité dans INDEX.md a un fichier `D-….md`.

Code retour : 2 si ≥1 écart, 0 sinon.  Usage : python3 checks/decisions-check.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEC = os.path.join(ROOT, "decisions")
INDEX = os.path.join(DEC, "INDEX.md")
ID = re.compile(r"D-\d{4}-\d{2}-\d{2}-\d{2}")


def main() -> int:
    if not os.path.isdir(DEC):
        print("decisions-check : pas de dossier decisions/ — rien à vérifier.")
        return 0

    files = {ID.search(f).group(0) for f in os.listdir(DEC)
             if f.endswith(".md") and ID.search(f)}
    indexed = set()
    if os.path.isfile(INDEX):
        indexed = set(ID.findall(open(INDEX, encoding="utf-8").read()))

    errs = []
    for d in sorted(files - indexed):
        errs.append(f"D1 : `{d}.md` existe mais n'est pas indexé dans decisions/INDEX.md")
    for d in sorted(indexed - files):
        errs.append(f"D2 : `{d}` est dans INDEX.md mais aucun fichier `{d}.md`")

    for e in errs:
        print(e)
    if errs:
        print(f"\ndecisions-check : {len(errs)} écart(s).")
        return 2
    print("decisions-check : OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
