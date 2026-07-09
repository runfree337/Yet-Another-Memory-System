# Backlog — protocole + clôture (DoD)

`backlog/` = **maison unique du travail ouvert** (le *todo* : conception, tâches en cours, restes). Distinct du **durable** (la doc du projet + les trois mémoires) et du *pourquoi* (`decisions/`). **Transitoire**, pas une mémoire — mais chaque `ETAT.md` suit le **même format d'entrée** que les canaux mémoire : c'est une instance du gabarit commun `GABARIT-ENTREE.md` (canal **Backlog**, table §Instanciation par canal).

## La chaîne

`spec` (conception d'un chantier) → **`backlog`** (décidé, pas encore bâti) → *en cours : découpé en tâches* → à la livraison, le contenu **migre vers le durable** et le chantier **quitte** le backlog.

## Structure

**Deux paliers** :
- Petit item → une ligne **inline** dans `INDEX.md` (statut porté par un badge sur la ligne, `[todo]` / `[in-progress]`).
- Chantier **doc-backed** → un dossier `backlog/<id>/` dont l'`ETAT.md` ouvre par un **frontmatter** aux clés **anglaises** (`id / title / status / milestone / after / docs / updated`, **source de vérité de l'état**), suivi d'une rubrique `## Tâches` **obligatoire** (voir ci-dessous) ; ses docs compagnons (spec, manifeste, docs de travail des tâches) vivent dans le même dossier.
- Sémantique des clés (inchangée, seul le vocabulaire change) : `after` = dépendance (ex-`apres`) ; `docs` = docs compagnons du dossier ; `updated` = date de dernière frappe (ex-`maj`), **stampée mécaniquement** au pré-commit ; `milestone` = jalon (ex-`jalon`), entier ou `null` (Non planifié).
- `status: todo | in-progress` (dans le frontmatter pour un doc-backed, le badge pour un inline). Fini → **retiré** (pas de statut « fini » qui s'accumule — un chantier ne passe jamais `status: done`, il quitte le backlog). La ligne d'`INDEX.md` d'un doc-backed ne porte que titre + cible + gist (le statut vit dans le frontmatter).
- **Ouvrir** un chantier doc-backed = `mkdir <id>/` + `ETAT.md` depuis `ETAT.gabarit.md` (frontmatter + `## Tâches` + `## Reste`) + sa ligne d'`INDEX.md` (sans badge).
- `updated` : **auto-tamponné au pré-commit** — un hook (`backlog-check.py --stamp --staged`, câblé au **pré-commit** : hook git `pre-commit` ou l'équivalent de ton outil) pose `updated = date du commit` sur les ETAT.md indexés, **mécaniquement** (pas de bump manuel, pas de pourrissement — via `entrylib.stamp_updated`).

## Rubrique `## Tâches` — le format canonique de ligne

Chaque `ETAT.md` porte une rubrique `## Tâches` **obligatoire** : le suivi par tâche vit **là**, jamais dupliqué dans le frontmatter ni dans l'`INDEX.md`. Une ligne, une tâche, deux formes :

```
- [<état>] <libellé ≤ 30 mots>
- [<état>] <libellé court> → <doc-de-travail.md>
```

- **États** (sous-état de la tâche, distinct du `status` du chantier) : `todo | in-progress | blocked | done`.
- **Une tâche simple tient dans le libellé** (≤ 30 mots). Au-delà, elle **doit** référencer un **document de travail** — un fichier **dans le dossier du chantier**, cité après `→` — et le libellé redevient court (le détail vit dans le doc, pas dans la ligne).
- **Cohérence chantier ⟺ tâches** (signal, pas un verdict ferme — l'étage 2 tranche) :
  - chantier `in-progress` ⟹ au moins une tâche entamée (état ≠ `todo`) ;
  - toutes les tâches `done` ⟹ chantier prêt à clore (dérouler la DoD ci-dessous).
- Une rubrique `## Reste` (facultative) porte, en prose libre, ce qui n'est **pas encore** découpé en tâches — elle se vide au profit de `## Tâches` au fur et à mesure du découpage. Aucune autre rubrique n'est canonique : `## Tâches` et `## Reste` sont les deux seules attendues dans un `ETAT.md` (au-delà du frontmatter).

## L'ETAT.md ne porte jamais de contenu durable

La capitalisation du durable (doc d'architecture, fiche `FEATURE_MAP`, décision…) se fait **en fin de chaque tâche qui en produit**, pas en fin de chantier — c'est là qu'elle est la plus fraîche. Conséquence directe : **l'`ETAT.md` ne porte jamais de contenu durable**, seulement l'**état** (frontmatter + tâches) et des **références** — vers les docs de travail du chantier, et vers le durable déjà écrit ailleurs. Une tâche finie qui a produit de la doc → cette doc part **immédiatement** dans son foyer durable (jamais laissée « en attente » dans l'ETAT.md), la tâche passe `[done]` avec, si utile, une référence vers ce foyer. Un `ETAT.md` qui gonfle (contenu > état + références) est le signal que cette règle a été contournée — voir `checks/backlog-check.py §E-STATE-SIZE / §E-STATE-SECTION` (soft, à-confirmer).

## Jalons — regroupement ordonné

L'`INDEX.md` **regroupe** les chantiers par **jalon** : un sous-titre `### Jalon N — <nom>` (N entier = l'ordre — ce titre de groupe reste en **français**, c'est le visage humain du plan), les chantiers non rattachés sous `### Non planifié`. Le jalon **ordonne**, il ne partitionne pas (toujours un seul `INDEX.md` — le « backlog d'un jalon » est la *vue* = son groupe). Le frontmatter `milestone:` (entier, ou `null` = Non planifié) en porte la **copie machine**, réconciliée par le check. Reclasser un chantier = déplacer sa ligne d'un groupe à l'autre **et** mettre à jour `milestone:` dans son frontmatter.

## Definition of Done — clôturer un chantier (dans l'ordre)

1. **Contrôle du durable** — puisque la capitalisation s'est déjà faite tâche par tâche (voir ci-dessus), cette étape n'est plus un gros œuvre mais une **vérification** : reste-t-il du contenu durable non migré (dans l'`ETAT.md`, un doc de travail oublié…) ? Si oui, le migrer maintenant vers son foyer durable + les mémoires touchées (`FEATURE_MAP`…) — le durable *porte le contenu*, pas une promesse.
2. **Décision** enregistrée si la clôture acte un choix structurel.
3. **Backlog vidé** — le chantier + sa ligne d'`INDEX.md` sont **retirés** (ou statut mis à jour si partiel).
4. **État mis à jour** — `TABLEAU_DE_BORD.md` : avancement du jalon concerné, points chauds (résolus retirés / nouveaux ajoutés), ligne de date.
5. **Capitalisation** — poser la question « apprentissage de méthode réutilisable ? » et la router si oui.

> Tant que ces étapes ne sont pas faites, le chantier **n'est pas clos**. L'étape de validation se branche sur le rituel du projet (sa skill de review, etc.) — le process n'en impose aucun.
