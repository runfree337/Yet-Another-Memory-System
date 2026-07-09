# Carte des features — mémoire « feature »

> Routeur **« feature → comprendre le sujet : ce qu'elle fait, le code à voir, la doc d'archi »**.
> Quand une tâche touche une feature listée ici, **lire sa fiche avant de chercher**. Mettre la
> fiche à jour **au même moment que le code** — une fiche qui ment est pire qu'absente.
> **Référence DURABLE uniquement** : doc d'archi/spec + code + décisions. **Jamais** un doc
> transitoire (backlog, spec/plan en cours) — le « planifié » vit au backlog. Une fiche dit ce
> qui *existe*.
> Une fiche ≈ « un seul sujet qu'on comprend d'un coup ». Trop longue → probablement deux
> features (test **sémantique**, pas un simple compte de lignes ; `checks/feature-map-check.py`
> donne un signal *soft* — `FM-GRAN` — mais ne tranche pas).

Ce fichier est l'**index** du canal Feature — même rôle que `MEMORY.md` pour le canal Mémoire.
C'est une **instance** de `ENTRY-TEMPLATE.md` (le méta-schéma commun à tous les canaux) : il n'en
redéfinit pas le frontmatter, seulement ce qui est **propre** au canal Feature.

## Le format — un fichier par fiche + une ligne d'index

- **`features/<slug>.md`** — une fiche par feature, frontmatter du canal `feature` en tête (voir
  `ENTRY-TEMPLATE.md §Le frontmatter commun` pour le détail des clés) :
  ```
  ---
  id: <slug>
  created: AAAA-MM-JJ
  updated: AAAA-MM-JJ
  links: [D-AAAA-MM-JJ-NN]        # optionnel — ids de décisions liées, ou autres entrées
  source: human                    # optionnel
  confidence: verified             # optionnel
  ratified: <qui>, AAAA-MM-JJ      # optionnel — requis si confidence: verified
  ---
  ```
  Requis pour ce canal : `id`, `created`, `updated`. Pas de `status` — une fiche Feature n'a pas
  d'états, contrairement au canal Décision ou Backlog.
- **Cet index (`FEATURE_MAP.md`)** — une ligne par fiche, jamais le détail :
  ```
  - [<slug>](features/<slug>.md) — <résumé ≤ 1 ligne>
  ```

*(`features/` est **vide au départ** — le projet adoptant la peuple au fil de l'eau, à mesure
qu'une feature devient assez importante pour mériter une fiche. `checks/feature-map-check.py`
vérifie la concordance fichier↔index et le format — voir ses règles.)*

## Le corps d'une fiche — clés canoniques

Le frontmatter est commun à tous les canaux ; le **corps**, lui, reste propre au canal Feature —
prose libre organisée par les clés suivantes (français ou langue de l'équipe, cf.
`ENTRY-TEMPLATE.md §Note — vocabulaire anglais par conception`) :

| Clé | Sens | Statut |
|---|---|---|
| `**Rôle :**` | ce que la feature fait, en 1 phrase — pour comprendre le sujet | cœur |
| `**Code :**` | les fichiers clés à regarder, regroupés par rôle du projet | cœur |
| `**Doc (durable) :**` | renvoi vers la doc d'archi/spec DURABLE du projet — jamais transitoire | cœur |
| `**Tests :**` | les tests qui couvrent le comportement | — |
| `**Motif d'ajout :**` | recette de réplication — utile surtout en data-driven | optionnel |

**Clés-cœur** (`checks/feature-map-check.py`, règles `FM1-*`) : une ligne `**Rôle :**`, ≥ 1
chemin de fichier sous `**Code :**`, et ≥ 1 référence durable — soit une clé `**Doc (durable) :**`
non vide, soit un id de décision `D-AAAA-MM-JJ-NN` (dans le corps ou dans `links:`). Une fiche
sans l'une de ces trois choses est **bloquante** : elle ne remplit pas son rôle de routeur.

## Exemple complet

<!-- template -->

`features/null-check-unity.md` :

```
---
id: null-check-unity
created: 2026-07-09
updated: 2026-07-09
links: [D-2026-07-09-01]
source: human
confidence: verified
ratified: raphael, 2026-07-09
---

**Rôle :** Empêche les faux-négatifs Unity — un `UnityEngine.Object` détruit reste « non-null »
pour `??`/`?.`, qui contournent l'override `==` d'Unity ; jamais de `??` sur un type Unity.

**Code :** `Scripts/Combat/CombatManager.cs` (résolution de tour), `Scripts/Core/NullGuard.cs`
(garde partagée `IsAlive`).

**Doc (durable) :** `Docs/architecture/ARCHITECTURE.md §Null check Unity`.

**Tests :** `Tests/EditMode/NullGuardTests.cs`.

**Motif d'ajout :** tout nouveau composant qui référence un `UnityEngine.Object` optionnel passe
par `NullGuard.IsAlive(obj)` plutôt qu'un opérateur `??`/`?.` cru.
```

Ligne correspondante dans `FEATURE_MAP.md` :

```
- [null-check-unity](features/null-check-unity.md) — garde anti-faux-négatif sur les null check Unity.
```

<!-- /template -->

## Fiches

<!-- (vide) — le projet adoptant la peuple : une ligne par fiche `features/<slug>.md`. -->
