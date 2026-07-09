#!/usr/bin/env python3
"""Contrôle déterministe du canal « Décision » (zéro faux positif).

Le canal Décision est une instance de `ENTRY-TEMPLATE.md` (cf. `decisions/README.md`) : un
frontmatter commun (`entrylib.CHANNELS["decision"]`) au-dessus de trois rubriques en prose
(Décision/Pourquoi/Invariant), une ligne d'`INDEX.md` par fichier, une révocation/archivage
= transition de `status` + liens `replaces`/`replaced-by`. Ce script vérifie les SEPT
invariants mécaniques — NE corrige rien, **signale**.

Règles (identifiants stables — API, ne pas renommer) :
  D1  Tout fichier `D-AAAA-MM-JJ-NN.md` a une ligne `D-AAAA-MM-JJ-NN` dans INDEX.md.
  D2  Tout identifiant `D-…` cité dans INDEX.md a un fichier `D-….md`.
  D3  Frontmatter complet et valide pour le canal « decision » (via `entrylib.validate_entry`,
      règles remontées telles quelles : R-NO-FRONTMATTER, R-MISSING-KEY, R-BAD-VALUE,
      R-EXT-NO-CONF, R-UNVERIFIED, R-VERIFIED-NOT-RATIFIED, R-BAD-DATE).
  D4  Les trois rubriques canoniques (**Décision**, **Pourquoi**, **Invariant**) sont présentes
      dans le corps.
  D5  `status` ⟺ section de INDEX.md : une entrée `archived` référencée sous « ## Actives »,
      ou une `active` référencée sous « ## Archivées », est bloquante (`revoked` n'est pas
      contraint — les deux sections sont légitimes selon `decisions/README.md §4-5`).
  D6  Graphe de révocation sain : `replaced-by`/`replaces` pointent des ids existants,
      réciprocité (`A.replaced-by = B` ⟹ `B.replaces` contient `A`), aucun cycle.
  D7  Liens croisés inter-canaux (`links:`) résolus, via `entrylib.check_links` (règle
      remontée telle quelle : R-DEAD-LINK).

Code retour (`checks/TEMPLATE.md`) : 2 si ≥1 bloquant, 1 si seulement des à-confirmer, 0 sinon.

Usage :
  python3 checks/decisions-check.py
  python3 checks/decisions-check.py --json
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entrylib
from entrylib import BLOQUANT, CONFIRMER, Finding

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # …/ai-workflow
DEC = os.path.join(ROOT, "decisions")
INDEX = os.path.join(DEC, "INDEX.md")

ID_RE = re.compile(r"D-\d{4}-\d{2}-\d{2}-\d{2}")
CANONICAL_HEADINGS = ("**Décision**", "**Pourquoi**", "**Invariant**")


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT)


def _decision_files() -> dict:
    """`{id: nom_de_fichier}` pour chaque `D-AAAA-MM-JJ-NN.md` sous `decisions/`."""
    files = {}
    if not os.path.isdir(DEC):
        return files
    for fname in sorted(os.listdir(DEC)):
        if not fname.endswith(".md"):
            continue
        m = ID_RE.fullmatch(fname[: -len(".md")])
        if m:
            files[m.group(0)] = fname
    return files


def _as_list(v) -> list:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return list(v)


# --------------------------------------------------------------------------- #
# D1 / D2 — concordance fichier <-> index, via entrylib (mappage direct).     #
# --------------------------------------------------------------------------- #

def rule_d1_d2() -> list:
    """`entrylib.check_index_concordance` scanne l'index avec `pat.finditer(line)` — la nouvelle
    ligne d'index `- [<id>](<id>.md) — …` répète l'id deux fois (texte du lien + chemin), donc
    un même écart `D2` peut sortir deux fois pour une seule ligne. On déduplique par
    `(rule, path, line, msg)` — la même dérive ne doit être signalée qu'une fois. On relativise
    aussi les chemins absolus incrustés dans le message (construits par `entrylib` à partir des
    chemins passés, ici absolus)."""
    if not os.path.isdir(DEC):
        return []
    raw = entrylib.check_index_concordance(INDEX, DEC, ID_RE)
    renamed = {"R-ORPHAN-FILE": "D1", "R-DEAD-INDEX": "D2"}

    seen = set()
    findings = []
    for f in raw:
        rule = renamed.get(f.rule, f.rule)
        path = rel(f.path)
        msg = f.msg.replace(ROOT + os.sep, "").replace(ROOT, ".")
        key = (rule, path, f.line, msg)
        if key in seen:
            continue
        seen.add(key)
        findings.append(Finding(f.severity, rule, path, f.line, msg))
    return findings


# --------------------------------------------------------------------------- #
# D4 — rubriques canoniques présentes dans le corps.                          #
# --------------------------------------------------------------------------- #

def rule_d4(path: str, body: str) -> list:
    missing = [h for h in CANONICAL_HEADINGS if h not in body]
    if not missing:
        return []
    return [Finding(BLOQUANT, "D4", path, 1,
                     f"rubrique(s) canonique(s) manquante(s) dans le corps : {', '.join(missing)}")]


# --------------------------------------------------------------------------- #
# D5 — status <-> section de INDEX.md.                                        #
# --------------------------------------------------------------------------- #

def _index_sections() -> tuple:
    """`(ids sous ## Actives, ids sous ## Archivées)` — découpe INDEX.md à la première ligne
    `## Archiv...`. Tout ce qui précède = Actives, tout ce qui suit (incluse) = Archivées."""
    if not os.path.isfile(INDEX):
        return set(), set()
    text = open(INDEX, encoding="utf-8").read()
    m = re.search(r"(?m)^##\s*Archiv", text)
    actives_text, archived_text = (text[: m.start()], text[m.start():]) if m else (text, "")
    return set(ID_RE.findall(actives_text)), set(ID_RE.findall(archived_text))


def rule_d5(idv: str, path: str, meta: dict, actives_ids: set, archived_ids: set) -> list:
    status = meta.get("status")
    if not idv or not status:
        return []  # frontmatter déjà signalé par D3
    findings = []
    if status == "archived" and idv in actives_ids:
        findings.append(Finding(BLOQUANT, "D5", path, 1,
                                 f"status: archived mais « {idv} » référencé sous « ## Actives » "
                                 f"de {rel(INDEX)}"))
    if status == "active" and idv in archived_ids:
        findings.append(Finding(BLOQUANT, "D5", path, 1,
                                 f"status: active mais « {idv} » référencé sous « ## Archivées » "
                                 f"de {rel(INDEX)}"))
    return findings


# --------------------------------------------------------------------------- #
# D6 — graphe de révocation : cibles existantes, réciprocité, pas de cycle.   #
# --------------------------------------------------------------------------- #

def rule_d6(by_id: dict) -> list:
    """`by_id` : `{id: (path, meta)}`. Règle pure sur le graphe entier (portée cross-fichier,
    ne peut pas s'exprimer par-fichier comme D4/D5)."""
    findings = []

    for idv, (path, meta) in sorted(by_id.items()):
        rb = meta.get("replaced-by")
        if rb:
            if rb not in by_id:
                findings.append(Finding(BLOQUANT, "D6", path, 1,
                                         f"replaced-by: « {rb} » — aucun fichier decisions/{rb}.md"))
            else:
                target_replaces = _as_list(by_id[rb][1].get("replaces"))
                if idv not in target_replaces:
                    findings.append(Finding(BLOQUANT, "D6", path, 1,
                                             f"replaced-by: « {rb} » sans réciproque — "
                                             f"{rb}.replaces ne contient pas « {idv} »"))
        for r in _as_list(meta.get("replaces")):
            if r not in by_id:
                findings.append(Finding(BLOQUANT, "D6", path, 1,
                                         f"replaces: « {r} » — aucun fichier decisions/{r}.md"))

    # Cycles sur le graphe replaced-by (DFS itératif, un finding par cycle distinct).
    reported = set()
    for start in by_id:
        chain = []
        cur = start
        while cur in by_id:
            if cur in chain:
                cycle = tuple(sorted(chain[chain.index(cur):]))
                if cycle not in reported:
                    reported.add(cycle)
                    anchor = by_id[cycle[0]][0]
                    findings.append(Finding(BLOQUANT, "D6", anchor, 1,
                                             f"cycle détecté dans le graphe replaced-by : "
                                             f"{' → '.join(cycle)}"))
                break
            chain.append(cur)
            cur = by_id[cur][1].get("replaced-by")

    return findings


# --------------------------------------------------------------------------- #
# Orchestration.                                                               #
# --------------------------------------------------------------------------- #

def audit() -> list:
    findings = list(rule_d1_d2())

    files = _decision_files()
    by_id = {}
    loaded = []  # (path, meta, body) dans l'ordre de découverte
    for idv, fname in files.items():
        fpath = os.path.join(DEC, fname)
        text = open(fpath, encoding="utf-8").read()
        meta, body, err = entrylib.parse_frontmatter(text)
        loaded.append((fpath, meta, body))
        if meta.get("id"):
            by_id[meta.get("id")] = (rel(fpath), meta)

    actives_ids, archived_ids = _index_sections()

    for fpath, meta, body in loaded:
        p = rel(fpath)
        # D3 — frontmatter complet et valide (findings remontés tels quels).
        findings += entrylib.validate_entry(p, meta, "decision")
        # D4 — rubriques canoniques.
        findings += rule_d4(p, body)
        # D5 — status <-> section INDEX.
        findings += rule_d5(meta.get("id"), p, meta, actives_ids, archived_ids)
        # D7 — liens croisés inter-canaux (findings remontés tels quels).
        findings += entrylib.check_links(p, meta, ROOT)

    # D6 — graphe de révocation, portée cross-fichier.
    findings += rule_d6(by_id)

    return findings


def main(argv) -> int:
    as_json = "--json" in argv

    if not os.path.isdir(DEC):
        if as_json:
            print(json.dumps([], ensure_ascii=False))
        else:
            print("decisions-check : pas de dossier decisions/ — rien à vérifier.")
        return 0

    findings = audit()
    bloq = [f for f in findings if f.severity == BLOQUANT]
    conf = [f for f in findings if f.severity == CONFIRMER]

    if as_json:
        print(json.dumps([f._asdict() for f in findings], ensure_ascii=False, indent=2))
    else:
        for f in sorted(findings, key=lambda f: (f.severity != BLOQUANT, f.path, f.line, f.rule)):
            print(f"{f.severity:14} {f.path}:{f.line}  {f.rule}  {f.msg}")
        if findings:
            print(f"\n— {len(findings)} finding(s) : {len(bloq)} bloquant-auto, {len(conf)} à-confirmer")
        else:
            print("decisions-check : OK.")

    return 2 if bloq else (1 if conf else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
