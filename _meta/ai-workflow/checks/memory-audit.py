#!/usr/bin/env python3
"""Orchestrateur déterministe d'AUDIT MÉMOIRE MULTI-CANAL — agnostique (étage 1).

La mémoire se tient en trois canaux (`../WORKFLOW.md §Les trois mémoires` : Feature,
Décision, Mémoire) — chacun a son propre contrôle d'intégrité (feature-map-check,
decisions-audit, memory-check). Ce script les ENCHAÎNE en un seul passage et résume,
sans dupliquer leur logique — même motif deux niveaux que le reste de `checks/` :

  Étage 1 — CE SCRIPT (mécanique, zéro jugement, zéro faux positif) :
    --tier1   lance feature-map-check + decisions-audit --tier1 (qui couvre déjà lui-même
              décisions/doc/index/backlog) + memory-check, résume par canal. Ne remplace
              AUCUN des trois — les délègue.
    (défaut)  --tier1 puis mode d'emploi étage 2.

  Étage 2 — REVUE SÉMANTIQUE (jugement), PAR CANAL :
    - Décision — recette + barème `decisions-audit.md` (le seul canal qui accumule assez
      pour justifier un découpage en lots — `decisions-audit.py --plan/--merge`).
    - Feature — chaque fiche est relue en ENTIER (FEATURE_MAP.md reste volontairement
      assez petit pour ça, cf. WORKFLOW.md) : la fiche décrit-elle encore la réalité du
      code cité ?
    - Mémoire — chaque entrée `à vérifier` de MEMORY.md (repérée par memory-check.py) est
      recoupée avec le code/une source fiable, ou ratifiée telle quelle.
    Barème détaillé des trois : voir `memory-audit.md`.

Le projet apporte ses propres contrôles de CODE et sa revue. Ici : la méthode, agnostique.

Lecture seule. Ne corrige/supprime/archive RIEN. La ratification reste humaine.

Usage :
  python3 checks/memory-audit.py            # --tier1 + mode d'emploi
  python3 checks/memory-audit.py --tier1 [--json]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

CHECKS = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python3"

TIER1 = [
    ("feature",   [PY, os.path.join(CHECKS, "feature-map-check.py")]),
    ("decisions", [PY, os.path.join(CHECKS, "decisions-audit.py"), "--tier1"]),
    ("memory",    [PY, os.path.join(CHECKS, "memory-check.py")]),
]


def run_tier1(as_json: bool) -> int:
    results = []
    worst = 0
    for label, cmd in TIER1:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        code = proc.returncode
        worst = max(worst, code)
        tail = (proc.stdout.strip().splitlines() or [""])[-1]
        results.append({"canal": label, "code": code, "resume": tail})

    if as_json:
        print(json.dumps({"canaux": results, "code": worst}, ensure_ascii=False, indent=2))
        return worst

    for r in results:
        mark = "[OK]" if r["code"] == 0 else ("[BLOQUANT]" if r["code"] >= 2 else "[à confirmer]")
        print(f"{mark} {r['canal']:10} {r['resume']}")

    print()
    if worst == 0:
        print("Étage 1 propre sur les 3 canaux. Audit sémantique possible à la demande.")
    elif worst == 1:
        print("Candidats à confirmer — pas bloquant, mais un passage étage 2 est recommandé.")
    else:
        print("Dérive bloquante détectée — corriger avant d'envisager l'étage 2 (memory-audit.md).")
    return worst


def usage() -> int:
    print("usage: memory-audit.py [--tier1] [--json]", file=sys.stderr)
    print("  --tier1  lance les 4 contrôles d'intégrité (feature, décisions, mémoire, backlog)", file=sys.stderr)
    print("  (défaut) équivalent à --tier1", file=sys.stderr)
    return 0


def main(argv) -> int:
    as_json = "--json" in argv
    return run_tier1(as_json)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
