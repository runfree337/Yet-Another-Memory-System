#!/usr/bin/env python3
"""Contrôle d'intégrité du canal « Mémoire » (préférences), agnostique.

Format : un fait par fichier + frontmatter (`memory/<slug>.md`), `MEMORY.md` = index (une ligne
par fichier) — instance du méta-schéma `GABARIT-ENTREE.md`. Toute la logique de frontmatter/
concordance/liens vit dans la bibliothèque partagée `checks/entrylib.py` (un seul endroit définit
ce qu'est une entrée mémoire valide, réutilisé par `decisions-check.py` / `feature-map-check.py` /
`backlog-check.py`) — ce script se contente d'appeler `entrylib` avec le canal `"memory"` et
d'agréger.

Suit `checks/GABARIT.md` : `Finding` namedtuple à 5 champs, deux verdicts, code retour 0/1/2.

Table des règles (id → sévérité → ce qu'elle prouve) :

| Règle                      | Sévérité      | Prouve |
|-----------------------------|---------------|--------|
| `R-NO-FRONTMATTER`          | BLOQUANT-AUTO | `memory/<slug>.md` ne commence pas par un bloc `--- … ---`. |
| `R-MISSING-KEY`              | BLOQUANT-AUTO | une clé requise du canal (`id/source/confidence/created/updated`) est absente ou vide. |
| `R-BAD-VALUE`                | BLOQUANT-AUTO | `source:` ou `confidence:` ne respecte pas son vocabulaire fermé (`inferred\|human\|external:<réf>`, `verified\|unverified`). |
| `R-EXT-NO-CONF`              | BLOQUANT-AUTO | `source: external:...` sans champ `confidence` du tout — une source externe DOIT porter une confiance. |
| `R-BAD-DATE`                 | BLOQUANT-AUTO | `created`/`updated` n'est pas au format `AAAA-MM-JJ`. |
| `R-DEAD-LINK` (bloquant)     | BLOQUANT-AUTO | `links:` cite un id de décision `D-*` ou un chemin qui n'existe pas sur disque. |
| `R-ORPHAN-FILE`              | BLOQUANT-AUTO | `memory/<slug>.md` existe mais aucune ligne de `MEMORY.md` ne le référence. |
| `R-DEAD-INDEX`               | BLOQUANT-AUTO | une ligne de `MEMORY.md` référence `memory/<slug>.md` et le fichier n'existe pas. |
| `R-UNVERIFIED`               | À-CONFIRMER   | `confidence: unverified` — candidate pour l'audit sémantique (étage 2, `memory-audit.md`), pas une erreur en soi. |
| `R-VERIFIED-NOT-RATIFIED`    | À-CONFIRMER   | `confidence: verified` sans champ `ratified` — ratification humaine non tracée. |
| `R-DEAD-LINK` (à-confirmer)  | À-CONFIRMER   | `links:` cite un slug d'entrée introuvable dans `memory/`/`features/`/`backlog/` — le canal cible n'est peut-être pas encore peuplé. |

Ces ids sont l'API du canal — stables, grep-ables, cités par `checks/memory-audit.md` et les
docs. Le détail de chaque règle est défini une seule fois dans `checks/entrylib.py` ; ce fichier
ne les redéfinit jamais.

Lecture seule par défaut. Ne corrige rien — signale. `--stamp` est la seule écriture (voir plus
bas), bornée au champ `updated`.

Usage :
  python3 checks/memory-check.py                 # MEMORY.md + memory/ par défaut
  python3 checks/memory-check.py --json
  python3 checks/memory-check.py --stamp --staged # pré-commit uniquement
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entrylib  # noqa: E402

BLOQUANT = entrylib.BLOQUANT
CONFIRMER = entrylib.CONFIRMER
Finding = entrylib.Finding

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # racine du framework
MEMORY_MD = os.path.join(ROOT, "MEMORY.md")
MEMORY_DIR = os.path.join(ROOT, "memory")

# Une entrée mémoire n'a pas de grammaire d'id rigide (contrairement à `D-AAAA-MM-JJ-NN` côté
# décisions) — un `.md` nu ne suffit pas à prouver une référence (`MEMORY.md` en parle sans arrêt
# de `GABARIT-ENTREE.md`, `memory-audit.md`…). On ancre donc sur la FORME de lien du gabarit :
# soit un nom de fichier nu (`entries_dir`, ex. `mem-slug.md`), soit `(memory/<slug>.md)` dans le
# texte de l'index — jamais un `.md` flottant en prose.
ID_RE = re.compile(r"(?<=\(memory/)[\w.-]+\.md(?=\))|^[\w.-]+\.md$")


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT)


# --------------------------------------------------------------------------- #
# Règles pures — délèguent à entrylib, ce script ne fait qu'agréger.           #
# --------------------------------------------------------------------------- #

def audit_memory_dir() -> list:
    """Frontmatter + liens croisés de chaque `memory/<slug>.md`, via `entrylib`."""
    findings: list = []
    if not os.path.isdir(MEMORY_DIR):
        return findings
    for fname in sorted(os.listdir(MEMORY_DIR)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(MEMORY_DIR, fname)
        text = open(fpath, encoding="utf-8").read()
        meta, _body, _err = entrylib.parse_frontmatter(text)
        path = rel(fpath)
        findings += entrylib.validate_entry(path, meta, "memory")
        findings += entrylib.check_links(path, meta, ROOT)
    return findings


def audit_index_concordance() -> list:
    """Concordance `memory/<slug>.md` ⟺ lignes de `MEMORY.md`, via `entrylib`."""
    findings = entrylib.check_index_concordance(MEMORY_MD, MEMORY_DIR, ID_RE)
    return [f._replace(path=rel(f.path)) for f in findings]


# --------------------------------------------------------------------------- #
# --stamp — même triple garde-fou que backlog-check.py : scope stagé,         #
# champ mécanique (`updated`) seul, jamais bloquant.                          #
# --------------------------------------------------------------------------- #

def cmd_stamp(argv) -> int:
    """Pose `updated: <aujourd'hui>` sur les `memory/*.md` cités (ou stagés avec --staged) et
    re-stage. À câbler au pré-commit — la date du frontmatter suit la date du commit,
    mécaniquement (zéro pourrissement). Scope stagé uniquement : ne tire jamais un fichier hors
    du commit en cours."""
    import datetime
    today = datetime.date.today().isoformat()
    staged = "--staged" in argv

    if staged:
        r = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                            capture_output=True, text=True)
        files = [f for f in r.stdout.splitlines()
                 if f.replace("\\", "/").startswith("memory/") and f.endswith(".md")]
    else:
        files = [a for a in argv[argv.index("--stamp") + 1:] if not a.startswith("-")]

    changed = []
    for f in files:
        if not os.path.isfile(f):
            continue
        if entrylib.stamp_updated(f, today):
            changed.append(f)
            if staged:
                subprocess.run(["git", "add", f])

    print(f"memory-check : --stamp — {len(changed)} memory/*.md daté(s) à {today}.")
    return 0


# --------------------------------------------------------------------------- #
def main(argv) -> int:
    if "--stamp" in argv:
        return cmd_stamp(argv)

    as_json = "--json" in argv

    findings = audit_memory_dir() + audit_index_concordance()
    bloq = [f for f in findings if f.severity == BLOQUANT]
    conf = [f for f in findings if f.severity == CONFIRMER]

    if as_json:
        print(json.dumps([f._asdict() for f in findings], ensure_ascii=False, indent=2))
    else:
        for f in sorted(findings, key=lambda f: (f.severity != BLOQUANT, f.path, f.line)):
            print(f"{f.severity:14} {f.path}:{f.line}  {f.rule}  {f.msg}")
        print(f"\n— {len(findings)} finding(s) : {len(bloq)} bloquant-auto, {len(conf)} à-confirmer")

    return 2 if bloq else (1 if conf else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
