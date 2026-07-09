#!/usr/bin/env python3
"""Intégrité de l'INDEX par-fichier (universel, portable).

Vérifie la concordance entre un index plat `chemin<TAB>intent` et les fichiers réels —
le « détail par-fichier » (Format A) de la couche navigation (cf. `index/INDEX.md`).

AGNOSTIQUE : les **racines** et **extensions** à indexer ne sont PAS codées en dur. C'est le
PROJET qui les définit (typiquement **à l'installation du framework**) dans
`index/index-config.json` — schéma : `index/index-config.example.json`. Sans config, il n'y a
rien à vérifier (le projet n'a pas opté pour un index par-fichier) → exit 0.

Vérifs (zéro faux positif) :
  I1  toute ligne de l'index → un fichier réel existe.
  I2  tout fichier sous `roots` d'extension `extensions` (hors `ignore`) → présent dans l'index.

Exit 2 si dérive, 0 sinon. Lecture seule, signale — ne réécrit jamais l'index.
"""
import argparse
import fnmatch
import json
import os
import sys

FRAMEWORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ai-workflow/
DEFAULT_CONFIG = os.path.join(FRAMEWORK, "index", "index-config.json")


def read_manifest(path):
    entries = {}
    with open(path, encoding="utf-8") as fh:
        for ln, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            entries[line.split("\t")[0].strip()] = ln
    return entries


def walk_files(base, roots, exts, ignore):
    exts = tuple(exts)
    found = set()
    for r in roots:
        for dpath, _, names in os.walk(os.path.join(base, r)):
            for n in names:
                if not n.endswith(exts):
                    continue
                rel = os.path.relpath(os.path.join(dpath, n), base).replace("\\", "/")
                if any(fnmatch.fnmatch(rel, pat) for pat in ignore):
                    continue
                found.add(rel)
    return found


def main():
    ap = argparse.ArgumentParser(description="Intégrité de l'index par-fichier (portable).")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--base", default=None, help="racine du dépôt (défaut : config.base ou cwd)")
    a = ap.parse_args()

    try:
        with open(a.config, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except OSError:
        print(f"index-check : pas de config ({a.config}) — le projet n'a pas défini de "
              "racines/extensions à indexer. Rien à vérifier.")
        print("  → copier/remplir index/index-config.example.json (à l'installation du framework).")
        return 0
    except json.JSONDecodeError as e:
        print(f"index-check : config illisible ({e}).", file=sys.stderr)
        return 2

    base = a.base or cfg.get("base") or os.getcwd()
    roots = cfg.get("roots", [])
    exts = cfg.get("extensions", [])
    ignore = cfg.get("ignore", [])
    if not roots or not exts:
        print("index-check : config sans `roots` ou `extensions` — rien à indexer.")
        return 0

    manifest_path = os.path.join(base, cfg.get("manifest", "index/manifest.tsv"))
    if not os.path.isfile(manifest_path):
        print(f"index-check : manifeste introuvable ({manifest_path}).", file=sys.stderr)
        return 2

    indexed = read_manifest(manifest_path)
    actual = walk_files(base, roots, exts, ignore)

    dead = sorted(p for p in indexed if not os.path.isfile(os.path.join(base, p)))
    missing = sorted(actual - set(indexed))

    for p in dead:
        print(f"I1 : indexé mais fichier absent → {p} (ligne {indexed[p]})")
    for p in missing:
        print(f"I2 : fichier non indexé → {p}")

    if dead or missing:
        print(f"\nindex-check : {len(dead)} entrée(s) morte(s), {len(missing)} fichier(s) à indexer.")
        return 2
    print(f"index-check : OK ({len(indexed)} entrées, {len(actual)} fichiers couverts).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
