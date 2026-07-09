#!/usr/bin/env python3
"""Contrôle déterministe du backlog (zéro faux positif), agnostique.

Vérifie mécaniquement les invariants de `backlog/README.md` — NE corrige rien, **signale**.
Premier étage du motif deux-niveaux (script → revue sémantique). Format : un chantier doc-backed
= un **sous-dossier** `backlog/<id>/` dont l'`ETAT.md` ouvre par un **frontmatter** aux clés
anglaises (`id/title/status/milestone/after/docs/updated`) — instance de `GABARIT-ENTREE.md`
(canal « backlog »), généralisé via `entrylib.py` comme `feature-map-check.py`. La ligne
d'`INDEX.md` d'un doc-backed ne porte que titre + cible + gist (sans badge) ; un item inline
(pas de doc) garde son badge `[todo]`/`[in-progress]`. Deux paliers : inline / sous-dossier.

Suit `checks/GABARIT.md` : `Finding` namedtuple à 5 champs, deux verdicts, règles pures.

Règles :
  (R-*)          (voir entrylib) `entrylib.validate_entry(path, meta, "backlog")` par ETAT.md —
                                  `R-NO-FRONTMATTER`, `R-MISSING-KEY`, `R-BAD-VALUE`,
                                  `R-EXT-NO-CONF`, `R-UNVERIFIED`, `R-VERIFIED-NOT-RATIFIED`,
                                  `R-BAD-DATE` ; `entrylib.check_links` pour les `links:` —
                                  `R-DEAD-LINK`.
  E-ID           (BLOQUANT)      frontmatter `id` ≠ nom du dossier.
  E-ID-KEBAB     (BLOQUANT)      frontmatter `id` pas en kebab-case.
  E-ID-DUP       (BLOQUANT)      `id` déjà utilisé par un autre chantier.
  E-MILESTONE    (BLOQUANT)      `milestone` du frontmatter ≠ groupe `### Jalon N` de l'INDEX.
  E-AFTER        (BLOQUANT)      `after:` pointe un id de chantier qui n'existe pas.
  E-DOCS         (BLOQUANT)      `docs:` ≠ exactement les `.md` compagnons du dossier.
  E-TASK-SECTION (BLOQUANT)      rubrique `## Tâches` absente de l'ETAT.md.
  E-TASK-STATE   (BLOQUANT)      état de tâche hors `todo|in-progress|blocked|done`.
  E-TASK-LEN     (BLOQUANT)      libellé de tâche > 30 mots SANS document de travail référencé
                                  (comptage simple : le badge `[état]` et le `→ doc.md` exclus).
  E-TASK-REF     (BLOQUANT)      document de travail cité (`→ doc.md`) introuvable dans le
                                  dossier du chantier.
  E-TASK-SYNC    (À-CONFIRMER)   incohérence chantier⟺tâches : toutes `done` mais chantier
                                  `todo`/`in-progress` (signal « prêt à clore ») — ou l'inverse,
                                  chantier `in-progress` sans aucune tâche entamée.
  E-STATE-SIZE   (À-CONFIRMER)   ETAT.md > 80 lignes — candidat « du durable vit dans l'état »
                                  (garde anti-accumulation, soft — jamais bloquant).
  E-STATE-SECTION(À-CONFIRMER)   titre `## …` hors rubriques canoniques (`Tâches`/`Reste`) —
                                  soft, jamais bloquant.
  I-FLAT         (BLOQUANT)      fichier `.md` plat au premier niveau de `backlog/` (hors
                                  `INDEX.md`/`README.md`/`ETAT.gabarit.md`) — palier abandonné.
  I-ORPHAN       (BLOQUANT)      dossier `backlog/<id>/` cité nulle part dans `INDEX.md`.
  I-DEAD-POINTER (BLOQUANT)      pointeur `` `<id>/` `` ou `` `<fichier>.md` `` de `INDEX.md`
                                  qui ne résout vers rien.
  I-CHECKBOX     (BLOQUANT)      case Markdown `- [ ]`/`- [x]` dans `INDEX.md` (fini = retiré ;
                                  statut = frontmatter pour les doc-backed, badge pour les autres).

Vues : `--board` (chantiers par jalon, statut + compteurs de tâches par état) · `--state <id>`
(un chantier, tâches déroulées). Les deux acceptent `--json`. `--checklist [<id>]` émet le
gabarit de clôture (DoD, `backlog/README.md`).

`--stamp [fichiers…]` / `--stamp --staged` : pose `updated: <aujourd'hui>` via
`entrylib.stamp_updated` sur les `ETAT.md` cités (ou stagés avec `--staged`, scope strict
`backlog/**/ETAT.md`, re-stage git après écriture) — même triple garde-fou que
`feature-map-check.py --stamp` : scope stagé strict, un seul champ mécanique, jamais bloquant.

Usage :
  python3 checks/backlog-check.py                     # rapport texte
  python3 checks/backlog-check.py --json               # sortie JSON des findings
  python3 checks/backlog-check.py --board               # vue d'ensemble
  python3 checks/backlog-check.py --state <id>           # un chantier déroulé
  python3 checks/backlog-check.py --stamp --staged        # pré-commit uniquement
  python3 checks/backlog-check.py --checklist [<id>]        # gabarit de clôture (DoD)
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
BACKLOG = os.path.join(ROOT, "backlog")
INDEX_PATH = os.path.join(BACKLOG, "INDEX.md")

# Noms structurels au premier niveau du backlog — jamais des pointeurs de chantier.
STRUCTURAL = {"ETAT.md", "INDEX.md", "README.md", "ETAT.gabarit.md"}

KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

TASK_STATES = {"todo", "in-progress", "blocked", "done"}
TASK_LABEL_MAX_WORDS = 30
STATE_SIZE_MAX_LINES = 80
CANON_SECTIONS = {"Tâches", "Reste"}

# DoD (cf. backlog/README.md). `{cible}` = le chantier à supprimer. Étape 1 = un CONTRÔLE
# (la capitalisation s'est déjà faite tâche par tâche), pas un gros œuvre.
CLOSURE_STEPS = [
    ("Durable", "contrôler qu'il ne reste pas de durable non migré (l'ETAT.md n'en porte "
                "jamais) — sinon le migrer maintenant vers son foyer + les mémoires touchées"),
    ("Décision", "enregistrer la décision si la clôture acte un choix structurel"),
    ("Backlog", "supprimer {cible} **+ sa ligne dans `INDEX.md`**"),
    ("État", "mettre à jour `TABLEAU_DE_BORD.md` : avancement du jalon concerné, points chauds"),
    ("Capitalisation", "poser la question « apprentissage de méthode réutilisable ? » et router si oui"),
]


def closure_checklist(cible="le dossier du chantier"):
    head = "Checklist de clôture (DoD — `backlog/README.md`) :"
    rows = [f"  [ ] {i}. **{t}** — {d.format(cible=cible)}"
            for i, (t, d) in enumerate(CLOSURE_STEPS, 1)]
    return "\n".join([head, *rows])


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT)


# --------------------------------------------------------------------------- #
# Parsing du corps de l'ETAT.md — titres H2 + tâches de la rubrique `Tâches`  #
# --------------------------------------------------------------------------- #

H2 = re.compile(r"^##\s+(.+?)\s*$")
TOP_BULLET = re.compile(r"^-\s+(.*)$")           # bullet top-level (pas de retrait)
TASK_BADGE = re.compile(r"^\[(?P<state>[^\]]*)\]\s*(?P<rest>.*)$")
DOC_REF = re.compile(r"→\s*(\S+)\s*$")


def parse_etat(text):
    """Retourne (headings: [(lineno, titre)], sections: {titre: [(lineno, contenu_du_bullet)]})."""
    headings, sections, current = [], {}, None
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = H2.match(line)
        if m:
            current = m.group(1).strip()
            headings.append((lineno, current))
            sections.setdefault(current, [])
            continue
        if current is not None:
            bm = TOP_BULLET.match(line)
            if bm:
                sections[current].append((lineno, bm.group(1)))
    return headings, sections


def parse_task(content):
    """Une ligne de tâche (déjà sans le `- ` de tête) → (etat, libellé, doc_ref|None)."""
    m = TASK_BADGE.match(content)
    state = m.group("state").strip() if m else ""
    rest = m.group("rest").strip() if m else content.strip()
    dm = DOC_REF.search(rest)
    if dm:
        doc = dm.group(1).strip("`")
        label = rest[:dm.start()].strip()
    else:
        doc = None
        label = rest.strip()
    return state, label, doc


# --------------------------------------------------------------------------- #
# Parsing de l'INDEX.md — jalon par chantier (titres de groupe restent en FR) #
# --------------------------------------------------------------------------- #

H3_JALON = re.compile(r"^###\s+Jalon\s+(\d+)")
H3_ANY = re.compile(r"^###\s+")
H2_ANY = re.compile(r"^##\s+")
ENTRY_TOK = re.compile(r"→\s*`([\w.\-]+)/`")  # entrée canonique « → `<id>/` »


def index_jalon_map(index_text):
    """Groupe courant = dernier `### Jalon N` vu ; tout autre titre (`### Non planifié`, ou un
    `##` de plus haut niveau) le réinitialise à `None` — sinon un chantier sous « Non planifié »
    hériterait à tort du dernier jalon numéroté rencontré plus haut dans le fichier."""
    mapping, current = {}, None
    for line in index_text.splitlines():
        mj = H3_JALON.match(line)
        if mj:
            current = int(mj.group(1))
            continue
        if H3_ANY.match(line) or H2_ANY.match(line):
            current = None
            continue
        if line.lstrip().startswith("- "):
            m = ENTRY_TOK.search(line)
            if m:
                mapping.setdefault(m.group(1).rstrip("/"), current)
    return mapping


def _norm_milestone(v):
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    return int(s) if re.fullmatch(r"-?\d+", s) else s


# --------------------------------------------------------------------------- #
# Un chantier — frontmatter (entrylib) + tâches + garde-fous                  #
# --------------------------------------------------------------------------- #

def collect_chantiers():
    if not os.path.isdir(BACKLOG):
        return []
    return [(n, os.path.join(BACKLOG, n)) for n in sorted(os.listdir(BACKLOG))
            if os.path.isdir(os.path.join(BACKLOG, n)) and not n.startswith(".")]


def check_chantier(cid, cdir, ids, jalon_map, seen_ids) -> list[Finding]:
    findings: list[Finding] = []
    etat = os.path.join(cdir, "ETAT.md")
    etat_rel = rel(etat)
    if not os.path.isfile(etat):
        findings.append(Finding(BLOQUANT, "E-ETAT-MISSING", rel(cdir), 1,
                                 "sous-dossier chantier sans ETAT.md."))
        return findings

    with open(etat, encoding="utf-8") as f:
        text = f.read()

    meta, body, err = entrylib.parse_frontmatter(text)
    findings += entrylib.validate_entry(etat_rel, meta, "backlog")
    findings += entrylib.check_links(etat_rel, meta, ROOT)

    headings, sections = parse_etat(text)

    # E-ID / E-ID-KEBAB / E-ID-DUP
    fid = meta.get("id")
    if fid != cid:
        findings.append(Finding(BLOQUANT, "E-ID", etat_rel, 1,
                                 f"frontmatter `id: {fid}` ≠ nom du dossier « {cid} »."))
    if isinstance(fid, str) and not KEBAB.match(fid):
        findings.append(Finding(BLOQUANT, "E-ID-KEBAB", etat_rel, 1,
                                 f"frontmatter `id: {fid}` n'est pas en kebab-case."))
    if fid is not None:
        if fid in seen_ids:
            findings.append(Finding(BLOQUANT, "E-ID-DUP", etat_rel, 1,
                                     f"id « {fid} » déjà utilisé par « {seen_ids[fid]} »."))
        else:
            seen_ids[fid] = cid

    # E-MILESTONE
    milestone = _norm_milestone(meta.get("milestone"))
    if cid in jalon_map and milestone != jalon_map[cid]:
        attendu = jalon_map[cid]
        a = "null (Non planifié)" if attendu is None else str(attendu)
        m = "null" if milestone is None else str(milestone)
        findings.append(Finding(BLOQUANT, "E-MILESTONE", etat_rel, 1,
                                 f"frontmatter `milestone: {m}` mais l'INDEX range ce chantier "
                                 f"sous « {a} »."))

    # E-AFTER
    for dep in (meta.get("after") or []):
        if dep not in ids:
            findings.append(Finding(BLOQUANT, "E-AFTER", etat_rel, 1,
                                     f"frontmatter `after` pointe « {dep} » — aucun chantier de ce nom."))

    # E-DOCS
    declared = set(meta.get("docs") or [])
    actual = {fn for fn in os.listdir(cdir) if fn.endswith(".md") and fn != "ETAT.md"}
    if declared != actual:
        det = []
        if actual - declared:
            det.append("non déclarés : " + ", ".join(sorted(actual - declared)))
        if declared - actual:
            det.append("inexistants : " + ", ".join(sorted(declared - actual)))
        findings.append(Finding(BLOQUANT, "E-DOCS", etat_rel, 1,
                                 "frontmatter `docs:` ≠ compagnons du dossier (" + " ; ".join(det) + ")."))

    # E-STATE-SECTION (soft) — tout titre hors Tâches/Reste
    for lineno, h in headings:
        if h not in CANON_SECTIONS:
            findings.append(Finding(CONFIRMER, "E-STATE-SECTION", f"{etat_rel}:{lineno}",
                                     lineno, f"titre « ## {h} » hors rubriques canoniques "
                                     "(Tâches/Reste) — candidat « du durable vit dans l'état »."))

    # E-STATE-SIZE (soft)
    nb_lines = len(text.splitlines())
    if nb_lines > STATE_SIZE_MAX_LINES:
        findings.append(Finding(CONFIRMER, "E-STATE-SIZE", etat_rel, 1,
                                 f"{nb_lines} lignes (> {STATE_SIZE_MAX_LINES}) — candidat "
                                 "« du durable vit dans l'état », à vider vers son foyer durable."))

    # E-TASK-SECTION + tâches
    if "Tâches" not in sections:
        findings.append(Finding(BLOQUANT, "E-TASK-SECTION", etat_rel, 1,
                                 "rubrique `## Tâches` absente (obligatoire, `backlog/README.md`)."))
    else:
        counts = {s: 0 for s in TASK_STATES}
        total = 0
        for lineno, raw in sections["Tâches"]:
            state, label, doc = parse_task(raw)
            total += 1
            if state not in TASK_STATES:
                findings.append(Finding(BLOQUANT, "E-TASK-STATE", f"{etat_rel}:{lineno}", lineno,
                                         f"état de tâche « {state or '(absent)'} » hors "
                                         "todo|in-progress|blocked|done."))
            else:
                counts[state] += 1
            if doc is None and len(label.split()) > TASK_LABEL_MAX_WORDS:
                findings.append(Finding(BLOQUANT, "E-TASK-LEN", f"{etat_rel}:{lineno}", lineno,
                                         f"libellé de {len(label.split())} mots (> {TASK_LABEL_MAX_WORDS}) "
                                         "sans document de travail référencé (`→ doc.md`)."))
            if doc is not None and not os.path.isfile(os.path.join(cdir, doc)):
                findings.append(Finding(BLOQUANT, "E-TASK-REF", f"{etat_rel}:{lineno}", lineno,
                                         f"document de travail « {doc} » introuvable dans "
                                         f"{rel(cdir)}/."))

        status = meta.get("status")
        started = any(counts[s] for s in ("in-progress", "blocked", "done"))
        all_done = total > 0 and counts["done"] == total
        if all_done and status in ("todo", "in-progress"):
            findings.append(Finding(CONFIRMER, "E-TASK-SYNC", etat_rel, 1,
                                     f"toutes les tâches sont `done` mais chantier `status: {status}` "
                                     "— prêt à clore ?"))
        if status == "in-progress" and not started:
            findings.append(Finding(CONFIRMER, "E-TASK-SYNC", etat_rel, 1,
                                     "chantier `status: in-progress` sans aucune tâche entamée."))

    return findings


# --------------------------------------------------------------------------- #
# INDEX.md — orphelins, pointeurs morts, cases Markdown                      #
# --------------------------------------------------------------------------- #

def check_index(chantiers, index_text) -> list[Finding]:
    findings: list[Finding] = []
    ids = {cid for cid, _ in chantiers}

    for name in sorted(os.listdir(BACKLOG)) if os.path.isdir(BACKLOG) else []:
        if name in STRUCTURAL or name.startswith("."):
            continue
        full = os.path.join(BACKLOG, name)
        if os.path.isfile(full) and name.endswith(".md"):
            findings.append(Finding(BLOQUANT, "I-FLAT", rel(full), 1,
                                     "fichier plat au premier niveau du backlog — un chantier = "
                                     "un sous-dossier `<id>/` avec ETAT.md (palier abandonné)."))

    for cid, cdir in chantiers:
        if (cid + "/") not in index_text and cid not in index_text:
            findings.append(Finding(BLOQUANT, "I-ORPHAN", rel(cdir), 1,
                                     f"« {cid}/ » n'est cité nulle part dans INDEX.md."))

    basenames, reldirs = set(), set()
    for _dp, dirs, files in os.walk(BACKLOG):
        basenames.update(files)
        reldirs.update(dirs)
    for lineno, line in enumerate(index_text.splitlines(), start=1):
        for tok in re.findall(r"`([^`]+)`", line):
            tok = tok.strip()
            if "<" in tok or ">" in tok or tok in STRUCTURAL:
                continue
            if re.fullmatch(r"[\w.\-]+\.md", tok) and tok not in basenames:
                findings.append(Finding(BLOQUANT, "I-DEAD-POINTER", f"{rel(INDEX_PATH)}:{lineno}",
                                         lineno, f"pointeur « {tok} » ne résout vers aucun fichier "
                                         "du backlog."))
            elif re.fullmatch(r"[\w.\-]+/", tok):
                name_ = tok.rstrip("/")
                if name_ not in reldirs and name_ not in ids:
                    findings.append(Finding(BLOQUANT, "I-DEAD-POINTER", f"{rel(INDEX_PATH)}:{lineno}",
                                             lineno, f"pointeur « {tok} » ne résout vers aucun "
                                             "dossier existant."))
        if re.match(r"^\s*[-*]\s*\[[ xX]\]", line):
            findings.append(Finding(BLOQUANT, "I-CHECKBOX", f"{rel(INDEX_PATH)}:{lineno}", lineno,
                                     "case Markdown dans l'INDEX — retirer `[ ]`/`[x]` (fini = "
                                     "retiré ; statut = frontmatter ou badge inline)."))
    return findings


# --------------------------------------------------------------------------- #
# --stamp — pose `updated` seul, jamais bloquant                              #
# --------------------------------------------------------------------------- #

def cmd_stamp(argv: list[str]) -> int:
    """Pose `updated: aujourd'hui` sur les ETAT.md cités (ou stagés avec `--staged`) + re-stage.
    Même triple garde-fou que `feature-map-check.py --stamp` : scope stagé strict
    (`backlog/**/ETAT.md` uniquement), un seul champ mécanique (`entrylib.stamp_updated` ne
    touche que `updated`), jamais bloquant (code retour toujours 0)."""
    today = datetime.date.today().isoformat()
    staged = "--staged" in argv
    if staged:
        r = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                            cwd=ROOT, capture_output=True, text=True)
        files = [f for f in r.stdout.splitlines()
                 if f.replace("\\", "/").startswith("backlog/") and f.endswith("ETAT.md")]
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
    print(f"backlog-check : --stamp — {len(changed)} ETAT.md daté(s) à {today}.")
    return 0


# --------------------------------------------------------------------------- #
# Vues --board / --state                                                      #
# --------------------------------------------------------------------------- #

TASK_STATE_DISPLAY_ORDER = ["done", "in-progress", "blocked", "todo"]


def chantier_ids():
    return [cid for cid, _ in collect_chantiers()]


def chantier_state(cid):
    cdir = os.path.join(BACKLOG, cid)
    etat = os.path.join(cdir, "ETAT.md")
    if not os.path.isdir(cdir) or not os.path.isfile(etat):
        return None
    with open(etat, encoding="utf-8") as f:
        text = f.read()
    meta, _body, _err = entrylib.parse_frontmatter(text)
    _headings, sections = parse_etat(text)
    counts = {s: 0 for s in TASK_STATES}
    tasks = []
    for lineno, raw in sections.get("Tâches", []):
        state, label, doc = parse_task(raw)
        if state in TASK_STATES:
            counts[state] += 1
        tasks.append({"line": lineno, "state": state, "label": label, "doc": doc})
    return {
        "id": meta.get("id", cid), "title": meta.get("title"), "status": meta.get("status"),
        "milestone": _norm_milestone(meta.get("milestone")), "updated": meta.get("updated"),
        "docs": meta.get("docs") or [], "tasks": tasks, "task_counts": counts,
        "reste": [content for _, content in sections.get("Reste", [])],
    }


def _task_counts_suffix(counts):
    parts = [f"{counts[s]} {s}" for s in TASK_STATE_DISPLAY_ORDER if counts.get(s)]
    return " / ".join(parts)


def render_state(cid):
    st = chantier_state(cid)
    if st is None:
        dispo = ", ".join(chantier_ids()) or "(aucun)"
        return f"[backlog-check] chantier « {cid} » introuvable (backlog/{cid}/ETAT.md).\nChantiers : {dispo}"
    jalon = "Non planifié" if st["milestone"] is None else f"Jalon {st['milestone']}"
    lines = [f"Chantier {st['id']} — {st['title']}",
             f"  status : {st['status']}   ·   {jalon}   ·   updated {st['updated']}"]
    suffix = _task_counts_suffix(st["task_counts"])
    lines.append("  tâches : " + (suffix if suffix else "—"))
    if st["docs"]:
        lines.append("  docs   : " + ", ".join(st["docs"]))
    lines.append(f"\n## Tâches ({len(st['tasks'])})")
    for t in st["tasks"]:
        tail = f" → {t['doc']}" if t["doc"] else ""
        lines.append(f"  - [{t['state']}] {t['label']}{tail}")
    if st["reste"]:
        lines.append(f"\n## Reste ({len(st['reste'])})")
        lines.extend("  " + it for it in st["reste"])
    return "\n".join(lines)


def render_board():
    rows = [chantier_state(cid) or {"id": cid} for cid in chantier_ids()]
    if not rows:
        return "[backlog-check] aucun chantier doc-backed."
    rows.sort(key=lambda s: (s.get("milestone") is None,
                              s.get("milestone") if s.get("milestone") is not None else 0, s.get("id")))
    icon = {"todo": "○", "in-progress": "◐"}
    lines, cur = ["Backlog — chantiers par jalon (statuts live) :"], object()
    for s in rows:
        milestone = s.get("milestone")
        grp = "Non planifié" if milestone is None else f"Jalon {milestone}"
        if grp != cur:
            cur = grp
            lines.append(f"\n### {grp}")
        status = s.get("status") or "?"
        line = f"  {icon.get(status, '·')} [{status}] {s.get('id')} — {s.get('title') or s.get('id')}"
        suffix = _task_counts_suffix(s.get("task_counts") or {})
        if suffix:
            line += f"   ({suffix})"
        lines.append(line)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Rendu / CLI                                                                  #
# --------------------------------------------------------------------------- #

def run() -> list[Finding]:
    chantiers = collect_chantiers()
    index_text = ""
    if os.path.isfile(INDEX_PATH):
        with open(INDEX_PATH, encoding="utf-8") as f:
            index_text = f.read()
    ids = {cid for cid, _ in chantiers}
    jalon_map = index_jalon_map(index_text)
    seen_ids: dict = {}

    findings: list[Finding] = []
    for cid, cdir in chantiers:
        findings += check_chantier(cid, cdir, ids, jalon_map, seen_ids)
    findings += check_index(chantiers, index_text)
    return findings


def render_text(findings: list[Finding]) -> str:
    if not findings:
        return "backlog-check : OK."
    bloq = [f for f in findings if f.severity == BLOQUANT]
    conf = [f for f in findings if f.severity == CONFIRMER]
    lines = [f"{f.severity:14} {f.path}:{f.line}  {f.rule}  {f.msg}"
             for f in sorted(findings, key=lambda f: (f.severity != BLOQUANT, f.path, f.line))]
    lines.append(f"\n— {len(findings)} finding(s) : {len(bloq)} bloquant-auto, {len(conf)} à-confirmer")
    return "\n".join(lines)


def main(argv):
    if "--stamp" in argv:
        return cmd_stamp(argv)
    if "--checklist" in argv:
        rest = [a for a in argv[argv.index("--checklist") + 1:] if not a.startswith("-")]
        cible = ("`backlog/" + rest[0].strip("/") + "/`") if rest else "le dossier du chantier"
        print(closure_checklist(cible))
        return 0
    if "--state" in argv:
        rest = [a for a in argv[argv.index("--state") + 1:] if not a.startswith("-")]
        if not rest:
            print("usage : --state <id>   (chantiers : " + ", ".join(chantier_ids()) + ")")
            return 1
        cid = rest[0].strip("/")
        st = chantier_state(cid)
        print(json.dumps(st, ensure_ascii=False, indent=2) if "--json" in argv else render_state(cid))
        return 0 if st else 1
    if "--board" in argv:
        if "--json" in argv:
            print(json.dumps([chantier_state(c) for c in chantier_ids()], ensure_ascii=False, indent=2))
        else:
            print(render_board())
        return 0

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
