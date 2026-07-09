# Gabarit d'une entrée mémoire — comment en écrire une nouvelle

> **Pour qui.** Ce fichier ne fournit **pas** une mémoire — c'est le **méta-schéma** que suit
> chaque entrée des canaux mémoire de ce framework (`WORKFLOW.md §Les trois mémoires`), au même
> titre que `checks/GABARIT.md` normalise la forme d'un **check**. Écrire une nouvelle entrée
> sans repartir de ce gabarit, c'est redécouvrir à la main un choix déjà tranché de façon
> identique dans chaque canal.
>
> **Bibliothèque associée :** `checks/entrylib.py` — parseur de frontmatter + validation du
> schéma commun, importée par les checks de canal (`memory-check.py`, `decisions-check.py`,
> `feature-map-check.py`, `backlog-check.py`). Un seul endroit définit ce qu'est une entrée
> mémoire valide ; ce fichier documente ce que cet endroit applique.

## Le principe

Toute entrée mémoire = **un fichier + une ligne d'index**, écrits au même moment :

- Le **fichier** ouvre par un **frontmatter commun** (ci-dessous), suivi d'un **corps en prose
  libre**, propre au canal — le gabarit ne contraint pas le corps, seulement le frontmatter.
- La **ligne d'index** est uniforme entre canaux :
  ```
  - [<id>](<chemin>) — <résumé ≤ 1 ligne>
  ```
  Un id, un lien vers le fichier, un résumé qui tient sur une ligne — jamais le détail dupliqué
  dans l'index (le détail vit dans le fichier, l'index ne fait que pointer).

## Le frontmatter commun

```
---
id: mem-null-check-unity
source: human
confidence: verified
created: 2026-07-09
updated: 2026-07-09
links: [D-2026-07-09-01]
ratified: raphael, 2026-07-09
---
```

| Clé | Sens |
|---|---|
| `id` | Identifiant stable, greppable — sert de clé de concordance fichier↔index (`checks/entrylib.py::check_index_concordance`). Ne change jamais après création. |
| `status` | Valeurs **propres au canal** (voir table d'instanciation ci-dessous) — absent des canaux Mémoire et Feature, présent (obligatoire) pour Décision et Backlog. |
| `source` | `inferred \| human \| external:<réf>` — d'où vient l'entrée. Toute source `external:` porte obligatoirement `confidence` (sinon `R-EXT-NO-CONF`, bloquant). |
| `confidence` | `verified \| unverified` — si un humain l'a ratifiée ou non. Gouverne la promotion (voir cycle de vie ci-dessous). |
| `created` | AAAA-MM-JJ, date de création — écrite une fois, jamais retouchée. |
| `updated` | AAAA-MM-JJ, **stampée mécaniquement** (`checks/entrylib.py::stamp_updated`, ou l'équivalent `--stamp` d'un check de canal) — jamais bumpée à la main. |
| `links` | `[<ids ou chemins>]` — références croisées inter-canaux (ex. une fiche Feature qui pointe une décision `D-AAAA-MM-JJ-NN`). |
| `ratified` | `<qui>, <AAAA-MM-JJ>` — **requis** pour passer `confidence: verified` (traçabilité de la ratification humaine). Absent sur une entrée `verified` = à-confirmer, pas bloquant (`R-VERIFIED-NOT-RATIFIED`). |

Ces clés et leurs valeurs sont volontairement en **anglais** (voir §Note en bas de page) ; le
**corps** de l'entrée, lui, reste dans la langue de l'équipe.

## Instanciation par canal

Chaque canal **détaille ses propres règles** dans son README (`MEMORY.md`, `decisions/README.md`,
`FEATURE_MAP.md`, `backlog/README.md`) — la table ci-dessous ne fait que situer l'instance :

<!-- gabarit -->

| Canal | Fichier d'entrée | Index | Clés propres | Notes |
|---|---|---|---|---|
| **Mémoire** | `memory/<slug>.md` | `MEMORY.md` | *(aucune — le frontmatter commun suffit)* | Pas de `status` obligatoire. |
| **Décision** | `decisions/D-AAAA-MM-JJ-NN.md` | `decisions/INDEX.md` | `status: active \| revoked \| archived`, `replaces: [ids]`, `replaced-by: <id>` | `status` obligatoire ; la révocation/l'archivage est une **transition de `status` + liens**, vérifiable — plus une pure discipline de prose. |
| **Feature** | `features/<slug>.md` | `FEATURE_MAP.md` | *(aucune — le frontmatter commun suffit)* | Pas de `status` obligatoire ; le corps garde ses rubriques propres (Rôle/Code/Doc/Tests/Motif d'ajout). |
| **Backlog** | `backlog/<id>/ETAT.md` | `backlog/INDEX.md` | `status: todo \| in-progress`, `title`, `milestone`, `after: [ids]`, `docs: [chemins]` | **Transitoire** (le *todo*), pas une mémoire — mais suit le **même format d'entrée**. Les tâches de la rubrique `## Tasks` du corps portent leur propre sous-état `todo \| in-progress \| blocked \| done`, distinct du `status` du chantier lui-même. |

<!-- /gabarit -->

## Cycle de vie de la confiance

- **`unverified → verified`** exige `ratified: <qui>, <AAAA-MM-JJ>` dans le frontmatter — l'IA
  **propose** la promotion (le diff de frontmatter), l'humain **ratifie** (pose `ratified`).
  Jamais d'auto-promotion : une entrée qui passe `verified` sans `ratified` associé est signalée
  (`R-VERIFIED-NOT-RATIFIED`, à-confirmer), pas bloquée — mais reste une créance non soldée.
- **La sortie** (`verified` → retrait ou révocation) passe par la **revue sémantique** (étage 2,
  cf. `checks/memory-audit.md` / `checks/decisions-audit.md`) **+ décision utilisateur**, et est
  **journalisée** (référence au successeur + raison + historique git) — jamais silencieuse.
- Le fond de la règle (provenance, empoisonnement, résolution de conflit entre deux mémoires)
  est posé une fois pour toutes dans `MEMORY.md §Provenance & confiance` — ce fichier n'en donne
  que la mécanique de frontmatter.

## Note — vocabulaire anglais par conception

Les **clés et valeurs de frontmatter** sont une API machine (parsées par `checks/entrylib.py`,
grep-ées par les checks et les agents) : elles sont en **anglais dès maintenant**, sans attendre
la traduction générale du framework (`PLAN.md` étape 3, qui portera sur la **prose**). La **prose
du corps** d'une entrée, elle, reste dans la langue de l'équipe — ce gabarit ne la contraint pas.
