# Gabarit d'un `ETAT.md` — à copier tel quel dans `backlog/<id>/ETAT.md`

> Instance concrète de `GABARIT-ENTREE.md` pour le canal **Backlog** (voir sa table
> §Instanciation par canal). Le frontmatter est la **source de vérité de l'état** ; le corps ne
> porte **jamais de contenu durable** — seulement l'état (tâches) et des références (voir
> `README.md §L'ETAT.md ne porte jamais de contenu durable`).

## Frontmatter

<!-- gabarit -->
```
---
id: <id-du-chantier>
title: <Titre lisible du chantier>
status: todo
milestone: null
after: []
docs: []
updated: 2026-07-09
---
```
<!-- /gabarit -->

`id` = nom du dossier (kebab-case). `status` = `todo | in-progress` (jamais `done` — un chantier
fini est **retiré**, pas marqué). `milestone` = entier (jalon) ou `null` (Non planifié). `after` =
liste d'`id` de chantiers dont celui-ci dépend. `docs` = liste des `.md` compagnons du dossier
(hors `ETAT.md` lui-même). `updated` = stampé mécaniquement par `backlog-check.py --stamp`, jamais
à la main.

## Tâches

<!-- gabarit -->
- [done] Cadrer l'intention du chantier et écrire la spec initiale.
- [in-progress] Découper le moteur de résolution en briques testables → plan-resolution.md
- [todo] Écrire les tests d'intégration une fois le découpage stabilisé.
<!-- /gabarit -->

Une ligne = une tâche. `<!-- gabarit -->` ci-dessus n'exempte que les **chemins d'exemple** de ce
gabarit — pas un format à recopier dans les commentaires du vrai `ETAT.md`. Deux formes :
- `- [<état>] <libellé ≤ 30 mots>` — la tâche tient dans son libellé.
- `- [<état>] <libellé court> → <doc-de-travail.md>` — le détail vit dans le doc de travail
  (dans le dossier du chantier), le libellé reste court.

États : `todo | in-progress | blocked | done`.

## Reste

<!-- gabarit -->
Tant qu'un chantier n'est pas encore découpé en tâches, décrire ici en prose libre ce qui reste à
faire. Cette rubrique se **vide** au profit de `## Tâches` au fur et à mesure du découpage — elle
n'est pas un journal permanent, juste le sas avant découpage.
<!-- /gabarit -->
