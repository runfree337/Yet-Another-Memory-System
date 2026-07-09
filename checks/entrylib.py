#!/usr/bin/env python3
"""Bibliothèque partagée « entrée mémoire » — PAS un check autonome, stdlib uniquement.

Généralise le motif porté par `memory-check.py` (frontmatter + concordance fichier↔index) à
tous les canaux mémoire (`GABARIT-ENTREE.md`) : Mémoire, Décision, Feature, Backlog. Les checks
de canal important cette lib au lieu de redéfinir leur propre parseur/regex — **un seul endroit**
définit ce qu'est une entrée mémoire valide.

Suit `checks/GABARIT.md` : `Finding` namedtuple à 5 champs, deux verdicts (`BLOQUANT-AUTO` /
`À-CONFIRMER`), règles pures, aucun effet de bord.

Vocabulaire de frontmatter — clés/valeurs en ANGLAIS par conception (API machine, greppable ;
la prose du corps reste dans la langue de l'équipe, cf. `GABARIT-ENTREE.md`) :
  id, status, source, confidence, created, updated, links, ratified
  source     : inferred | human | external:<réf>
  confidence : verified | unverified
  ratified   : <qui>, <AAAA-MM-JJ>  — requis pour passer confidence: verified

Usage :
  import sys; sys.path.insert(0, "checks"); import entrylib   # depuis un autre check
  python3 checks/entrylib.py --selftest                       # seul mode exécutable
"""
from __future__ import annotations

import os
import re
import sys
from collections import namedtuple

# --------------------------------------------------------------------------- #
# Le gabarit (checks/GABARIT.md) — Finding + deux verdicts.                   #
# --------------------------------------------------------------------------- #

BLOQUANT = "BLOQUANT-AUTO"
CONFIRMER = "À-CONFIRMER"

Finding = namedtuple("Finding", "severity rule path line msg")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SOURCE_RE = re.compile(r"^(inferred|human|external:.+)$")
CONFIDENCE_VALUES = {"verified", "unverified"}


# --------------------------------------------------------------------------- #
# Spec par canal — clés requises/optionnelles + enums propres au canal.       #
# Vocabulaire commun (id/source/confidence/created/updated/links/ratified)    #
# validé par des règles génériques ; `enums` ne porte que les clés PROPRES    #
# au canal (ex. `status`) dont les valeurs varient d'un canal à l'autre.      #
# --------------------------------------------------------------------------- #

CHANNELS = {
    "memory": {
        "required": ("id", "source", "confidence", "created", "updated"),
        "optional": ("links", "ratified"),
        "enums": {},
        "nullable": (),
    },
    "decision": {
        "required": ("id", "status", "source", "confidence", "created", "updated"),
        "optional": ("links", "replaces", "replaced-by", "ratified"),
        "enums": {"status": {"active", "revoked", "archived"}},
        "nullable": (),
    },
    "feature": {
        "required": ("id", "created", "updated"),
        "optional": ("links", "source", "confidence", "ratified"),
        "enums": {},
        "nullable": (),
    },
    "backlog": {
        "required": ("id", "status", "title", "milestone", "updated"),
        "optional": ("links", "source", "confidence", "ratified", "after", "docs", "created"),
        "enums": {"status": {"todo", "in-progress"}},
        "nullable": ("milestone",),
    },
}


# --------------------------------------------------------------------------- #
# Parseur de frontmatter minimal maison — pas de dépendance yaml.             #
# --------------------------------------------------------------------------- #

def _parse_scalar(val: str):
    """Une valeur scalaire ou une liste inline `[a, b]`. Jamais de YAML imbriqué."""
    val = val.strip()
    if val in ("", "null", "~"):
        return None
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()] if inner else []
    return val.strip("'\"")


def parse_frontmatter(text: str):
    """Bloc `--- … ---` en tête de fichier, `clé: valeur` scalaires + listes `[a, b]`.

    Retourne `(meta, body, error)` : `meta` est `{}` et `error` non `None` si le bloc est
    absent ou jamais refermé. `body` est le texte après le bloc (chaîne vide si pas de bloc).
    Ne lève jamais.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, "bloc frontmatter absent (pas de --- en première ligne)"

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, "", "bloc frontmatter jamais refermé (pas de second ---)"

    meta = {}
    for line in lines[1:end]:
        raw = line.strip()
        if not raw or raw.startswith("#") or ":" not in raw:
            continue
        key, _, val = line.partition(":")
        meta[key.strip()] = _parse_scalar(val)

    body = "\n".join(lines[end + 1:])
    return meta, body, None


# --------------------------------------------------------------------------- #
# Validation d'une entrée — règles communes à tous les canaux.                #
# --------------------------------------------------------------------------- #

def validate_entry(path: str, meta: dict, channel: str) -> list:
    """Valide le frontmatter `meta` d'une entrée `path` contre le canal `channel`.

    Règles (identifiants stables, grep-ables — voir en-tête de fichier pour le détail) :
      R-NO-FRONTMATTER, R-MISSING-KEY, R-BAD-VALUE, R-EXT-NO-CONF, R-UNVERIFIED,
      R-VERIFIED-NOT-RATIFIED, R-BAD-DATE.
    Lève `ValueError` si `channel` n'est pas dans `CHANNELS`.
    """
    spec = CHANNELS.get(channel)
    if spec is None:
        raise ValueError(f"canal inconnu : {channel!r} (attendu : {', '.join(sorted(CHANNELS))})")

    findings = []

    if not meta:
        findings.append(Finding(BLOQUANT, "R-NO-FRONTMATTER", path, 1,
                                 "pas de frontmatter --- ... --- en tête de fichier"))
        return findings

    nullable = set(spec.get("nullable", ()))
    for key in spec["required"]:
        val = meta.get(key)
        missing = key not in meta or val == "" or (val is None and key not in nullable)
        if missing:
            findings.append(Finding(BLOQUANT, "R-MISSING-KEY", path, 1,
                                     f"clé requise « {key} » absente ou vide pour le canal « {channel} »"))

    for key, allowed in spec.get("enums", {}).items():
        val = meta.get(key)
        if val is not None and val not in allowed:
            findings.append(Finding(BLOQUANT, "R-BAD-VALUE", path, 1,
                                     f"« {key}: {val} » invalide pour le canal « {channel} » "
                                     f"(attendu : {' | '.join(sorted(allowed))})"))

    source = meta.get("source")
    if source is not None and not SOURCE_RE.match(str(source).strip()):
        findings.append(Finding(BLOQUANT, "R-BAD-VALUE", path, 1,
                                 f"« source: {source} » invalide (attendu : inferred | human | external:<réf>)"))

    confidence = meta.get("confidence")
    if confidence is not None and confidence not in CONFIDENCE_VALUES:
        findings.append(Finding(BLOQUANT, "R-BAD-VALUE", path, 1,
                                 f"« confidence: {confidence} » invalide (attendu : verified | unverified)"))

    if source and str(source).strip().startswith("external:") and not confidence:
        findings.append(Finding(BLOQUANT, "R-EXT-NO-CONF", path, 1,
                                 "source: external:... sans champ confidence"))

    if confidence == "unverified":
        findings.append(Finding(CONFIRMER, "R-UNVERIFIED", path, 1,
                                 "confidence: unverified — candidate pour l'audit sémantique (étage 2)"))

    if confidence == "verified" and not meta.get("ratified"):
        findings.append(Finding(CONFIRMER, "R-VERIFIED-NOT-RATIFIED", path, 1,
                                 "confidence: verified sans champ ratified — ratification non tracée"))

    for key in ("created", "updated"):
        val = meta.get(key)
        if val is not None and not DATE_RE.match(str(val)):
            findings.append(Finding(BLOQUANT, "R-BAD-DATE", path, 1,
                                     f"« {key}: {val} » mal formé (attendu AAAA-MM-JJ)"))

    return findings


# --------------------------------------------------------------------------- #
# Concordance fichier ↔ index — généralisation de memory-check/decisions-check#
# --------------------------------------------------------------------------- #

def check_index_concordance(index_path: str, entries_dir: str, id_pattern) -> list:
    """Tout fichier d'entrée référencé par l'index, toute référence d'index résolue.

    `id_pattern` (str ou regex compilée) extrait un identifiant comparable à la fois des noms
    de fichier de `entries_dir` (recherche sur le nom seul) et du texte de `index_path`
    (recherche sur chaque ligne). Même motif que `memory-check.py` (fichiers `memory/<slug>.md`
    ⟺ liens `MEMORY.md`) et `decisions-check.py` (fichiers `D-*.md` ⟺ ids `decisions/INDEX.md`),
    généralisé au canal fourni par l'appelant.
    """
    pat = re.compile(id_pattern) if isinstance(id_pattern, str) else id_pattern
    findings = []

    files = {}
    if os.path.isdir(entries_dir):
        for fname in sorted(os.listdir(entries_dir)):
            if not fname.endswith(".md"):
                continue
            m = pat.search(fname)
            if m:
                files[m.group(0)] = fname

    indexed = set()
    if os.path.isfile(index_path):
        with open(index_path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                for m in pat.finditer(line):
                    idv = m.group(0)
                    indexed.add(idv)
                    if idv not in files:
                        findings.append(Finding(BLOQUANT, "R-DEAD-INDEX", index_path, lineno,
                                                 f"référence « {idv} » — fichier introuvable dans {entries_dir}"))

    for idv, fname in sorted(files.items()):
        if idv not in indexed:
            findings.append(Finding(BLOQUANT, "R-ORPHAN-FILE", os.path.join(entries_dir, fname), 1,
                                     f"existe mais n'est référencé par aucune ligne de {index_path}"))

    return findings


# --------------------------------------------------------------------------- #
# Stamp — réécrit `updated` et rien d'autre.                                  #
# --------------------------------------------------------------------------- #

def stamp_updated(path: str, date_str: str) -> bool:
    """Réécrit le champ `updated` du frontmatter de `path` (et lui seul).

    Motif `--stamp` mutualisé (cf. `backlog-check.py --stamp`). Retourne `True` si le fichier
    a été modifié, `False` si `updated` était déjà à `date_str` (ou champ absent — no-op).
    """
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    new_text = re.sub(r"(?m)^updated:.*$", f"updated: {date_str}", text, count=1)
    if new_text == text:
        return False
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new_text)
    return True


DECISION_ID = re.compile(r"^D-\d{4}-\d{2}-\d{2}-\d{2}$")


def check_links(path: str, meta: dict, root: str) -> list:
    """Résout les `links:` d'une entrée — références croisées inter-canaux.

    Trois formes reconnues : un id de décision `D-AAAA-MM-JJ-NN` (→ `decisions/<id>.md` doit
    exister), un chemin (contient `/` ou une extension → le fichier/dossier doit exister depuis
    `root`), sinon un slug d'entrée (→ cherché dans `memory/`, `features/`, `backlog/<slug>/`).
    Id/chemin introuvable = `R-DEAD-LINK` (bloquant) ; slug introuvable = à-confirmer (le canal
    cible n'est peut-être pas encore peuplé).
    """
    findings = []
    links = meta.get("links") or []
    if isinstance(links, str):
        links = [links]
    for link in links:
        link = str(link).strip()
        if not link:
            continue
        if DECISION_ID.match(link):
            if not os.path.isfile(os.path.join(root, "decisions", link + ".md")):
                findings.append(Finding(BLOQUANT, "R-DEAD-LINK", path, 1,
                                        f"links: décision « {link} » sans fichier decisions/{link}.md"))
        elif "/" in link or "." in link:
            if not os.path.exists(os.path.join(root, link)):
                findings.append(Finding(BLOQUANT, "R-DEAD-LINK", path, 1,
                                        f"links: chemin « {link} » introuvable"))
        else:
            candidates = (os.path.join(root, "memory", link + ".md"),
                          os.path.join(root, "features", link + ".md"),
                          os.path.join(root, "backlog", link))
            if not any(os.path.exists(c) for c in candidates):
                findings.append(Finding(CONFIRMER, "R-DEAD-LINK", path, 1,
                                        f"links: entrée « {link} » introuvable (memory/, features/, backlog/)"))
    return findings


# --------------------------------------------------------------------------- #
# --selftest — jeu d'essais embarqué, aucun effet quand importé.              #
# --------------------------------------------------------------------------- #

def _selftest() -> int:
    import tempfile

    failures = []

    def check(cond, label):
        if not cond:
            failures.append(label)

    # parse_frontmatter — bloc valide, scalaire, liste inline, corps après le bloc
    meta, body, err = parse_frontmatter("---\nid: mem-1\nlinks: [a, b]\n---\ncorps\n")
    check(err is None, "parse_frontmatter: pas d'erreur sur bloc valide")
    check(meta.get("id") == "mem-1", "parse_frontmatter: id scalaire")
    check(meta.get("links") == ["a", "b"], "parse_frontmatter: liste inline")
    check(body.strip() == "corps", "parse_frontmatter: corps après le bloc")

    # parse_frontmatter — pas de bloc / bloc jamais refermé
    meta2, _, err2 = parse_frontmatter("pas de frontmatter\n")
    check(err2 is not None and meta2 == {}, "parse_frontmatter: erreur + meta vide si pas de bloc")
    _, _, err3 = parse_frontmatter("---\nid: x\n")
    check(err3 is not None, "parse_frontmatter: erreur si bloc jamais refermé")

    # validate_entry — R-NO-FRONTMATTER
    f = validate_entry("f.md", {}, "memory")
    check(len(f) == 1 and f[0].rule == "R-NO-FRONTMATTER", "validate_entry: R-NO-FRONTMATTER")

    # validate_entry — R-MISSING-KEY
    f = validate_entry("f.md", {"id": "x"}, "memory")
    check(any(x.rule == "R-MISSING-KEY" for x in f), "validate_entry: R-MISSING-KEY")

    # validate_entry — R-BAD-VALUE (enum status propre au canal decision)
    meta_dec = {"id": "D-2026-01-01-01", "status": "bogus", "source": "human",
                "confidence": "verified", "ratified": "raph, 2026-01-01",
                "created": "2026-01-01", "updated": "2026-01-01"}
    f = validate_entry("d.md", meta_dec, "decision")
    check(any(x.rule == "R-BAD-VALUE" for x in f), "validate_entry: R-BAD-VALUE (status)")

    # validate_entry — R-EXT-NO-CONF
    meta_ext = {"id": "mem-2", "source": "external:https://x", "created": "2026-01-01", "updated": "2026-01-01"}
    f = validate_entry("m.md", meta_ext, "memory")
    check(any(x.rule == "R-EXT-NO-CONF" for x in f), "validate_entry: R-EXT-NO-CONF")

    # validate_entry — R-UNVERIFIED
    meta_unv = {"id": "mem-3", "source": "human", "confidence": "unverified",
                "created": "2026-01-01", "updated": "2026-01-01"}
    f = validate_entry("m.md", meta_unv, "memory")
    check(any(x.rule == "R-UNVERIFIED" and x.severity == CONFIRMER for x in f),
          "validate_entry: R-UNVERIFIED")

    # validate_entry — R-VERIFIED-NOT-RATIFIED
    meta_verif = {"id": "mem-4", "source": "human", "confidence": "verified",
                  "created": "2026-01-01", "updated": "2026-01-01"}
    f = validate_entry("m.md", meta_verif, "memory")
    check(any(x.rule == "R-VERIFIED-NOT-RATIFIED" for x in f),
          "validate_entry: R-VERIFIED-NOT-RATIFIED")

    # validate_entry — R-BAD-DATE
    meta_date = {"id": "mem-5", "source": "human", "confidence": "verified",
                 "ratified": "raph, 2026-01-01", "created": "2026/01/01", "updated": "2026-01-01"}
    f = validate_entry("m.md", meta_date, "memory")
    check(any(x.rule == "R-BAD-DATE" for x in f), "validate_entry: R-BAD-DATE")

    # validate_entry — canal inconnu
    try:
        validate_entry("m.md", {"id": "x"}, "inconnu")
        check(False, "validate_entry: doit lever ValueError sur canal inconnu")
    except ValueError:
        check(True, "validate_entry: lève ValueError sur canal inconnu")

    # check_index_concordance — orphelin + lien mort, sur fixtures tempfile
    with tempfile.TemporaryDirectory() as td:
        entries_dir = os.path.join(td, "memory")
        os.makedirs(entries_dir)
        with open(os.path.join(entries_dir, "orphan-fact.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nid: orphan-fact\n---\n")
        index_path = os.path.join(td, "MEMORY.md")
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write("- [dead-fact](memory/dead-fact.md) — n'existe pas\n")
        findings = check_index_concordance(index_path, entries_dir, r"[\w.\-]+\.md")
        check(any(x.rule == "R-ORPHAN-FILE" for x in findings), "check_index_concordance: R-ORPHAN-FILE")
        check(any(x.rule == "R-DEAD-INDEX" for x in findings), "check_index_concordance: R-DEAD-INDEX")

    # stamp_updated — réécrit updated seul, no-op si déjà à jour
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "entry.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("---\nid: x\nupdated: 2020-01-01\n---\ncorps\n")
        ok = stamp_updated(p, "2026-07-09")
        check(ok, "stamp_updated: signale une modification")
        text = open(p, encoding="utf-8").read()
        check("updated: 2026-07-09" in text, "stamp_updated: date réécrite")
        check("id: x" in text, "stamp_updated: autres clés intactes")
        check(not stamp_updated(p, "2026-07-09"), "stamp_updated: no-op si déjà à jour")

    # check_links — id de décision, chemin, slug ; morts et vivants
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "decisions"))
        os.makedirs(os.path.join(td, "memory"))
        with open(os.path.join(td, "decisions", "D-2026-01-01-01.md"), "w") as fh:
            fh.write("x")
        with open(os.path.join(td, "memory", "regle-a.md"), "w") as fh:
            fh.write("x")
        meta = {"links": ["D-2026-01-01-01", "memory/regle-a.md", "regle-a"]}
        check(check_links("e.md", meta, td) == [], "check_links: liens vivants -> aucun finding")
        meta = {"links": ["D-2099-01-01-01", "memory/absente.md", "slug-inconnu"]}
        fs = check_links("e.md", meta, td)
        check(len(fs) == 3, "check_links: 3 liens morts -> 3 findings")
        check(sum(1 for f in fs if f.severity == BLOQUANT) == 2,
              "check_links: id/chemin morts bloquants")
        check(sum(1 for f in fs if f.rule == "R-DEAD-LINK") == 3, "check_links: règle R-DEAD-LINK")

    if failures:
        print(f"entrylib --selftest : {len(failures)} échec(s) :")
        for label in failures:
            print(f"  - {label}")
        return 1
    print("entrylib --selftest : OK.")
    return 0


def main(argv) -> int:
    if "--selftest" in argv:
        return _selftest()
    print("usage : python3 checks/entrylib.py --selftest   "
          "(bibliothèque partagée — importée par les checks de canal, pas un check autonome)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
