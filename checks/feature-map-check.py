#!/usr/bin/env python3
"""Contrôle d'intégrité du canal « Feature » (`FEATURE_MAP.md` + `features/`), agnostique.

Format : un fichier par fiche (`features/<slug>.md`, frontmatter du canal `feature`) +
`FEATURE_MAP.md` = index (une ligne par fiche) — même motif que `memory-check.py` /
`decisions-check.py`, généralisé via `entrylib.py` (`GABARIT-ENTREE.md`, canal « feature »).
NE corrige rien — signale.

Suit `checks/GABARIT.md` : `Finding` namedtuple à 5 champs, deux verdicts, règles pures.

Règles :
  FM-INDEX       (BLOQUANT)      concordance `features/*.md` <-> `FEATURE_MAP.md`, via
                                  `entrylib.check_index_concordance` — surface
                                  `R-ORPHAN-FILE` (fiche sans ligne d'index) et
                                  `R-DEAD-INDEX` (ligne d'index sans fiche).
  (R-*)          (voir entrylib) `entrylib.validate_entry(path, meta, "feature")` par fiche —
                                  `R-NO-FRONTMATTER`, `R-MISSING-KEY`, `R-BAD-VALUE`,
                                  `R-EXT-NO-CONF`, `R-UNVERIFIED`, `R-VERIFIED-NOT-RATIFIED`,
                                  `R-BAD-DATE` ; `entrylib.check_links` pour les `links:` —
                                  `R-DEAD-LINK`.
  FM1-role       (BLOQUANT)      pas de ligne `**Rôle :**` dans le corps.
  FM1-code       (BLOQUANT)      aucun chemin de fichier (code) cité dans le corps.
  FM1-durable    (BLOQUANT)      aucune réf durable : ni clé `**Doc (durable) :**` non vide,
                                  ni id `D-AAAA-MM-JJ-NN` (corps ou `links:`).
  FM-DECISION    (BLOQUANT)      un id `D-*` cité dans le CORPS n'a pas de fichier
                                  `decisions/D-*.md` (le volet `links:` est couvert par
                                  `entrylib.check_links` -> `R-DEAD-LINK`).
  FM-TRANSIENT   (BLOQUANT)      référence transitoire (`backlog/…`) dans une fiche —
                                  durable uniquement, le planifié vit au backlog (ex-FM5).
  FM-FRESH       (À-CONFIRMER)   `updated` de la fiche antérieur au dernier commit git touchant
                                  un des chemins cités par `**Code :**` — fiche possiblement
                                  périmée. Soft : chemin non versionné/inexistant → ignoré
                                  (déjà couvert par d'autres règles, pas de double signal).
  FM-GRAN        (À-CONFIRMER)   corps > ~60 lignes utiles → candidat « deux sujets ».

⚠️ **Pattern à adapter au projet** : `TRANSIENT` (où vit le backlog du projet hôte) dépend du
layout — le défaut ci-dessous couvre CE dépôt (`backlog/`).

`--stamp [fichiers…]` / `--stamp --staged` : pose `updated: <aujourd'hui>` via
`entrylib.stamp_updated` sur les fiches passées en argument (ou stagées avec `--staged`, scope
strict `features/*.md`, re-stage git après écriture) — même triple garde-fou que
`backlog-check.py --stamp` : scope stagé strict, un seul champ mécanique, jamais bloquant.

Usage :
  python3 checks/feature-map-check.py                    # rapport texte
  python3 checks/feature-map-check.py --json              # sortie JSON des findings
  python3 checks/feature-map-check.py --stamp features/x.md
  python3 checks/feature-map-check.py --stamp --staged    # pré-commit
Code retour : 0 propre, 1 seulement des À-CONFIRMER, 2 au moins un BLOQUANT.
"""
from __future__ import annotations

import datetime
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # …/ai-workflow
FMAP = os.path.join(ROOT, "FEATURE_MAP.md")
FEATURES_DIR = os.path.join(ROOT, "features")

ROLE_KEY = re.compile(r"^\*\*\s*Rôle\b", re.IGNORECASE)
DOC_KEY = re.compile(r"^\*\*\s*Doc\b", re.IGNORECASE)
DOC_KEY_VALUE = re.compile(r"^\*\*\s*Doc[^:*]*:?\*{0,2}\s*", re.IGNORECASE)
CODE_PATH = re.compile(r"(?:[\w.\-]+/)+[\w.\-]+\.[A-Za-z0-9]{1,6}")
DECISION_MENTION = re.compile(r"\bD-\d{4}-\d{2}-\d{2}-\d{2}\b")
TRANSIENT = re.compile(r"\bbacklog/")
GRAN_SEUIL = 60


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT)


def list_fiches() -> list[str]:
    if not os.path.isdir(FEATURES_DIR):
        return []
    return sorted(f for f in os.listdir(FEATURES_DIR) if f.endswith(".md"))


# --------------------------------------------------------------------------- #
# FM-INDEX — concordance features/*.md <-> FEATURE_MAP.md                    #
# --------------------------------------------------------------------------- #

INDEX_HEADING = "## Fiches"


def _index_section_tempfile() -> str | None:
    """Isole la section `## Fiches` (l'index réel) dans un fichier temporaire — les lignes
    précédentes sont remplacées par des lignes vides pour préserver la numérotation (les
    findings restent `path:line`-adressables sur l'original). Nécessaire car le reste du
    document (`§Le format`, `§Exemple complet`…) cite légitimement d'autres `.md`
    (`GABARIT-ENTREE.md`, l'exemple `null-check-unity.md`…) sans rapport avec l'index — un
    scan pleine-page produirait des `R-DEAD-INDEX` en faux positif sur ces mentions."""
    if not os.path.isfile(FMAP):
        return None
    with open(FMAP, encoding="utf-8") as fh:
        lines = fh.readlines()
    start = next((i for i, l in enumerate(lines) if l.strip() == INDEX_HEADING), len(lines))
    padded = ["\n"] * start + lines[start:]
    import tempfile
    fd, tmp_path = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.writelines(padded)
    return tmp_path


def check_index() -> list[Finding]:
    tmp = _index_section_tempfile()
    if tmp is None:
        return []
    try:
        findings = entrylib.check_index_concordance(tmp, FEATURES_DIR, r"[\w.\-]+\.md")
    finally:
        os.unlink(tmp)
    fmap_rel = rel(FMAP)
    return [Finding(f.severity, f.rule,
                     fmap_rel if f.path == tmp else rel(f.path),
                     f.line, f.msg.replace(tmp, fmap_rel))
            for f in findings]


# --------------------------------------------------------------------------- #
# Fraîcheur — FM-FRESH (soft)                                                 #
# --------------------------------------------------------------------------- #

def _git_last_commit_date(relpath: str) -> str | None:
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", relpath],
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    out = r.stdout.strip()
    return out or None


def check_freshness(fiche_path: str, meta: dict, body: str) -> list[Finding]:
    """FM-FRESH — `updated` plus ancien que le dernier commit d'un chemin de `**Code :**`.

    Tolérant : chemin inexistant (dead-path, déjà `doc-refs-check.py`) ou non versionné (git
    log vide) → ignoré, pas de double signal.
    """
    updated = meta.get("updated")
    if not updated or not entrylib.DATE_RE.match(str(updated)):
        return []
    findings: list[Finding] = []
    seen = set()
    for m in CODE_PATH.finditer(body):
        p = m.group(0)
        if p in seen:
            continue
        seen.add(p)
        if not os.path.exists(os.path.join(ROOT, p)):
            continue
        commit_date = _git_last_commit_date(p)
        if commit_date and commit_date > str(updated):
            findings.append(Finding(CONFIRMER, "FM-FRESH", rel(fiche_path), 1,
                f"« {p} » modifié le {commit_date}, fiche « updated: {updated} » "
                "— fiche possiblement périmée."))
    return findings


# --------------------------------------------------------------------------- #
# Une fiche — frontmatter (entrylib) + clés-cœur du corps + garde-fous        #
# --------------------------------------------------------------------------- #

def check_fiche(fname: str) -> list[Finding]:
    path = os.path.join(FEATURES_DIR, fname)
    findings: list[Finding] = []
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    meta, body, err = entrylib.parse_frontmatter(text)
    if err:
        findings.append(Finding(BLOQUANT, "R-NO-FRONTMATTER", rel(path), 1, err))
        return findings  # pas de corps exploitable sans frontmatter fermé

    findings += entrylib.validate_entry(rel(path), meta, "feature")
    findings += entrylib.check_links(rel(path), meta, ROOT)

    body_lines = body.splitlines()

    if not any(ROLE_KEY.match(l.strip()) for l in body_lines):
        findings.append(Finding(BLOQUANT, "FM1-role", rel(path), 1,
                                 "pas de clé-cœur `**Rôle :**`."))

    if not CODE_PATH.search(body):
        findings.append(Finding(BLOQUANT, "FM1-code", rel(path), 1,
                                 "aucun chemin de fichier (code) cité."))

    doc_nonempty = any(
        DOC_KEY.match(l.strip()) and DOC_KEY_VALUE.sub("", l.strip()).strip()
        for l in body_lines
    )
    links_meta = meta.get("links") or []
    if isinstance(links_meta, str):
        links_meta = [links_meta]
    has_decision_link = any(entrylib.DECISION_ID.match(str(x).strip()) for x in links_meta)
    has_decision_mention = bool(DECISION_MENTION.search(body))
    if not (doc_nonempty or has_decision_link or has_decision_mention):
        findings.append(Finding(BLOQUANT, "FM1-durable", rel(path), 1,
                                 "aucune réf durable (clé `**Doc**` non vide, ou id `D-*`)."))

    for m in TRANSIENT.finditer(body):
        findings.append(Finding(BLOQUANT, "FM-TRANSIENT", rel(path), 1,
                                 f"référence transitoire « {m.group(0)}… » — durable uniquement, "
                                 "le planifié vit au backlog."))

    for d in sorted(set(DECISION_MENTION.findall(body))):
        if not os.path.isfile(os.path.join(ROOT, "decisions", d + ".md")):
            findings.append(Finding(BLOQUANT, "FM-DECISION", rel(path), 1,
                                     f"id « {d} » cité dans le corps mais decisions/{d}.md introuvable."))

    useful = [l for l in body_lines if l.strip() and not l.strip().startswith("|---")]
    if len(useful) > GRAN_SEUIL:
        findings.append(Finding(CONFIRMER, "FM-GRAN", rel(path), 1,
                                 f"{len(useful)} lignes utiles (> {GRAN_SEUIL}) → envisager un "
                                 "découpage (deux sujets ?)."))

    findings += check_freshness(path, meta, body)
    return findings


# --------------------------------------------------------------------------- #
# --stamp — pose `updated` seul, jamais bloquant                              #
# --------------------------------------------------------------------------- #

def cmd_stamp(argv: list[str]) -> int:
    """Pose `updated: aujourd'hui` sur les fiches citées (ou stagées avec `--staged`) + re-stage.
    Motif mutualisé avec `backlog-check.py --stamp` : scope stagé strict (`features/*.md`
    uniquement), un seul champ mécanique (`entrylib.stamp_updated` ne touche que `updated`),
    jamais bloquant (code retour toujours 0)."""
    today = datetime.date.today().isoformat()
    staged = "--staged" in argv
    if staged:
        r = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                            cwd=ROOT, capture_output=True, text=True)
        files = [f for f in r.stdout.splitlines()
                 if f.replace("\\", "/").startswith("features/") and f.endswith(".md")]
    else:
        files = [a for a in argv[argv.index("--stamp") + 1:] if not a.startswith("-")]

    changed = []
    for f in files:
        full = f if os.path.isabs(f) else os.path.join(ROOT, f)
        if not os.path.isfile(full):
            continue
        if entrylib.stamp_updated(full, today):
            changed.append(f)
            if staged:
                subprocess.run(["git", "add", f], cwd=ROOT)
    print(f"feature-map-check : --stamp — {len(changed)} fiche(s) datée(s) à {today}.")
    return 0


# --------------------------------------------------------------------------- #
# Rendu / CLI                                                                  #
# --------------------------------------------------------------------------- #

def run() -> list[Finding]:
    findings = list(check_index())
    for fname in list_fiches():
        findings += check_fiche(fname)
    return findings


def render_text(findings: list[Finding]) -> str:
    if not findings:
        return "feature-map-check : OK."
    bloq = [f for f in findings if f.severity == BLOQUANT]
    conf = [f for f in findings if f.severity == CONFIRMER]
    lines = [f"{f.severity:14} {f.path}:{f.line}  {f.rule}  {f.msg}"
             for f in sorted(findings, key=lambda f: (f.severity != BLOQUANT, f.path, f.line))]
    lines.append(f"\n— {len(findings)} finding(s) : {len(bloq)} bloquant-auto, {len(conf)} à-confirmer")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if "--stamp" in argv:
        return cmd_stamp(argv)

    findings = run()
    if "--json" in argv:
        print(json.dumps([f._asdict() for f in findings], ensure_ascii=False, indent=2))
    else:
        print(render_text(findings))

    if any(f.severity == BLOQUANT for f in findings):
        return 2
    if any(f.severity == CONFIRMER for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
