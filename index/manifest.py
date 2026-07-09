#!/usr/bin/env python3
"""Maintenance du manifeste plat `index/manifest.tsv` (le « détail par-fichier »,
Format A de `index/INDEX.md`) — un `chemin<TAB>intent` par ligne, trié par chemin.

AGNOSTIQUE, comme `checks/index-check.py` : ce script ne code en dur ni racines ni
extensions. Il lit `index/index-config.json` (schéma : `index-config.example.json`),
que le projet remplit **à l'installation du framework**.

Sous-commandes :
  manifest.py set   <chemin> <intent>   upsert (ajoute ou remplace l'intent), garde trié
  manifest.py rm    <chemin>            retire l'entrée
  manifest.py get   <chemin>            imprime l'intent (ou rien)
  manifest.py stamp                     si `hub` est configuré, met à jour sa ligne
                                        "> Last updated: ..." (date + commit court) — no-op sinon

Ce script est le pendant EN ÉCRITURE de `checks/index-check.py` (lecture seule, vérifie
la dérive). Aucune commande `check` ici : lancer `checks/index-check.py` pour ça — pas
de logique de vérification dupliquée entre les deux fichiers.

Le manifeste se grep pour la recherche ; il s'édite via ce script (jamais à la main —
l'en-tête du fichier le rappelle, et `set` re-trie/dédup)."""
import datetime
import json
import os
import subprocess
import sys

FRAMEWORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ai-workflow/
DEFAULT_CONFIG = os.path.join(FRAMEWORK, "index", "index-config.json")
HEADER = ("# chemin\tintent — manifeste plat, source de vérité de l'index par-fichier. "
          "Éditer via index/manifest.py, pas à la main.")


def load_config(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError:
        print(f"manifest : pas de config ({path}) — copier/remplir "
              "index/index-config.example.json avant d'utiliser ce script.", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"manifest : config illisible ({e}).", file=sys.stderr)
        return None


def manifest_path(cfg, base):
    return os.path.join(base, cfg.get("manifest", "index/manifest.tsv"))


def load(path):
    rows = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            p, _, intent = line.partition("\t")
            if p:
                rows[p] = intent
    return rows


def save(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(HEADER + "\n")
        for p in sorted(rows):
            f.write(f"{p}\t{rows[p]}\n")


def cmd_set(rows_path, chemin, intent):
    rows = load(rows_path)
    existed = chemin in rows
    rows[chemin] = " ".join(intent.split())
    save(rows_path, rows)
    print(("maj" if existed else "ajout") + f" : {chemin}")


def cmd_rm(rows_path, chemin):
    rows = load(rows_path)
    if rows.pop(chemin, None) is None:
        print(f"absent : {chemin}")
        return
    save(rows_path, rows)
    print(f"retiré : {chemin}")


def cmd_get(rows_path, chemin):
    print(load(rows_path).get(chemin, ""))


def cmd_stamp(cfg, base):
    hub = cfg.get("hub")
    if not hub:
        print("manifest : pas de `hub` configuré dans index-config.json — stamp désactivé "
              "(champ optionnel : chemin d'un fichier portant une ligne '> Last updated: ...').")
        return 0
    hub_path = os.path.join(base, hub)
    if not os.path.isfile(hub_path):
        print(f"manifest : hub introuvable ({hub_path}).", file=sys.stderr)
        return 2
    today = datetime.date.today().isoformat()
    try:
        head = subprocess.check_output(
            ["git", "-C", base, "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        head = "?"
    lines = open(hub_path, encoding="utf-8").read().splitlines()
    stamped = False
    for i, l in enumerate(lines):
        if l.startswith("> Last updated:"):
            lines[i] = f"> Last updated: {today} (commit {head})"
            stamped = True
            break
    if not stamped:
        print(f"manifest : aucune ligne '> Last updated: ...' dans {hub} — rien à tamponner.")
        return 0
    open(hub_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"stamped: {today} ({head}) → {hub}")
    return 0


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    cmd, rest = argv[0], argv[1:]

    cfg = load_config(DEFAULT_CONFIG)
    if cfg is None:
        return 2
    base = cfg.get("base") or os.getcwd()

    if cmd == "stamp" and not rest:
        return cmd_stamp(cfg, base)

    rows_path = manifest_path(cfg, base)
    if cmd == "set" and len(rest) == 2:
        cmd_set(rows_path, rest[0], rest[1])
    elif cmd == "rm" and len(rest) == 1:
        cmd_rm(rows_path, rest[0])
    elif cmd == "get" and len(rest) == 1:
        cmd_get(rows_path, rest[0])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
