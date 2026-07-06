# `_meta/` — référence hors-projet

Dossier **méta** : documents de référence qui ne concernent **pas** le contenu du jeu *Souvenir d'outre-mort*. Conservés dans le dépôt par commodité, mais **explicitement hors du périmètre projet** :

- **Hors index** — sous aucune racine de `manifest.py` (`Assets/Project/`, `Docs/`, `Tools/`). `manifest.py check` ne le voit pas.
- **Hors linter doc** — `doc-audit.py --all` scanne `Docs/` + `.claude/skills/` + `CLAUDE.md` + `projectIndex.md`, pas `_meta/`.
- **Hors Unity** — en dehors d'`Assets/`, jamais importé par l'éditeur.

Ne rien mettre ici qui doive être suivi par l'outillage du projet (doc d'architecture, décision, donnée). Pour ça : `Docs/` et son cycle de vie.

## Contenu

- `ai-workflow/` — **framework de process IA**, agnostique à l'outil (Claude Code / Copilot / autre) et à la techno/archi, dérivé de la méthode de travail de ce projet. À déposer sur un autre dépôt pour qu'une IA y travaille. Cœur : `ai-workflow/WORKFLOW.md`. Sans rapport avec le contenu de ce jeu.
