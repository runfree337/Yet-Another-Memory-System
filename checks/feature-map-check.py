#!/usr/bin/env python3
"""Linter déterministe de `FEATURE_MAP.md` (zéro faux positif) — version agnostique.

La carte des features doit rester scannable et non-menteuse. Ce linter vérifie la
STRUCTURE des fiches ; il NE corrige rien — signale. Motif `backlog-check` :
déterministe, consultatif (hook / manuel).

Vérifs :
  FM1  (erreur)    chaque fiche porte ses clés-cœur : une ligne `**Rôle`, ≥ 1 chemin de
                   fichier (code), ≥ 1 référence durable (clé `**Doc` durable OU id `D-*`).
  FM2  (erreur)    Sommaire ↔ fiches : ancres GitHub concordantes (si un `## Sommaire` existe).
  FM5  (erreur)    durable-only : aucune fiche ne cite `backlog/` (transitoire — vit au backlog).
  FM4  (candidat)  granularité : corps de fiche > seuil → alerte de découpage (soft).

Le DEAD-PATH (chemin cité introuvable) est HORS scope : voir `doc-refs-check.py`.

⚠️ **Patterns à adapter au projet** : `DURABLE`, `TRANSITOIRE` et la détection de « code »
dépendent du layout du projet hôte (où vivent sa doc durable, son backlog, son code). Les
valeurs ci-dessous sont des défauts raisonnables ; un projet les ajuste à son arborescence.

Usage : python3 checks/feature-map-check.py [--json]
Code retour : 2 si ≥1 erreur, 1 si seulement des candidats, 0 sinon.
"""
from __future__ import annotations

import json
import os
import re
import sys

ERREUR = "ERREUR"
CANDIDAT = "CANDIDAT"
FM4_SEUIL = 16

# --- Patterns (défauts agnostiques — à adapter au layout du projet) ---
CODE = re.compile(r"(?:[\w.\-]+/)+[\w.\-]+\.[A-Za-z0-9]{1,6}")  # un chemin de fichier
DURABLE_KEY = re.compile(r"^\*\*\s*Doc", re.IGNORECASE)          # clé « **Doc (durable) :** »
DECISION = re.compile(r"\bD-\d{4}-\d{2}-\d{2}-\d{2}\b")
TRANSITOIRE = re.compile(r"\bbacklog/")
ROLE = re.compile(r"^\*\*\s*Rôle\b", re.IGNORECASE)
SOMMAIRE_LINK = re.compile(r"\[([^\]]+)\]\(#([^)]+)\)")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ai-workflow/
FMAP = os.path.join(ROOT, "FEATURE_MAP.md")


def gh_anchor(title):
    s = title.strip().lower()
    s = re.sub(r"[^\w\s\-]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s", "-", s)
    return s


def parse(text):
    lines = text.splitlines()
    sommaire_anchors, fiches = set(), []
    in_sommaire = False
    cur_title, cur_body = None, []
    for line in lines:
        h = re.match(r"^##\s+(.+?)\s*$", line)
        if h:
            title = h.group(1).strip()
            if cur_title is not None:
                fiches.append((cur_title, cur_body))
                cur_title, cur_body = None, []
            if title.lower().startswith("sommaire"):
                in_sommaire = True
                continue
            in_sommaire = False
            cur_title, cur_body = title, []
            continue
        if line.startswith("# "):
            continue
        if in_sommaire:
            for m in SOMMAIRE_LINK.finditer(line):
                sommaire_anchors.add(m.group(2).strip().lstrip("#"))
        elif cur_title is not None:
            cur_body.append(line)
    if cur_title is not None:
        fiches.append((cur_title, cur_body))
    return sommaire_anchors, fiches


def check(out):
    if not os.path.isfile(FMAP):
        return
    with open(FMAP, encoding="utf-8") as f:
        text = f.read()
    sommaire_anchors, fiches = parse(text)
    fiches = [(t, b) for t, b in fiches if "gabarit" not in t.lower()]
    fiche_anchors = {gh_anchor(t): t for t, _ in fiches}

    # FM2 — seulement si un Sommaire est présent (certaines petites cartes n'en ont pas)
    if sommaire_anchors:
        for anc in sorted(sommaire_anchors):
            if anc not in fiche_anchors:
                out.append((ERREUR, "FM2-sommaire", anc, f"ancre « #{anc} » du Sommaire ne pointe aucune fiche."))
        for anc, titre in sorted(fiche_anchors.items()):
            if anc not in sommaire_anchors:
                out.append((ERREUR, "FM2-fiche", titre, f"fiche « {titre} » absente du Sommaire."))

    for titre, body in fiches:
        joined = "\n".join(body)
        useful = [l for l in body if l.strip() and not l.strip().startswith("|---")]
        if not any(ROLE.match(l.strip()) for l in body):
            out.append((ERREUR, "FM1-role", titre, "pas de clé-cœur `**Rôle :**`."))
        if not CODE.search(joined):
            out.append((ERREUR, "FM1-code", titre, "aucun chemin de fichier (code)."))
        if not (any(DURABLE_KEY.match(l.strip()) for l in body) or DECISION.search(joined)):
            out.append((ERREUR, "FM1-durable", titre, "aucune réf durable (clé `**Doc` durable ou id `D-*`)."))
        for m in TRANSITOIRE.finditer(joined):
            out.append((ERREUR, "FM5-transitoire", titre, f"référence transitoire « {m.group(0)}… » — vit au backlog."))
        if len(useful) > FM4_SEUIL:
            out.append((CANDIDAT, "FM4-granularite", titre, f"{len(useful)} lignes utiles (> {FM4_SEUIL}) → envisager un découpage."))


def main(argv):
    out = []
    check(out)
    if "--json" in argv:
        print(json.dumps([{"severity": s, "rule": r, "where": w, "msg": m} for s, r, w, m in out],
                         ensure_ascii=False, indent=2))
    else:
        if not out:
            print("feature-map-check : OK.")
        else:
            order = {ERREUR: 0, CANDIDAT: 1}
            for s, r, w, m in sorted(out, key=lambda f: (order[f[0]], f[1], f[2])):
                print(f"  [{r}] {w} — {m}")
    if any(s == ERREUR for s, *_ in out):
        return 2
    if any(s == CANDIDAT for s, *_ in out):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
