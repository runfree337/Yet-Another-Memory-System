# Mémoire « préférences & apprentissages »

Deux niveaux, à ne **jamais** mélanger :

- **Partagée** (règle d'équipe, **versionnée**) — une préférence ou une règle qui vaut pour tout le monde. Vit dans le dépôt (ici, ou la convention du projet) et n'évolue que de façon **explicite**.
- **Personnelle** (machine-locale, **non versionnée**) — tes raccourcis et apprentissages perso. Restent **hors du dépôt** (ex. la mémoire automatique de ton outil). Ne jamais les imposer à l'équipe.

**Promotion / rétrogradation** : un apprentissage perso qui se révèle d'intérêt général peut être *promu* en mémoire partagée — explicitement. À l'inverse, une « règle partagée » qui n'est qu'un goût individuel est *rétrogradée* hors du dépôt.

## Préférences partagées — un fait par fichier + frontmatter

Même format que la mémoire personnelle de ton outil (ex. l'auto-memory de Claude Code : « un
fait par fichier + frontmatter ; `MEMORY.md` = index ») — appliqué ici à la mémoire **partagée**.
Le frontmatter (et éventuellement le contenu) doit être **chargeable mécaniquement**, pas
extrait d'une ligne de prose au regex :

- **`memory/<slug>.md`** — un fichier par préférence, frontmatter en tête :
  ```
  ---
  source: déduite | humain | externe:<réf>
  confiance: validé | à vérifier
  ---
  <la règle elle-même, en prose libre>
  ```
- **Cet index (`MEMORY.md`)** — une ligne par fichier, jamais le détail :
  ```
  - [<slug>](memory/<slug>.md) — <résumé ≤ 1 ligne>
  ```

*(`memory/` vide au départ — le projet la peuple. `checks/memory-check.py` vérifie la
concordance fichier↔index et le frontmatter — voir ses règles.)*

## Provenance & confiance (contre l'empoisonnement)

Toute écriture en mémoire **partagée** (et toute note durable) porte **d'où elle vient** et **si elle est validée** :
- **Source** — déduite par l'IA · proposée par un humain · reprise d'un **contenu externe** (doc tierce, issue, page web).
- **Confiance** — `validé` (un humain l'a ratifié) vs `à vérifier`.

Une mémoire **`à vérifier`** ou de **source externe** ne s'utilise **pas comme un fait** : on la **recoupe** d'abord (code réel, source fiable, ou un humain). C'est le garde-fou contre le *poisoning* — un contenu externe glissé dans une note ne devient pas « vérité d'équipe » par simple persistance. **Rien n'est promu en partagé sans passer `validé`.**

**Résolution de conflit** : entre deux mémoires qui se contredisent, la **plus confiante l'emporte** — une `validé` n'est pas écrasée par une `à vérifier` (ni par une source externe non recoupée) ; à confiance égale, la plus récente ratifiée.

**Mémoire ↔ code** : si une mémoire (décision, doc) diverge du **code** (la vérité observable) sans qu'on sache lequel a dérivé — mémoire périmée *ou* code parti de l'intention — **l'utilisateur tranche** ; l'IA **signale**, elle ne corrige jamais l'un pour l'autre en silence.

> Règle d'or : ce qui est versionné **lie tout le monde**. Ne versionner que le partagé, assumé.
