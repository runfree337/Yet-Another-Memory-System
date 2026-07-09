# Mémoire « préférences & apprentissages »

Deux niveaux, à ne **jamais** mélanger :

- **Partagée** (règle d'équipe, **versionnée**) — une préférence ou une règle qui vaut pour tout le monde. Vit dans le dépôt (ici, ou la convention du projet) et n'évolue que de façon **explicite**.
- **Personnelle** (machine-locale, **non versionnée**) — tes raccourcis et apprentissages perso. Restent **hors du dépôt** (ex. la mémoire automatique de ton outil). Ne jamais les imposer à l'équipe.

**Promotion / rétrogradation** : un apprentissage perso qui se révèle d'intérêt général peut être *promu* en mémoire partagée — explicitement. À l'inverse, une « règle partagée » qui n'est qu'un goût individuel est *rétrogradée* hors du dépôt.

## Préférences partagées — un fait par fichier + frontmatter

Même format que la mémoire personnelle de ton outil (ex. l'auto-memory de Claude Code : « un
fait par fichier + frontmatter ; `MEMORY.md` = index ») — appliqué ici à la mémoire **partagée**.
Le frontmatter (et éventuellement le contenu) doit être **chargeable mécaniquement**, pas
extrait d'une ligne de prose au regex.

Ce canal est une **instance** du méta-schéma `GABARIT-ENTREE.md` — le frontmatter commun, la
ligne d'index, la concordance fichier↔index et le cycle de vie de la confiance y sont définis
**une fois pour toutes** ; ce paragraphe ne fait que situer l'instance Mémoire, il ne les
reproduit pas. Le canal Mémoire n'a **aucune clé propre** : le frontmatter commun suffit (pas de
`status`, à la différence des canaux Décision/Backlog).

- **`memory/<slug>.md`** — un fichier par préférence, frontmatter en tête (schéma complet →
  `GABARIT-ENTREE.md §Le frontmatter commun`) :
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
  <la règle elle-même, en prose libre>
  ```
- **Cet index (`MEMORY.md`)** — une ligne par fichier, jamais le détail, format uniforme du
  gabarit (`GABARIT-ENTREE.md §Le principe`) :
  ```
  - [<id>](memory/<slug>.md) — <résumé ≤ 1 ligne>
  ```

*(`memory/` vide au départ — le projet la peuple. `checks/memory-check.py` vérifie chaque fichier
contre `checks/entrylib.py::validate_entry(..., "memory")`, la concordance fichier↔index et les
liens croisés `links:` — voir sa docstring pour la table des règles.)*

## Provenance & confiance (contre l'empoisonnement)

Toute écriture en mémoire **partagée** (et toute note durable) porte **d'où elle vient** et **si
elle est validée** — clés `source`/`confidence` du frontmatter commun (`GABARIT-ENTREE.md`) :
- **`source`** — `inferred` (déduite par l'IA) · `human` (proposée par un humain) ·
  `external:<réf>` (reprise d'un **contenu externe** — doc tierce, issue, page web ; `<réf>` =
  url/id de la source).
- **`confidence`** — `verified` (un humain l'a ratifié) vs `unverified`.

Une mémoire `unverified` ou de source `external:` ne s'utilise **pas comme un fait** : on la
**recoupe** d'abord (code réel, source fiable, ou un humain). C'est le garde-fou contre le
*poisoning* — un contenu externe glissé dans une note ne devient pas « vérité d'équipe » par
simple persistance. **Rien n'est promu en partagé sans passer par le cycle de vie tracé ci-dessous.**

### Cycle de vie de la confiance

- **`unverified → verified`** exige `ratified: <qui>, <AAAA-MM-JJ>` dans le frontmatter — l'IA
  **propose** la promotion (le diff de frontmatter), l'humain **ratifie** (pose `ratified`).
  Jamais d'auto-promotion : une entrée `confidence: verified` sans `ratified` associé est
  signalée (`R-VERIFIED-NOT-RATIFIED`, à-confirmer — pas bloquant, mais reste une créance non
  soldée). Mécanique complète → `GABARIT-ENTREE.md §Cycle de vie de la confiance`.
- **La sortie** de `verified` (retrait ou révision) passe par la **revue sémantique** (étage 2,
  `checks/memory-audit.md`) **+ décision utilisateur**, et est **journalisée** (raison + historique
  git) — jamais silencieuse.

**Résolution de conflit** : entre deux mémoires qui se contredisent, la **plus confiante
l'emporte** — une `verified` n'est pas écrasée par une `unverified` (ni par une source
`external:` non recoupée) ; à confiance égale, la plus récente ratifiée.

**Mémoire ↔ code** : si une mémoire (décision, doc) diverge du **code** (la vérité observable)
sans qu'on sache lequel a dérivé — mémoire périmée *ou* code parti de l'intention — **l'utilisateur
tranche** ; l'IA **signale**, elle ne corrige jamais l'un pour l'autre en silence.

> Règle d'or : ce qui est versionné **lie tout le monde**. Ne versionner que le partagé, assumé.
