# Index de navigation

> **Pour retrouver sans tout lire.** Une carte courte : **une ligne par unité** (projet / module / dossier majeur) — son rôle + ses dépendances. Assez petite pour être lue **en entier** avant d'agir. Le détail fin (fichier par fichier) se **grep**, il ne se lit pas en bloc.

## Unités (`Unité | Rôle (1 ligne) | Dépend de`)

<!-- À remplir selon le découpage RÉEL du projet — aucune hypothèse d'architecture. Format : -->

| Unité | Rôle | Dépend de |
|---|---|---|
| `<unité-a>` | <rôle> | — |
| `<unité-b>` | <rôle> | `<unité-a>` |

> **Gros projet** : ajouter un détail par unité (`chemin → intent`, **généré** par script, pas maintenu à la main) + le **graphe de dépendances** — base de l'analyse d'impact (« si je touche X, qui dépend de X ? »).

## Détail par-fichier (Format A) — gros projets

Quand la carte par-unité ne suffit pas, ajouter un index **par fichier** : un manifeste plat
`index/manifest.tsv` (`chemin<TAB>intent`, une ligne par fichier, **généré**, pas maintenu à la <!-- template -->
main).

- **Écriture** — `index/manifest.py` (`set` / `rm` / `get` / `stamp`) : seul moyen d'éditer le
  manifeste. Ne code aucune extension ni racine en dur — il lit `index/index-config.json`, comme <!-- template -->
  `index-check.py` ci-dessous. Détail des commandes → `../SCRIPTS.md`.
- **Intégrité** (chaque ligne ↔ un fichier réel ; chaque fichier indexable ↔ une ligne) — vérifiée
  en **lecture seule** par `../checks/index-check.py` (ne réécrit jamais l'index).

**Le projet définit ce qu'il indexe** — racines + extensions — dans `index/index-config.json` <!-- template -->
(schéma : `index/index-config.example.json`), typiquement **à l'installation du framework** : les
extensions à indexer dépendent du langage du projet, le framework ne les présume pas. Sans config,
`manifest.py` et `index-check.py` sont simplement **inactifs**. Ce format TSV est celui du projet
hôte de référence — on **ne touche pas** à son index existant, on adopte le même format.
