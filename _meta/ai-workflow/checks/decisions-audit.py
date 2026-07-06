#!/usr/bin/env python3
"""Orchestrateur déterministe d'AUDIT DU JOURNAL DE DÉCISIONS — agnostique (premier étage).

Le journal de décisions doit être audité périodiquement — déclencheur « Volume » du
modèle de pruning quand l'INDEX gonfle. L'audit a DEUX natures, traitées séparément
(même motif deux niveaux que le reste de `checks/`) :

  Étage 1 — CE SCRIPT (mécanique, zéro jugement, zéro faux positif) :
    --tier1   lance les contrôles d'intégrité du framework (decisions, backlog) et résume.
    --plan    découpe `decisions/INDEX.md` en lots ÉQUILIBRÉS → offset/limit/ids par lot.
              (Supprime le découpage manuel : une revue par lot.)
    --merge   agrège les sorties de revue (format strict `id | VERDICT | … | confiance:…`)
              → rapport classé + CONTRÔLE DE COUVERTURE (chaque id audité exactement 1×).
    (défaut)  --tier1 puis --plan + mode d'emploi.

  Étage 2 — REVUE SÉMANTIQUE (jugement) : recoupe chaque décision avec le CODE réel
            (retrieve-then-verify), classe sujet disparu / invariant migré / redondance /
            drift mémoire↔code / conflit. Assurée par la revue du projet (un agent, la skill
            de review, ou un humain). Barème : voir `MEMORY.md` et `decisions/README.md`.

Portée = le journal de décisions uniquement. Pour l'audit multi-canal (feature/décision/
préférences), voir `memory-audit.py` (orchestrateur, appelle celui-ci pour son volet
décisions).

Le projet apporte ses propres contrôles de CODE et sa revue. Ici : la méthode, agnostique.

Lecture seule. Ne corrige/supprime/archive RIEN. La ratification reste humaine — rien
n'est élagué en silence (cf. `MEMORY.md §Provenance`, `decisions/README.md §pruning`).

Usage :
  python3 checks/decisions-audit.py                       # tier1 + plan
  python3 checks/decisions-audit.py --plan [--batch-size 33] [--json]
  python3 checks/decisions-audit.py --merge revue1.txt …  # agrège + couverture
  python3 checks/decisions-audit.py --index <chemin/INDEX.md>   # autre journal
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # …/ai-workflow
CHECKS = os.path.dirname(os.path.abspath(__file__))
INDEX_DEFAULT = os.path.join(ROOT, "decisions", "INDEX.md")

ID_RE = re.compile(r"^(D-\d{4}-\d{2}-\d{2}-\d{2})\b")
ANY_ID_RE = re.compile(r"D-\d{4}-\d{2}-\d{2}-\d{2}")
VERDICTS = {"ARCHIVER-1", "ARCHIVER-4", "REDONDANTE", "DRIFT-CODE", "CONFLIT", "DOUTE"}

TIER1 = [
    ("décisions (fichier↔INDEX)",   "decisions-check.py"),
    ("backlog (intégrité process)", "backlog-check.py"),
    ("réfs mortes doc",             "doc-refs-check.py"),
    ("intégrité index",             "index-check.py"),
]


def parse_entries(index_path: str):
    if not os.path.isfile(index_path):
        return [], 0
    with open(index_path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    entries = [(i, ID_RE.match(l).group(1)) for i, l in enumerate(lines, 1) if ID_RE.match(l)]
    return entries, len(lines)


def make_batches(entries, total_lines, batch_size):
    batches = []
    for start in range(0, len(entries), batch_size):
        chunk = entries[start:start + batch_size]
        first = chunk[0][0]
        nxt = start + batch_size
        last = entries[nxt][0] - 1 if nxt < len(entries) else total_lines
        batches.append({"batch": len(batches) + 1, "offset": first,
                        "limit": last - first + 1, "count": len(chunk),
                        "ids": [e[1] for e in chunk]})
    return batches


def cmd_plan(index_path, batch_size, as_json) -> int:
    entries, total = parse_entries(index_path)
    if not entries:
        print(f"PLAN : aucune décision dans {os.path.relpath(index_path, ROOT)} "
              "(journal vide — rien à auditer).")
        return 0
    batches = make_batches(entries, total, batch_size)
    if as_json:
        print(json.dumps({"entries": len(entries), "batches": batches},
                         ensure_ascii=False, indent=2))
        return 0
    print(f"PLAN D'AUDIT — {len(entries)} décisions, {len(batches)} lot(s) de ~{batch_size}.")
    print("Confier un lot par reviewer, avec l'offset/limit indiqué :\n")
    for b in batches:
        print(f"  Lot {b['batch']} — lire offset={b['offset']} limit={b['limit']} "
              f"({b['count']} décisions : {b['ids'][0]} … {b['ids'][-1]})")
    print("\nPuis : python3 checks/decisions-audit.py --merge <sorties_revue…>")
    return 0


def cmd_tier1() -> int:
    print("ÉTAGE 1 — INTÉGRITÉ MÉMOIRE (mécanique, zéro-FP)\n")
    worst = 0
    for label, script in TIER1:
        path = os.path.join(CHECKS, script)
        if not os.path.isfile(path):
            print(f"  ⨯ {label} : {script} absent — ignoré")
            continue
        r = subprocess.run([sys.executable, path], cwd=ROOT, capture_output=True, text=True)
        worst = max(worst, r.returncode)
        mark = "OK " if r.returncode == 0 else ("?? " if r.returncode == 1 else "!! ")
        tail = (r.stdout.strip().splitlines() or [""])[-1]
        print(f"  [{mark}] {label} : exit={r.returncode}  {tail}")
    verdict = "OK" if worst == 0 else ("écart(s)" if worst >= 2 else "OK (à confirmer)")
    print(f"\nVerdict étage 1 : {verdict}.")
    return worst


def parse_review(text: str):
    flagged, gardees = [], set()
    for line in text.splitlines():
        s = line.strip()
        if s.upper().startswith("GARD"):
            gardees.update(ANY_ID_RE.findall(s)); continue
        if "|" in s:
            parts = [p.strip() for p in s.split("|")]
            m = ID_RE.match(parts[0])
            if m and len(parts) >= 2 and parts[1] in VERDICTS:
                flagged.append((m.group(1), parts[1], " | ".join(parts[2:])))
    return flagged, gardees


def cmd_merge(files, index_path) -> int:
    entries, _ = parse_entries(index_path)
    all_ids = {e[1] for e in entries}
    flagged, seen = [], {}
    for f in files:
        try:
            fl, ga = parse_review(open(f, encoding="utf-8").read())
        except OSError as e:
            print(f"⨯ illisible : {f} ({e})", file=sys.stderr); continue
        for fid, v, rest in fl:
            flagged.append((fid, v, rest)); seen[fid] = seen.get(fid, 0) + 1
        for gid in ga:
            seen[gid] = seen.get(gid, 0) + 1

    print("RAPPORT D'AUDIT — agrégé\n")
    by_v = {}
    for fid, v, rest in flagged:
        by_v.setdefault(v, []).append((fid, rest))
    for v in ["DRIFT-CODE", "CONFLIT", "ARCHIVER-1", "ARCHIVER-4", "REDONDANTE", "DOUTE"]:
        if by_v.get(v):
            print(f"## {v}  ({len(by_v[v])})")
            for fid, rest in by_v[v]:
                print(f"  {fid} | {rest}")
            print()

    audited = set(seen)
    missing = sorted(all_ids - audited)
    dups = sorted(i for i, n in seen.items() if n > 1)
    print("## COUVERTURE")
    print(f"  décisions à l'INDEX : {len(all_ids)}  ·  auditées : {len(audited & all_ids)}  "
          f"·  signalées : {len(flagged)}")
    rc = 0
    if missing:
        print(f"  !! NON AUDITÉES ({len(missing)}) : {' '.join(missing)}"); rc = 1
    if dups:
        print(f"  !! AUDITÉES >1× ({len(dups)}) : {' '.join(dups)}"); rc = 1
    if not missing and not dups and all_ids:
        print("  OK couverture complète : chaque décision auditée exactement une fois.")
    print("\nRappel : ce rapport SIGNALE. Aucun élagage sans ratification humaine. "
          "Tout élagage reste journalisé.")
    return rc


VOLUME_ALERTE = 285   # l'INDEX approche du seuil d'audit (~300) → recommander l'étage 2


def _report_dir(arg):
    """Dossier du rapport : argument > $UC_MEMORY_REPORT_DIR > défaut .memory-reports/ (à gitignorer)."""
    d = arg or os.environ.get("UC_MEMORY_REPORT_DIR") or os.path.join(ROOT, ".memory-reports")
    return d if os.path.isabs(d) else os.path.join(ROOT, d)


def cmd_report(report_dir) -> int:
    """Écrit un rapport déterministe (étage 1). Pensé pour un cron OS (headless, SANS LLM) :
    l'hôte le surface au démarrage de session, l'utilisateur décide de le traiter (étage 2)."""
    import datetime
    today = datetime.date.today().isoformat()
    results, worst = [], 0
    for label, script in TIER1:
        path = os.path.join(CHECKS, script)
        if not os.path.isfile(path):
            results.append((label, None, f"{script} absent")); continue
        r = subprocess.run([sys.executable, path], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        worst = max(worst, r.returncode)
        results.append((label, r.returncode, (r.stdout.strip().splitlines() or [""])[-1]))
    n_dec = len(parse_entries(INDEX_DEFAULT)[0])
    recommend = (worst >= 2) or (n_dec >= VOLUME_ALERTE)
    rdir = _report_dir(report_dir); os.makedirs(rdir, exist_ok=True)
    rpath = os.path.join(rdir, "memory-report.md")
    out = [f"# Rapport mémoire — {today}", "",
           "> Produit par le cron OS (étage 1 déterministe, **sans LLM**). À traiter en session :",
           "> l'agent demande, **l'utilisateur décide**. Supprimer une fois traité.", "",
           "## Étage 1 — intégrité", ""]
    for label, code, tail in results:
        mark = "[OK]" if code == 0 else ("[BLOQUANT]" if (code or 0) >= 2
               else ("[à confirmer]" if code == 1 else "[absent]"))
        out.append(f"- {mark} {label} — {tail}")
    out += ["", "## Décisions", "", f"- {n_dec} à l'INDEX (alerte ≥ {VOLUME_ALERTE}).", "",
            "## Verdict", "",
            ("**Audit sémantique recommandé** — lancer l'étage 2 (agents décision↔code) puis ratifier."
             if recommend else "**Rien d'urgent** — un audit reste possible à la demande."), ""]
    with open(rpath, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    print(f"rapport écrit : {rpath} (audit sémantique {'recommandé' if recommend else 'non requis'})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Orchestrateur d'audit mémoire (étage 1, agnostique).")
    ap.add_argument("--tier1", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--merge", nargs="+", metavar="FICHIER")
    ap.add_argument("--report", nargs="?", const="", metavar="DIR",
                    help="rapport déterministe (cron OS) ; DIR ou $UC_MEMORY_REPORT_DIR ou défaut .memory-reports/")
    ap.add_argument("--batch-size", type=int, default=33)
    ap.add_argument("--index", default=INDEX_DEFAULT)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.report is not None:
        return cmd_report(a.report or None)
    if a.merge:
        return cmd_merge(a.merge, a.index)
    if a.plan and not a.tier1:
        return cmd_plan(a.index, a.batch_size, a.json)
    if a.tier1 and not a.plan:
        return cmd_tier1()
    rc = cmd_tier1(); print(); cmd_plan(a.index, a.batch_size, False)
    return rc


if __name__ == "__main__":
    sys.exit(main())
