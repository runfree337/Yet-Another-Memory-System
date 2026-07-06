# Backlog — protocole + clôture (DoD)

`backlog/` = **maison unique du travail ouvert** (le *todo* : conception, tâches en cours, restes). Distinct du **durable** (la doc du projet + les trois mémoires) et du *pourquoi* (`decisions/`).

## La chaîne

`spec` (conception d'un chantier) → **`backlog`** (décidé, pas encore bâti) → *en cours : découpé en tâches* → à la livraison, le contenu **migre vers le durable** et le chantier **quitte** le backlog.

## Structure

**Deux paliers** :
- Petit item → une ligne **inline** dans `INDEX.md` (statut porté par un badge sur la ligne).
- Chantier **doc-backed** → un dossier `backlog/<id>/` dont l'`ETAT.md` ouvre par un **frontmatter** (`id/titre/statut/jalon/apres/docs/maj`, **source de vérité de l'état**) + un suivi **par tâche** ; ses docs compagnons (spec, manifeste) dans le même dossier.
- Statut : `à faire` / `en cours` (dans le frontmatter pour un doc-backed, le badge pour un inline). Fini → **retiré** (pas de statut « fini » qui s'accumule). La ligne d'`INDEX.md` d'un doc-backed ne porte que titre + cible + gist (le statut vit dans le frontmatter).
- **Ouvrir** un chantier doc-backed = `mkdir <id>/` + `ETAT.md` depuis le gabarit (frontmatter + rubriques, tout le concret en `Reste`) + sa ligne d'`INDEX.md` (sans badge).
- `maj` (si présent au frontmatter) : **auto-tamponné au pré-commit** — un hook (`backlog-check.py --stamp --staged`, câblé au **pré-commit** : hook git `pre-commit` ou l'équivalent de ton outil) pose `maj = date du commit` sur les ETAT.md indexés, **mécaniquement** (pas de bump manuel, pas de pourrissement). L'état **par tâche** vit dans les rubriques, jamais dupliqué dans le frontmatter ni dans l'INDEX.

## Jalons — regroupement ordonné

L'`INDEX.md` **regroupe** les chantiers par **jalon** : un sous-titre `### Jalon N — <nom>` (N entier = l'ordre), les chantiers non rattachés sous `### Non planifié`. Le jalon **ordonne**, il ne partitionne pas (toujours un seul `INDEX.md` — le « backlog d'un jalon » est la *vue* = son groupe). Le frontmatter `jalon:` (entier, ou `null` = Non planifié) en porte la **copie machine**, réconciliée par le check. Reclasser un chantier = déplacer sa ligne d'un groupe à l'autre **et** mettre à jour `jalon:` dans son frontmatter.

## Definition of Done — clôturer un chantier (dans l'ordre)

1. **Durable écrit** — la doc qui décrit *ce qui existe* (côté projet) + les mémoires touchées (`FEATURE_MAP`…). Le durable *porte le contenu*, pas une promesse.
2. **Décision** enregistrée si la clôture acte un choix structurel.
3. **Backlog vidé** — le chantier + sa ligne d'`INDEX.md` sont **retirés** (ou statut mis à jour si partiel).
4. **Capitalisation** — poser la question « apprentissage de méthode réutilisable ? » et la router si oui.

> Tant que ces étapes ne sont pas faites, le chantier **n'est pas clos**. L'étape de validation se branche sur le rituel du projet (sa skill de review, etc.) — le process n'en impose aucun.
