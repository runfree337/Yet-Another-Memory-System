# Backlog — le travail en cours (le *todo*)

> Le **travail ouvert**, lu en premier. Un chantier **doc-backed** (dossier `<id>/`) porte son statut dans le **frontmatter** de son `ETAT.md` — sa ligne ici = **titre + cible + gist, sans badge** ; un **item inline** (pas de doc) garde son badge `[à faire]`/`[en cours]`. Un chantier **fini est retiré** (son histoire vit dans `git log` + `decisions/`). Les chantiers sont **regroupés par jalon** (ordre = entier croissant). Protocole + clôture : `README.md`. Vue des statuts : `python3 checks/backlog-check.py --board`.

## Chantiers ouverts — par jalon

### Jalon 1 — <nom du jalon>

<!-- doc-backed : pas de badge, le statut vit dans le frontmatter de <id>/ETAT.md -->
- **<Titre du chantier>** → `<id>/` — <gist en une phrase (ce qui reste)>.

### Non planifié

<!-- items inline (pas de doc dédié) : gardent leur badge -->
- **[à faire] <petit item sans doc dédié>** — <gist en une phrase>.
