#!/usr/bin/env python3
"""Contrôle d'intégrité du canal « Mémoire » (préférences), agnostique.

Format : un fait par fichier + frontmatter (`memory/<slug>.md`), `MEMORY.md` = index
(une ligne par fichier) — même motif que l'auto-memory personnelle de l'outil, appliqué
à la mémoire PARTAGÉE. Le frontmatter est chargeable mécaniquement (pas de regex sur une
ligne de prose) : deux clés, `source:` et `confiance:`, entre deux lignes `---`.

Suit `GABARIT.md` : `Finding` namedtuple, deux verdicts, règles pures, code retour 0/1/2.

Règles :
  R-NO-FRONTMATTER (BLOQUANT) — `memory/<slug>.md` ne commence pas par un bloc `---`.
  R-EXT-NO-CONF    (BLOQUANT) — `source: externe:...` sans champ `confiance:` du tout.
  R-ORPHAN-FILE    (BLOQUANT) — `memory/<slug>.md` existe mais aucune ligne de `MEMORY.md`
                                 ne le référence (`memory/<slug>.md`).
  R-DEAD-INDEX     (BLOQUANT) — une ligne de `MEMORY.md` référence `memory/<slug>.md` et
                                 le fichier n'existe pas.
  R-UNVERIFIED  (À-CONFIRMER) — `confiance: à vérifier` : candidate pour l'audit sémantique
                                 (étage 2, `memory-audit.md`) — pas une erreur en soi.

Lecture seule. Ne corrige rien — signale.

Usage :
  python3 checks/memory-check.py                 # MEMORY.md + memory/ par défaut
  python3 checks/memory-check.py --json
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import namedtuple

BLOQUANT = "BLOQUANT-AUTO"
CONFIRMER = "À-CONFIRMER"

Finding = namedtuple("Finding", "severity rule path line msg")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # …/ai-workflow
MEMORY_MD = os.path.join(ROOT, "MEMORY.md")
MEMORY_DIR = os.path.join(ROOT, "memory")

INDEX_LINK_RE = re.compile(r"\(memory/([\w.-]+\.md)\)")


def _norm(s: str) -> str:
    return s.strip().lower().replace("é", "e").replace("à", "a")


def parse_frontmatter(text: str):
    """Retourne (dict clé->valeur, a_frontmatter: bool). Ne lève jamais."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, False
    fm = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fm, True
        if ":" in line:
            k, v = line.split(":", 1)
            fm[_norm(k)] = v.strip()
    return fm, False  # jamais de second '---' → frontmatter mal formé


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT)


# --------------------------------------------------------------------------- #
# Règles pures                                                                 #
# --------------------------------------------------------------------------- #

def audit_memory_dir() -> list[Finding]:
    findings: list[Finding] = []
    if not os.path.isdir(MEMORY_DIR):
        return findings
    for fname in sorted(os.listdir(MEMORY_DIR)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(MEMORY_DIR, fname)
        text = open(fpath, encoding="utf-8").read()
        fm, closed = parse_frontmatter(text)

        if not closed:
            findings.append(Finding(BLOQUANT, "R-NO-FRONTMATTER", rel(fpath), 1,
                                     "pas de frontmatter --- ... --- en tête de fichier"))
            continue

        source = fm.get("source", "")
        conf = _norm(fm.get("confiance", ""))
        if source.lower().startswith("externe") and not fm.get("confiance"):
            findings.append(Finding(BLOQUANT, "R-EXT-NO-CONF", rel(fpath), 1,
                                     "source externe sans champ confiance:"))
        if conf == "a verifier":
            findings.append(Finding(CONFIRMER, "R-UNVERIFIED", rel(fpath), 1,
                                     "confiance: à vérifier — candidate pour l'audit sémantique"))
    return findings


def audit_index_concordance() -> list[Finding]:
    findings: list[Finding] = []
    files = set()
    if os.path.isdir(MEMORY_DIR):
        files = {f for f in os.listdir(MEMORY_DIR) if f.endswith(".md")}

    indexed = set()
    if os.path.isfile(MEMORY_MD):
        with open(MEMORY_MD, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                for m in INDEX_LINK_RE.finditer(line):
                    fname = m.group(1)
                    indexed.add(fname)
                    if fname not in files:
                        findings.append(Finding(BLOQUANT, "R-DEAD-INDEX", rel(MEMORY_MD), lineno,
                                                 f"référence memory/{fname} — fichier introuvable"))

    for fname in sorted(files - indexed):
        findings.append(Finding(BLOQUANT, "R-ORPHAN-FILE", rel(os.path.join(MEMORY_DIR, fname)), 1,
                                 "existe mais n'est référencé par aucune ligne de MEMORY.md"))
    return findings


# --------------------------------------------------------------------------- #
def main(argv) -> int:
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
