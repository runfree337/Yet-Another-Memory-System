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

  Le résumé par canal Feature/Mémoire s'enrichit, quand c'est simple, de compteurs fins
  utiles à l'étage 2 (`memory-audit.md §Le flux`) — relancés depuis le `--json` du check
  sous-jacent : `R-UNVERIFIED` / `R-VERIFIED-NOT-RATIFIED` (canal Mémoire), `FM-FRESH` /
  `FM-GRAN` (canal Feature). Tolérant par construction : `--json` indisponible, sortie
  illisible ou champ absent -> pas de compteurs, le résumé retombe sur le comptage actuel
  (code retour + dernière ligne texte) sans jamais planter.

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

# Compteurs fins optionnels par canal — un canal absent de cette table (ex. "decisions",
# déjà agrégé par decisions-audit.py) n'est simplement pas enrichi. Clés = ids de règle
# `entrylib`/canal, directement grep-ables (mêmes ids que `memory-audit.md`).
EXTRA_COUNTS = {
    "memory":  ("R-UNVERIFIED", "R-VERIFIED-NOT-RATIFIED"),
    "feature": ("FM-FRESH", "FM-GRAN"),
}


def _json_findings(cmd: list[str]):
    """Relance `cmd` + `--json`, retourne la liste de `Finding` (dicts) — `None` si le
    check ne supporte pas `--json`, si la sortie n'est pas un JSON de liste, ou sur toute
    autre erreur (timeout, script absent…). Ne lève jamais — c'est un enrichissement,
    jamais un chemin bloquant."""
    try:
        proc = subprocess.run(cmd + ["--json"], capture_output=True, text=True, timeout=30)
        data = json.loads(proc.stdout)
        return data if isinstance(data, list) else None
    except Exception:
        return None


def _channel_counts(label: str, cmd: list[str]) -> dict:
    """Compteurs `{rule: n}` pour les règles utiles à l'étage 2 de ce canal (voir
    `EXTRA_COUNTS`). `{}` si le canal n'a pas de compteurs définis, ou si `_json_findings`
    échoue — retombe alors silencieusement sur le comptage actuel (code + dernière ligne)."""
    rules = EXTRA_COUNTS.get(label)
    if not rules:
        return {}
    findings = _json_findings(cmd)
    if findings is None:
        return {}
    return {
        rule: sum(1 for f in findings if isinstance(f, dict) and f.get("rule") == rule)
        for rule in rules
    }


def run_tier1(as_json: bool) -> int:
    results = []
    worst = 0
    for label, cmd in TIER1:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        code = proc.returncode
        worst = max(worst, code)
        tail = (proc.stdout.strip().splitlines() or [""])[-1]
        entry = {"canal": label, "code": code, "resume": tail}
        counts = _channel_counts(label, cmd)
        if counts:
            entry["compteurs"] = counts
        results.append(entry)

    if as_json:
        print(json.dumps({"canaux": results, "code": worst}, ensure_ascii=False, indent=2))
        return worst

    for r in results:
        mark = "[OK]" if r["code"] == 0 else ("[BLOQUANT]" if r["code"] >= 2 else "[à confirmer]")
        line = f"{mark} {r['canal']:10} {r['resume']}"
        if r.get("compteurs"):
            line += "  (" + ", ".join(f"{rule}={n}" for rule, n in r["compteurs"].items()) + ")"
        print(line)

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
