# Mémoire « décision » — protocole

Le *pourquoi* des choix **structurels** : pivot d'organisation, abandon d'une piste, choix d'un outil, périmètre tranché, convention transverse.

1. **Un fichier par décision** : `D-AAAA-MM-JJ-NN.md` + **sa ligne dans `INDEX.md`**, écrits **au même moment**.
2. **On lit `INDEX.md` d'abord** (1 ligne par décision). Le détail ne s'ouvre qu'au besoin du *pourquoi*.
3. **Format d'un `D-*.md`** :
   - **Décision** : ce qui est tranché.
   - **Pourquoi** : la raison + les alternatives écartées.
   - **Invariant** : la règle qui survit (vérifiable).
4. **Révocation** : une décision qui en contredit une autre le signale. Si l'ancienne **a été implémentée**, elle passe à « révoquée → D-X » aux **deux** endroits (ligne conservée : « ne pas réintroduire X » reste vivant). Si elle n'a **jamais été implémentée**, la **supprimer** (le successeur absorbe l'alternative rejetée) — pas de tombstone pour du jamais-bâti. Doute = conserver.
5. **Archivage** : une décision caduque **sort de l'index actif** (déplacée sous « Archivées »). La ligne quitte l'index **dès qu'une autorité vivante tient sa porte** — un **successeur encore indexé**, un **test-garde**, la **doc d'archi** ; elle ne **reste** que si la décision archivée est l'**unique gardienne** d'une contrainte vivante (« ne pas réintroduire X » sans autre domicile). Ainsi l'index **rétrécit** au lieu de croître sans fin (un index *append-only* finit illisible) ; le **registre permanent** reste les fichiers archivés + git. **Vérifier qu'une option déjà écartée ne ressort pas = consulter l'index actif ET les archivées.**
6. **Provenance** : une décision est **ratifiée par un humain** (un choix d'équipe, pas une inférence non vérifiée). Si elle découle d'un contenu externe, le noter dans le *Pourquoi*.

> Un fichier par décision (vs un gros fichier unique) = aucun conflit quand plusieurs contributeurs en ajoutent en parallèle.

## Modèle de pruning (quand on élague une mémoire)

1. **Conflit mémoire ↔ mémoire** — la plus récente *et au moins aussi fiable* l'emporte (une `validé` n'est pas écrasée par une `à vérifier`) → révocation (jamais-bâti → suppression ; bâti → tombstone).
2. **Conflit mémoire ↔ code (la vérité)** — la doc/décision dit X, le code fait Y. Le code est la réalité, mais le sens du correctif (mémoire périmée ou code dérivé) n'est pas tranchable par la machine → **l'utilisateur tranche** ; l'IA **signale**, ne corrige jamais l'un pour l'autre en silence.
3. **Redondance** — déjà porté par une autorité vivante (test / archi / fiche) → suppression / promotion.
4. **Volume** — audit quand l'index gonfle, **exécuté** via l'orchestrateur `checks/decisions-audit.py` (recette + barème de revue : `checks/decisions-audit.md`, volet décisions de l'audit multi-canal `checks/memory-audit.md`). **Pas de TTL / âge seul** (« pas utilisé » ≠ « inutile »).

Tout élagage est **journalisé** (référence au successeur + raison + git) ; jamais silencieux.
