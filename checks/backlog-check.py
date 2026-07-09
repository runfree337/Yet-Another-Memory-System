#!/usr/bin/env python3
"""Contrôle déterministe du backlog (zéro faux positif) — version agnostique.

Vérifie mécaniquement les invariants de `backlog/README.md` — NE corrige rien,
**signale**. Premier étage du motif deux-niveaux (script → revue sémantique).
À câbler pour tourner automatiquement (hook de fin de tâche / session, ou CI ;
voir `checks/README.md`).

Modèle : un chantier doc-backed = un **sous-dossier** `backlog/<id>/` dont l'`ETAT.md`
ouvre par un **frontmatter YAML** (`id/titre/statut/jalon/apres/docs/maj`) — **source de
vérité de l'état**. La ligne d'`INDEX.md` ne porte que titre + cible + gist (sans badge) ;
un item inline (pas de doc) garde son badge. Deux paliers : inline / sous-dossier.

Vérifs (déterministes, zéro-FP visé) :
  F1  Tout sous-dossier `backlog/<id>/` a un `ETAT.md` avec un frontmatter portant les
      champs requis (`id/titre/statut/jalon/maj`), `statut` ∈ {à faire, en cours}, `maj` en YYYY-MM-DD.
  F2  `id` du frontmatter = nom du dossier, kebab-case, unique entre chantiers.
  F3  `statut` concorde avec les rubriques (à faire ⟺ tout est dans Reste, sinon en cours).
  F4  `jalon` concorde avec le groupe `### Jalon N` de l'INDEX (null ⟺ hors Jalon).
  F5  Chaque `apres:` pointe un `id` de chantier existant.
  F6  `docs:` = exactement les `.md` compagnons du dossier (hors `ETAT.md`).
  Fr  Tout titre `## …` de l'`ETAT.md` ∈ rubriques canoniques ∪ préambule (Intention/Gain) ∪ Clôture.
  E4  Pas d'orphelin : tout dossier de `backlog/` est cité dans `INDEX.md`, tout pointeur résout,
      et aucun fichier plat de chantier au premier niveau (palier abandonné).
  E6  `INDEX.md` ne porte pas de case Markdown `- [ ]`/`- [x]`.
  C3  (info) Item d'ETAT « en surpoids » (> 6 sous-puces, ou ligne physique > 400 chars) →
      extraire le détail en doc compagnon (`docs:`), l'ETAT ne garde qu'une ligne de renvoi (README §4).
  I1  (info) Signal de clôture : `ETAT.md` tout en *Documenté* → chantier prêt à clôturer.

Vues : `--board` (chantiers par jalon, statut + comptes par rubrique) · `--state <id>`
(un chantier, rubriques déroulées). Les deux acceptent `--json`. `--checklist [<id>]`
émet le gabarit de clôture (DoD).

Code retour : 2 si ≥1 erreur (F*/E*), 0 sinon (I* neutre).
Usage : python3 checks/backlog-check.py [--json|--board|--state <id>|--checklist [<id>]]
"""
from __future__ import annotations

import json
import os
import re
import sys

ERREUR = "ERREUR"
INFO = "INFO"

RUBRIQUES = {"Documenté", "Fini", "À valider", "En cours", "Reste"}
RUBRIQUE_ORDER = ["Documenté", "Fini", "À valider", "En cours", "Reste"]
RUBRIQUES_NON_TERMINALES = {"Fini", "À valider", "En cours", "Reste"}
STATUTS = {"à faire", "en cours"}
REQUIS = ("id", "titre", "statut", "jalon", "maj")
STRUCTURAL = {"ETAT.md", "INDEX.md", "README.md"}  # noms structurels, pas des pointeurs de chantier

KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKLOG = os.path.join(ROOT, "backlog")

# DoD agnostique de clôture (cf. backlog/README.md). `{cible}` = le chantier à supprimer.
CLOSURE_STEPS = [
    ("Durable", "écrire/mettre à jour la doc durable (ce qui existe) + les mémoires touchées "
                "— porte le contenu, pas une promesse"),
    ("Décision", "enregistrer la décision si la clôture acte un choix structurel"),
    ("Backlog", "supprimer {cible} **+ sa ligne dans `INDEX.md`**"),
    ("Capitalisation", "poser la question « apprentissage de méthode réutilisable ? » et router si oui"),
]


def closure_checklist(cible="le dossier du chantier"):
    head = "Checklist de clôture (DoD — `backlog/README.md`) :"
    rows = [f"  [ ] {i}. **{t}** — {d.format(cible=cible)}"
            for i, (t, d) in enumerate(CLOSURE_STEPS, 1)]
    return "\n".join([head, *rows])


def add(out, severity, rule, path, msg):
    out.append({"severity": severity, "rule": rule, "path": path, "msg": msg})


# --------------------------------------------------------------------------- #
# Parsing — frontmatter + corps de l'ETAT.md
# --------------------------------------------------------------------------- #

H2 = re.compile(r"^##\s+(.+?)\s*$")
COMMENT = re.compile(r"\s+#.*$")


def parse_scalar(val):
    val = val.strip()
    if val in ("", "null", "~"):
        return None
    if val == "[]":
        return []
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()] if inner else []
    if re.fullmatch(r"-?\d+", val):
        return int(val)
    return val.strip("'\"")


def parse_frontmatter(text):
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None
    fm = {}
    for line in lines[1:end]:
        raw = COMMENT.sub("", line).rstrip()
        if not raw.strip() or ":" not in raw:
            continue
        key, _, val = raw.partition(":")
        fm[key.strip()] = parse_scalar(val)
    return fm


def parse_etat_body(text):
    headings, sections, current = [], {}, None
    for line in text.splitlines():
        m = H2.match(line)
        if m:
            current = m.group(1).strip()
            headings.append(current)
            sections[current] = []
            continue
        if current is not None:
            s = line.strip()
            if s.startswith("- ") and s.strip("- ").strip() not in ("", "—", "-"):
                sections[current].append(s)
    return headings, sections


def is_allowed_heading(h):
    return h in RUBRIQUES or h.startswith(("Intention", "Gain", "Clôture", "Cloture"))


def derived_statut(sections):
    started = any(sections.get(r) for r in ("Documenté", "Fini", "À valider", "En cours"))
    return "en cours" if started else "à faire"


# --------------------------------------------------------------------------- #
# Parsing de l'INDEX.md — jalon par chantier
# --------------------------------------------------------------------------- #

H3_JALON = re.compile(r"^###\s+Jalon\s+(\d+)")
H2_ANY = re.compile(r"^##\s+")
ENTRY_TOK = re.compile(r"→\s*`([\w.\-]+)/`")  # entrée canonique « → `<id>/` »


def index_jalon_map(index_text):
    mapping, current = {}, None
    for line in index_text.splitlines():
        mj = H3_JALON.match(line)
        if mj:
            current = int(mj.group(1))
            continue
        if H2_ANY.match(line):
            current = None
            continue
        if line.lstrip().startswith("- "):
            m = ENTRY_TOK.search(line)
            if m:
                mapping.setdefault(m.group(1).rstrip("/"), current)
    return mapping


# --------------------------------------------------------------------------- #
# Règles
# --------------------------------------------------------------------------- #

def collect_chantiers(backlog):
    if not os.path.isdir(backlog):
        return []
    return [(n, os.path.join(backlog, n)) for n in sorted(os.listdir(backlog))
            if os.path.isdir(os.path.join(backlog, n)) and not n.startswith(".")]


# Seuils C3 (« item d'ETAT en surpoids ») — advisory. Voir backlog/README.md §4.
C3_SUBS_MAX = 6    # > 6 sous-puces sous un même item = journal imbriqué à externaliser
C3_LINE_MAX = 400  # ligne physique de rubrique > 400 chars = pavé à externaliser


def check_etat_overweight(text, etat_rel, out):
    """C3 (info, advisory) — un item de rubrique « en surpoids » (trop de sous-puces, ou
    une ligne physique trop longue) devrait migrer son détail dans un **doc compagnon**
    (déclaré dans `docs:`), l'ETAT ne gardant qu'une **ligne de renvoi** (intent + statut +
    référence). Réalise la discipline du README §4 (ETAT = statut par tâche + renvois, PAS un
    journal). Ne s'applique qu'aux rubriques canoniques (pas au préambule Intention/Gain)."""
    in_rubric = False
    parent = None  # (lineno, libellé) du bullet top-level courant
    subs = 0
    lineno = 0

    def flush():
        nonlocal parent, subs
        if parent is not None and subs > C3_SUBS_MAX:
            ln, label = parent
            add(out, INFO, "C3-item-surpoids", f"{etat_rel}:{ln}",
                f"item « {label} » porte {subs} sous-puces (> {C3_SUBS_MAX}) — extraire le "
                f"détail en doc compagnon (`docs:`), ne laisser qu'une ligne de renvoi.")
        parent, subs = None, 0

    for line in text.splitlines():
        lineno += 1
        m = H2.match(line)
        if m:
            flush()
            in_rubric = m.group(1).strip() in RUBRIQUES
            continue
        if not in_rubric:
            continue
        if len(line) > C3_LINE_MAX:
            add(out, INFO, "C3-ligne-longue", f"{etat_rel}:{lineno}",
                f"ligne de {len(line)} chars (> {C3_LINE_MAX}) — pavé à externaliser en doc "
                f"compagnon, ne laisser qu'une ligne de renvoi dans l'ETAT.")
        bm = re.match(r"( *)[-*] (.*)", line)
        if bm:
            if len(bm.group(1)) == 0:      # bullet top-level
                flush()
                parent = (lineno, bm.group(2)[:40])
                subs = 0
            elif parent is not None:        # sous-puce (indentée)
                subs += 1
    flush()


def check_backlog(out):
    if not os.path.isdir(BACKLOG):
        return
    index_path = os.path.join(BACKLOG, "INDEX.md")
    index_text = ""
    if os.path.isfile(index_path):
        with open(index_path, encoding="utf-8") as f:
            index_text = f.read()

    chantiers = collect_chantiers(BACKLOG)
    ids = {cid for cid, _ in chantiers}
    jalon_map = index_jalon_map(index_text)
    seen_ids = {}

    for name in sorted(os.listdir(BACKLOG)):
        if name in ("INDEX.md", "README.md") or name.startswith("."):
            continue
        full = os.path.join(BACKLOG, name)
        if os.path.isfile(full) and name.endswith(".md"):
            add(out, ERREUR, "E4-fichier-plat", os.path.relpath(full, ROOT),
                "fichier plat au premier niveau du backlog — un chantier = un sous-dossier `<id>/` "
                "avec ETAT.md (palier fichier plat abandonné).")

    for cid, cdir in chantiers:
        rel_dir = os.path.relpath(cdir, ROOT)
        if (cid + "/") not in index_text and cid not in index_text:
            add(out, ERREUR, "E4-orphelin", rel_dir,
                f"« {cid}/ » n'est cité nulle part dans INDEX.md (chantier sans entrée d'index).")

        etat = os.path.join(cdir, "ETAT.md")
        if not os.path.isfile(etat):
            add(out, ERREUR, "F1-etat-manquant", rel_dir, "sous-dossier chantier sans ETAT.md.")
            continue
        with open(etat, encoding="utf-8") as f:
            etat_text = f.read()
        etat_rel = os.path.relpath(etat, ROOT)
        fm = parse_frontmatter(etat_text)
        headings, sections = parse_etat_body(etat_text)

        # C3 — item de rubrique « en surpoids » → externaliser en doc compagnon (advisory).
        check_etat_overweight(etat_text, etat_rel, out)

        for h in headings:
            if not is_allowed_heading(h):
                add(out, ERREUR, "Fr-rubrique", etat_rel,
                    f"titre « ## {h} » hors rubriques canoniques "
                    "(Documenté/Fini/À valider/En cours/Reste, préambule Intention/Gain, ou Clôture).")

        if fm is None:
            add(out, ERREUR, "F1-frontmatter", etat_rel,
                "ETAT.md sans frontmatter YAML en tête (`--- … ---`).")
            continue
        for champ in REQUIS:
            if champ not in fm or (fm[champ] is None and champ != "jalon"):
                add(out, ERREUR, "F1-champ", etat_rel,
                    f"frontmatter : champ requis « {champ} » absent ou vide.")
        statut = fm.get("statut")
        if statut is not None and statut not in STATUTS:
            add(out, ERREUR, "F1-statut", etat_rel,
                f"frontmatter `statut: {statut}` invalide (attendu : à faire | en cours).")
        maj = fm.get("maj")
        if isinstance(maj, str) and not DATE.match(maj):
            add(out, ERREUR, "F1-maj", etat_rel, f"frontmatter `maj: {maj}` mal formé (YYYY-MM-DD).")

        fid = fm.get("id")
        if fid != cid:
            add(out, ERREUR, "F2-id", etat_rel,
                f"frontmatter `id: {fid}` ≠ nom du dossier « {cid} ».")
        if isinstance(fid, str) and not KEBAB.match(fid):
            add(out, ERREUR, "F2-kebab", etat_rel, f"frontmatter `id: {fid}` n'est pas en kebab-case.")
        if fid in seen_ids:
            add(out, ERREUR, "F2-doublon", etat_rel,
                f"id « {fid} » déjà utilisé par « {seen_ids[fid]} ».")
        elif fid is not None:
            seen_ids[fid] = cid

        derived = derived_statut(sections)
        if statut in STATUTS and statut != derived:
            add(out, ERREUR, "F3-statut-incoherent", etat_rel,
                f"frontmatter `statut: {statut}` mais le contenu est « {derived} ».")

        jalon = fm.get("jalon")
        if cid in jalon_map and jalon != jalon_map[cid]:
            attendu = jalon_map[cid]
            a = "null (Non planifié)" if attendu is None else str(attendu)
            j = "null" if jalon is None else str(jalon)
            add(out, ERREUR, "F4-jalon-incoherent", etat_rel,
                f"frontmatter `jalon: {j}` mais l'INDEX range ce chantier sous « {a} ».")

        for dep in (fm.get("apres") or []):
            if dep not in ids:
                add(out, ERREUR, "F5-apres", etat_rel,
                    f"frontmatter `apres` pointe « {dep} » — aucun chantier de ce nom.")

        declared = set(fm.get("docs") or [])
        actual = {fn for fn in os.listdir(cdir) if fn.endswith(".md") and fn != "ETAT.md"}
        if declared != actual:
            det = []
            if actual - declared:
                det.append("non déclarés : " + ", ".join(sorted(actual - declared)))
            if declared - actual:
                det.append("inexistants : " + ", ".join(sorted(declared - actual)))
            add(out, ERREUR, "F6-docs", etat_rel,
                "frontmatter `docs:` ≠ compagnons du dossier (" + " ; ".join(det) + ").")

        if sections.get("Documenté") and not any(
            sections.get(r) for r in RUBRIQUES_NON_TERMINALES
        ):
            add(out, INFO, "I1-cloture", etat_rel,
                "tout est en « Documenté » → chantier prêt à clôturer (dérouler la DoD).")

    # E4 — pointeurs d'INDEX.md (gabarits `<...>` ignorés).
    basenames, reldirs = set(), set()
    for dp, dirs, files in os.walk(BACKLOG):
        basenames.update(files)
        reldirs.update(dirs)
    for tok in re.findall(r"`([^`]+)`", index_text):
        tok = tok.strip()
        if "<" in tok or ">" in tok or tok in STRUCTURAL:
            continue
        if re.fullmatch(r"[\w.\-]+\.md", tok) and tok not in basenames:
            add(out, ERREUR, "E4-pointeur", "backlog/INDEX.md",
                f"pointeur « {tok} » ne résout vers aucun fichier du backlog.")
        elif re.fullmatch(r"[\w.\-]+/", tok):
            name_ = tok.rstrip("/")
            if name_ not in reldirs and not os.path.isdir(os.path.join(ROOT, name_)):
                add(out, ERREUR, "E4-pointeur", "backlog/INDEX.md",
                    f"pointeur « {tok} » ne résout vers aucun dossier existant.")


def check_index_checkboxes(out):
    index_path = os.path.join(BACKLOG, "INDEX.md")
    if not os.path.isfile(index_path):
        return
    with open(index_path, encoding="utf-8") as f:
        for i, line in enumerate(f.read().splitlines(), 1):
            if re.match(r"^\s*[-*]\s*\[[ xX]\]", line):
                add(out, ERREUR, "E6-checkbox", f"backlog/INDEX.md:{i}",
                    "case Markdown dans l'INDEX — retirer `[ ]`/`[x]` (fini = retiré ; statut = "
                    "frontmatter pour les doc-backed, badge inline pour les autres).")


# --------------------------------------------------------------------------- #
# Vues --board / --state
# --------------------------------------------------------------------------- #

def chantier_ids():
    return [cid for cid, _ in collect_chantiers(BACKLOG)]


def chantier_state(cid):
    cdir = os.path.join(BACKLOG, cid)
    etat = os.path.join(cdir, "ETAT.md")
    if not os.path.isdir(cdir) or not os.path.isfile(etat):
        return None
    with open(etat, encoding="utf-8") as f:
        text = f.read()
    fm = parse_frontmatter(text) or {}
    _, sections = parse_etat_body(text)
    rubriques = {r: sections.get(r, []) for r in RUBRIQUE_ORDER}
    return {
        "id": fm.get("id", cid), "titre": fm.get("titre"), "statut": fm.get("statut"),
        "jalon": fm.get("jalon"), "maj": fm.get("maj"), "docs": fm.get("docs") or [],
        "rubriques": rubriques, "compte": {r: len(v) for r, v in rubriques.items()},
        "statut_derive": derived_statut(sections),
    }


def _counts_suffix(compte):
    return " · ".join(f"{r} {compte.get(r, 0)}" for r in RUBRIQUE_ORDER if compte.get(r, 0))


def render_state(cid):
    st = chantier_state(cid)
    if st is None:
        dispo = ", ".join(chantier_ids()) or "(aucun)"
        return f"[backlog-check] chantier « {cid} » introuvable (backlog/{cid}/ETAT.md).\nChantiers : {dispo}"
    jalon = "Non planifié" if st["jalon"] is None else f"Jalon {st['jalon']}"
    lines = [f"Chantier {st['id']} — {st['titre']}",
             f"  statut : {st['statut']}   ·   {jalon}   ·   maj {st['maj']}"]
    if st["statut"] not in (None, st["statut_derive"]):
        lines.append(f"  ⚠ incohérent : rubriques → « {st['statut_derive']} »")
    if st["docs"]:
        lines.append("  docs   : " + ", ".join(st["docs"]))
    suffix = _counts_suffix(st["compte"])
    lines.append("  compte : " + (suffix if suffix else "—"))
    for r in RUBRIQUE_ORDER:
        items = st["rubriques"][r]
        lines.append(f"\n## {r} ({len(items)})")
        lines.extend("  " + it for it in items)
    return "\n".join(lines)


def render_board():
    rows = [chantier_state(cid) or {"id": cid} for cid in chantier_ids()]
    if not rows:
        return "[backlog-check] aucun chantier doc-backed."
    rows.sort(key=lambda s: (s.get("jalon") is None,
                             s.get("jalon") if s.get("jalon") is not None else 0, s.get("id")))
    icon = {"à faire": "○", "en cours": "◐"}
    lines, cur = ["Backlog — chantiers par jalon (statuts live) :"], object()
    for s in rows:
        jalon = s.get("jalon")
        grp = "Non planifié" if jalon is None else f"Jalon {jalon}"
        if grp != cur:
            cur = grp
            lines.append(f"\n### {grp}")
        statut = s.get("statut") or "?"
        line = f"  {icon.get(statut, '·')} [{statut}] {s.get('id')} — {s.get('titre') or s.get('id')}"
        suffix = _counts_suffix(s.get("compte") or {})
        if suffix:
            line += f"   ({suffix})"
        lines.append(line)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Rendu / CLI
# --------------------------------------------------------------------------- #

def run():
    out = []
    check_backlog(out)
    check_index_checkboxes(out)
    return out


def render_text(out):
    if not out:
        return "backlog-check : OK."
    order = {ERREUR: 0, INFO: 1}
    out = sorted(out, key=lambda f: (order[f["severity"]], f["rule"], f["path"]))
    lines, cur = [], None
    for f in out:
        if f["severity"] != cur:
            cur = f["severity"]
            lines.append(f"\n{cur} :")
        lines.append(f"  [{f['rule']}] {f['path']} — {f['msg']}")
        if f["rule"] == "I1-cloture":
            cible = "`" + os.path.dirname(f["path"]) + "/`"
            for row in closure_checklist(cible).splitlines():
                lines.append("    " + row.lstrip())
    return "\n".join(lines).lstrip("\n")


def cmd_stamp(argv):
    """Pose `maj = aujourd'hui` sur les ETAT.md cités (ou indexés avec --staged) + re-stage.
    À câbler au PRÉ-COMMIT (hook git pre-commit, ou l'équivalent de ton outil) → la date du
    frontmatter = la date du commit, mécaniquement (zéro pourrissement). Scope stagé uniquement :
    ne tire jamais un fichier non indexé dans le commit."""
    import datetime
    import subprocess
    today = datetime.date.today().isoformat()
    staged = "--staged" in argv
    if staged:
        r = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                           capture_output=True, text=True)
        files = [f for f in r.stdout.splitlines()
                 if ("/backlog/" in f.replace("\\", "/") or f.replace("\\", "/").startswith("backlog/"))
                 and f.endswith("ETAT.md")]
    else:
        files = [a for a in argv[argv.index("--stamp") + 1:] if not a.startswith("-")]
    changed = []
    for f in files:
        if not os.path.isfile(f):
            continue
        with open(f, encoding="utf-8") as fh:
            text = fh.read()
        new = re.sub(r"(?m)^maj:.*$", "maj: " + today, text, count=1)
        if new != text:
            with open(f, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new)
            changed.append(f)
            if staged:
                subprocess.run(["git", "add", f])
    print(f"backlog-check : --stamp — {len(changed)} ETAT.md daté(s) à {today}.")
    return 0


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
    out = run()
    if "--json" in argv:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(render_text(out))
    return 2 if any(f["severity"] == ERREUR for f in out) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
