# Backlog — le travail en cours (le *todo*)

> Le **travail ouvert**, lu en premier. Un chantier **doc-backed** (dossier `<id>/`) porte son statut dans le **frontmatter** de son `STATE.md` (clés anglaises id/title/status/milestone/after/docs/updated — instance du gabarit commun d'entrée mémoire, canal Backlog) ; sa ligne ici = **titre + cible + gist, sans badge** ; un **item inline** (pas de doc) garde son badge `[todo]`/`[in-progress]` (vocabulaire machine — gabarit concret d'un `STATE.md` : `STATE.template.md`). Un chantier **fini est retiré** (son histoire vit dans `git log` et le journal de décisions). Les chantiers sont **regroupés par jalon** (ordre = entier croissant, titres de groupe en français — le visage humain du plan). Protocole + clôture : `README.md`. Vue des statuts : `python3 checks/backlog-check.py --board`.

## Chantiers ouverts — par jalon

### Jalon 1 — <nom du jalon>

<!-- doc-backed : pas de badge, le statut vit dans le frontmatter de <id>/STATE.md -->
- **<Titre du chantier>** → `<id>/` — <gist en une phrase (ce qui reste)>.

### Non planifié

<!-- items inline (pas de doc dédié) : gardent leur badge -->
- **[todo] <petit item sans doc dédié>** — <gist en une phrase>.
