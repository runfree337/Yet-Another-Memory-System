# Mémoire « décision » — protocole

Le *pourquoi* des choix **structurels** : pivot d'organisation, abandon d'une piste, choix d'un outil, périmètre tranché, convention transverse.

Ce canal est une **instance** de `../ENTRY-TEMPLATE.md` (le méta-schéma commun à toute entrée
mémoire — un fichier + une ligne d'index, frontmatter commun). Ce qui suit ne redéfinit que ce
qui est **propre au canal Décision** ; les clés communes (`id`, `source`, `confidence`, `created`,
`updated`, `links`, `ratified`) et leur cycle de vie vivent dans `ENTRY-TEMPLATE.md`.

1. **Un fichier par décision** : `D-AAAA-MM-JJ-NN.md` + **sa ligne dans `INDEX.md`**, écrits **au même moment**.
2. **On lit `INDEX.md` d'abord** (1 ligne par décision). Le détail ne s'ouvre qu'au besoin du *pourquoi*.
3. **Format d'un `D-*.md`** — un frontmatter au-dessus de trois rubriques en prose libre :

   ```
   ---
   id: D-2026-07-09-01
   status: active
   source: human
   confidence: verified
   created: 2026-07-09
   updated: 2026-07-09
   replaces: []
   replaced-by: null
   links: []
   ratified: raphael, 2026-07-09
   ---

   **Décision** : ce qui est tranché.

   **Pourquoi** : la raison + les alternatives écartées.

   **Invariant** : la règle qui survit (vérifiable).
   ```

   Clés **communes** (`ENTRY-TEMPLATE.md`) : `id`, `source`, `confidence`, `created`, `updated`,
   `links`, `ratified`. Clés **propres au canal** :

   | Clé | Sens |
   |---|---|
   | `status` | `active \| revoked \| archived` — **obligatoire** pour ce canal. |
   | `replaces` | `[<ids>]` — décisions que celle-ci remplace (réciproque de `replaced-by`). |
   | `replaced-by` | `<id>` — décision qui remplace celle-ci, une fois révoquée. |

   Le **corps** garde ses trois rubriques canoniques, chacune amorcée par une puce en gras —
   **Décision** / **Pourquoi** / **Invariant** — vérifiées mécaniquement par
   `checks/decisions-check.py` (règle `D4`). C'est la forme canonique retenue (par opposition à
   des titres `##`) : elle correspond à ce que ce protocole documentait déjà avant frontmatter,
   aucune migration de corps existant à faire.
4. **Révocation** : une décision qui en contredit une autre passe `status: revoked` et pointe
   `replaced-by: <id-du-successeur>` ; le successeur porte la réciproque
   `replaces: [<id-revoked>, …]`. C'est désormais une **transition de `status` + liens,
   vérifiable mécaniquement** (`checks/decisions-check.py`, règle `D6` : la cible de
   `replaced-by` existe, la réciprocité `replaces` tient, aucun cycle) — plus une pure discipline
   de prose. Le fond ne change pas : si l'ancienne décision **a été implémentée**, elle reste un
   **tombstone** — fichier conservé (`status: revoked`), ligne conservée dans `INDEX.md` (« ne
   pas réintroduire X » reste vivant). Si elle n'a **jamais été implémentée**, elle est
   **supprimée** (fichier + ligne d'INDEX) et le successeur absorbe l'alternative rejetée — pas
   de tombstone pour du jamais-bâti. Doute = conserver.
5. **Archivage** : une décision caduque passe `status: archived` **et** sa ligne migre sous
   `## Archivées` de `INDEX.md` — les deux **à la fois**. C'est désormais une **transition de
   `status` + section d'index, vérifiable mécaniquement** (`checks/decisions-check.py`, règle
   `D5` : une entrée `archived` référencée sous `## Actives`, ou une `active` référencée sous
   `## Archivées`, est bloquante). La ligne quitte l'index actif dès qu'une **autorité vivante
   tient sa porte** — un successeur encore indexé (`replaced-by` résolu, cf. `D6`), un
   test-garde, la doc d'archi ; elle ne **reste** sous Actives que si la décision `revoked` est
   l'**unique gardienne** d'une contrainte vivante (pas d'autre domicile pour « ne pas
   réintroduire X »). Ainsi l'index **rétrécit** au lieu de croître sans fin (un index
   *append-only* finit illisible) ; le **registre permanent** reste les fichiers archivés + git.
   **Vérifier qu'une option déjà écartée ne ressort pas = consulter l'index actif ET les
   archivées.**
6. **Provenance** : `source` / `confidence` / `ratified` suivent le **cycle de vie commun**
   défini par `../ENTRY-TEMPLATE.md §Cycle de vie de la confiance` — une décision est
   **ratifiée par un humain** (`confidence: verified` + `ratified: <qui>, <AAAA-MM-JJ>`), pas une
   inférence non vérifiée laissée telle quelle. Si elle découle d'un contenu externe
   (`source: external:<réf>`, `confidence` alors obligatoire — sinon bloquant, `R-EXT-NO-CONF`),
   le noter aussi dans le *Pourquoi*.

> Un fichier par décision (vs un gros fichier unique) = aucun conflit quand plusieurs contributeurs en ajoutent en parallèle.

## Modèle de pruning (quand on élague une mémoire)

1. **Conflit mémoire ↔ mémoire** — la plus récente *et au moins aussi fiable* l'emporte (une `validé` n'est pas écrasée par une `à vérifier`) → révocation (jamais-bâti → suppression ; bâti → tombstone).
2. **Conflit mémoire ↔ code (la vérité)** — la doc/décision dit X, le code fait Y. Le code est la réalité, mais le sens du correctif (mémoire périmée ou code dérivé) n'est pas tranchable par la machine → **l'utilisateur tranche** ; l'IA **signale**, ne corrige jamais l'un pour l'autre en silence.
3. **Redondance** — déjà porté par une autorité vivante (test / archi / fiche) → suppression / promotion.
4. **Volume** — audit quand l'index gonfle, **exécuté** via l'orchestrateur `checks/decisions-audit.py` (recette + barème de revue : `checks/decisions-audit.md`, volet décisions de l'audit multi-canal `checks/memory-audit.md`). **Pas de TTL / âge seul** (« pas utilisé » ≠ « inutile »).

Tout élagage est **journalisé** (référence au successeur + raison + git) ; jamais silencieux.
