# Référence des scripts — intention + paramétrage

> Un script par entrée : ce qu'il **constate** (jamais ce qu'il corrige, sauf mention explicite),
> ses **paramètres**, ses **codes de sortie**. Les patrons de *câblage* (quand/où les lancer) sont
> documentés à part — `checks/README.md §À câbler` et `hooks/README.md §Câblage par outil` pour le
> **comment**, `INSTALL.md §Vue d'ensemble du câblage` pour l'arbre de décision. Ici : uniquement le
> script lui-même, indépendamment de son câblage.

## `checks/` — contrôles de méthode (Tier 1, déterministe)

### `backlog-check.py`
**Intention :** intégrité du `backlog/` (modèle frontmatter) — chaque chantier doc-backed a un
`ETAT.md` avec un frontmatter complet et cohérent (`id/titre/statut/jalon/apres/docs/maj`).

| Paramètre | Effet | Défaut |
|---|---|---|
| *(aucun)* | lance le contrôle complet, imprime le rapport texte | — |
| `--json` | même contrôle, sortie JSON | désactivé |
| `--board` | vue chantiers-par-jalon avec comptes (état live tiré des frontmatters) | — |
| `--state <id>` | déroule un chantier précis ; sans `<id>` liste les ids valides | — |
| `--stamp [fichiers…]` | **écrit** `maj: <aujourd'hui>` sur les `ETAT.md` cités, ré-enregistre le fichier | agit sur les fichiers passés en argument |
| `--stamp --staged` | même effet que `--stamp`, mais scope = `ETAT.md` **stagés** en git (`git diff --cached`), et **re-stage** après écriture | à câbler en pré-commit |
| `--checklist [id]` | imprime la checklist de clôture pour un chantier | — |

**Codes de sortie :** `0` propre · `1` id introuvable (`--state` sans hit) · `2` au moins une erreur `E*` sur le contrôle par défaut.
**Seule écriture du dossier `checks/` :** `--stamp` mute le champ `maj` et rien d'autre — borné, mécanique, jamais bloquant (cf. `checks/README.md §Câblage pré-commit`).

```bash
python3 checks/backlog-check.py                 # rapport texte
python3 checks/backlog-check.py --board          # vue d'ensemble
python3 checks/backlog-check.py --stamp --staged # pré-commit uniquement
```

### `feature-map-check.py`
**Intention :** structure de `FEATURE_MAP.md` — chaque fiche porte ses clés-cœur (Rôle, ≥1 chemin
de code, ≥1 référence durable), les ancres Sommaire↔fiches concordent, aucune référence transitoire.

| Paramètre | Effet | Défaut |
|---|---|---|
| *(aucun)* | rapport texte, trié erreurs puis candidats | — |
| `--json` | sortie JSON des findings (`severity`, `rule`, `where`, `msg`) | désactivé |

**Codes de sortie :** `0` propre · `1` au moins un candidat (`FM4`, granularité — *soft*) · `2` au moins une erreur dure (`FM1`/`FM2`/`FM5`).

```bash
python3 checks/feature-map-check.py
```

### `decisions-check.py`
**Intention :** concordance stricte entre les fichiers `decisions/D-*.md` et les lignes de
`decisions/INDEX.md`, par identifiant — aucun paramètre, aucune option, un seul mode.

**Codes de sortie :** `0` propre · `2` au moins un écart (`D1` fichier orphelin, `D2` ligne d'INDEX sans fichier).

```bash
python3 checks/decisions-check.py
```

### `doc-refs-check.py`
**Intention :** références de fichiers mortes dans la doc — un chemin cité dans un `.md` qui
n'existe pas/plus. Heuristique git (a existé puis disparu = bloquant ; jamais créé = à-confirmer).

| Paramètre | Effet | Défaut |
|---|---|---|
| `paths…` | limite le scan à ces chemins/fichiers | tout le corpus si omis avec `--staged` absent aussi → voir `gather()` |
| `--staged` | scanne le contenu **stagé** en git plutôt que le disque | désactivé |

**Codes de sortie :** `0` aucune référence morte · `1` uniquement des « à-confirmer » · `2` au moins un « BLOQUANT ».

```bash
python3 checks/doc-refs-check.py                 # corpus par défaut du script
python3 checks/doc-refs-check.py --staged         # pré-commit
python3 checks/doc-refs-check.py Docs/architecture/  # un sous-dossier
```

### `index-check.py`
**Intention :** intégrité de l'index par-fichier (`index/manifest.tsv` ↔ fichiers réels du dépôt).
**Inactif sans configuration** — le projet hôte doit fournir `index/index-config.json`.

| Paramètre | Effet | Défaut |
|---|---|---|
| `--config <chemin>` | chemin du fichier de config (`roots`, `extensions`, `ignore`, `base`, `manifest`) | `index/index-config.json` |
| `--base <chemin>` | racine du dépôt à scanner | `config.base`, sinon `cwd` |

**Codes de sortie :** `0` propre **ou** config absente/incomplète (inactif, pas une erreur) · `2` manifeste introuvable, config illisible, ou dérive détectée (`I1` entrée morte, `I2` fichier non indexé).

```bash
python3 checks/index-check.py                                    # nécessite index/index-config.json
python3 checks/index-check.py --config index/index-config.json --base .
```

### `memory-check.py`
**Intention :** intégrité du canal **Mémoire** — format « un fait par fichier + frontmatter »
(`../memory/<slug>.md`), `../MEMORY.md` = index. Deux familles de règles : (1) **frontmatter** de
chaque fichier — un `source: externe:...` DOIT porter un `confiance:` (sinon bloquant,
`MEMORY.md §Provenance`), un `confiance: à vérifier` est signalé comme candidate à l'audit
sémantique ; (2) **concordance fichier↔index** — tout `memory/<slug>.md` doit être référencé
par une ligne de `MEMORY.md` (sinon orphelin, bloquant) et réciproquement (sinon lien mort,
bloquant), même motif que `decisions-check.py`. Suit `GABARIT.md` à la lettre.

Pas de paramètre de ciblage (comme `decisions-check.py`, compare toujours `../MEMORY.md` et
`../memory/` en entier — une concordance fichier↔index ne se scope pas à un sous-ensemble).

| Paramètre | Effet | Défaut |
|---|---|---|
| `--json` | sortie JSON | désactivé |

**Codes de sortie :** `0` propre · `1` uniquement des « à-confirmer » (`R-UNVERIFIED`) · `2` au
moins un bloquant (`R-NO-FRONTMATTER`, `R-EXT-NO-CONF`, `R-ORPHAN-FILE`, `R-DEAD-INDEX`).

```bash
python3 checks/memory-check.py
python3 checks/memory-check.py --json
```

### `decisions-audit.py`
**Intention :** orchestrateur du **journal de décisions** — ne contrôle rien lui-même, enchaîne/agrège
les 4 scripts ci-dessus et pilote le cycle Tier 1 → Tier 2. Renommé depuis `memory-audit.py`
(D-2026-07-01-04, projet hôte) : son scope réel est le journal de décisions, pas toute la mémoire — voir
`memory-audit.py` ci-dessous pour l'orchestrateur multi-canal. Quatre modes mutuellement exclusifs
(priorité dans l'ordre : `--report` > `--merge` > `--plan` > `--tier1` > *défaut = les deux*).

| Paramètre | Effet | Défaut |
|---|---|---|
| `--tier1` | enchaîne `decisions-check`, `backlog-check`, `doc-refs-check`, `index-check`, imprime un verdict agrégé | — |
| `--plan` | découpe `decisions/INDEX.md` en lots équilibrés (offset/limit), un lot par reviewer | — |
| `--merge <fichiers…>` | agrège des sorties d'agents Tier 2, **contrôle de couverture** (chaque décision auditée exactement 1×) | — |
| `--report [dir]` | écrit un **rapport déterministe** (sans LLM) — pensé pour un cron OS headless | dossier : `$UC_MEMORY_REPORT_DIR` ou `.memory-reports/` |
| `--batch-size <n>` | taille des lots pour `--plan` | `33` |
| `--index <chemin>` | chemin du journal de décisions | `decisions/INDEX.md` |
| `--json` | sortie JSON (`--plan` seulement) | désactivé |
| *(aucun)* | équivaut à `--tier1` puis `--plan` | — |

**Codes de sortie :** `--tier1` → le pire code retour des 4 scripts sous-jacents (`0`/`1`/`2`) · `--plan`/`--report` → `0` (jamais bloquant, produisent un artefact) · `--merge` → `0` couverture complète, `1` décision non auditée ou auditée en double.

```bash
python3 checks/decisions-audit.py                              # tier1 + plan, usage courant
python3 checks/decisions-audit.py --plan --batch-size 20
python3 checks/decisions-audit.py --merge sortie_lot1.txt sortie_lot2.txt
python3 checks/decisions-audit.py --report                      # cron OS, headless
```

### `memory-audit.py`
**Intention :** orchestrateur **multi-canal** (Feature + Décision + Mémoire, `WORKFLOW.md §Les
trois mémoires`) — enchaîne `feature-map-check.py` et `decisions-audit.py --tier1` (qui couvre
déjà décisions/doc/index/backlog) et `memory-check.py`, résume par canal. Pas de `--plan`/`--merge`/
`--report` propres : seul le canal Décision accumule assez pour justifier un découpage en lots —
délégué à `decisions-audit.py`. Feature et Mémoire se relisent en un seul passage (petits par
construction).

| Paramètre | Effet | Défaut |
|---|---|---|
| `--tier1` | enchaîne les 3 canaux, imprime un verdict par canal | — |
| `--json` | sortie JSON | désactivé |
| *(aucun)* | équivaut à `--tier1` | — |

**Codes de sortie :** le pire code retour des 3 canaux sous-jacents (`0`/`1`/`2`).

```bash
python3 checks/memory-audit.py                              # tier1 sur les 3 canaux
python3 checks/memory-audit.py --json
```

---

## `index/` — maintenance du manifeste (écriture)

Pendant en écriture de `index-check.py` ci-dessus (qui reste lecture seule). Même config
agnostique (`index/index-config.json`), pas de logique de vérification dupliquée entre les deux.

### `manifest.py`
**Intention :** seul moyen d'éditer `index/manifest.tsv` — ajoute/retire une entrée, garde le
fichier trié et dédupliqué. **Inactif sans configuration**, comme `index-check.py`.

| Commande | Effet |
|---|---|
| `set <chemin> <intent>` | upsert l'entrée (ajoute ou remplace l'intent), ré-écrit le manifeste trié |
| `rm <chemin>` | retire l'entrée ; no-op si absente |
| `get <chemin>` | imprime l'intent de ce chemin (vide si absent) |
| `stamp` | si `hub` est renseigné dans la config, met à jour sa ligne `> Last updated: ...` (date + commit court) ; **no-op** si `hub` est `null`/absent, ou si le fichier n'a pas cette ligne |

Pas de commande `check` ici — c'est `checks/index-check.py` qui vérifie la dérive ; `manifest.py`
ne fait qu'écrire ce qu'on lui donne, il ne scanne pas le dépôt pour la détecter lui-même.

**Codes de sortie :** `0` commande exécutée · `1` config absente/illisible, ou usage invalide (aucune commande reconnue, imprime l'aide) · `2` `hub` configuré mais introuvable sur disque.

```bash
python3 index/manifest.py set src/foo.py "point d'entrée du parseur"
python3 index/manifest.py rm src/old.py
python3 index/manifest.py get src/foo.py
python3 index/manifest.py stamp             # met à jour index/INDEX.md si `hub` pointe dessus
```

---

## `hooks/` — gardes universelles (sécurité, portables)

Toutes partagent le même contrat à deux entrées : une **entrée universelle** (chemins/`--staged`,
pour git ou usage manuel) et une **entrée adaptateur Claude Code** (`--stdin-json`, lit le JSON
`tool_name`/`tool_input` du hook). Voir `hooks/README.md §Câblage par outil` pour le où/quand.

### `poisoning-scan.py`
**Intention :** détecte l'Unicode invisible/bidi dans les fichiers d'instruction et de mémoire
(vecteur d'empoisonnement — texte caché qui trompe l'IA sans être visible à l'œil).

| Paramètre | Effet | Défaut |
|---|---|---|
| `paths…` | fichiers/chemins à scanner | — |
| `--staged` | scanne le contenu stagé en git | désactivé |
| `--stdin-json` | lit `{tool_name, tool_input}` sur stdin, extrait `tool_input.file_path` | désactivé |

**Codes de sortie :** `0` propre (ou JSON illisible en mode `--stdin-json` — n'échoue jamais l'hook) · `2` caractères suspects trouvés → **bloquer**.

```bash
python3 hooks/poisoning-scan.py --staged
echo '{"tool_name":"Write","tool_input":{"file_path":"CLAUDE.md"}}' | python3 hooks/poisoning-scan.py --stdin-json
```

### `secret-scan.py`
**Intention :** détecte des clés/jetons commités ou écrits (18 motifs — fournisseurs cloud, VCS,
messagerie, paiement…).

| Paramètre | Effet | Défaut |
|---|---|---|
| `paths…` | fichiers à scanner directement | — |
| `--staged` | scanne le contenu stagé en git | comportement par défaut si ni `paths` ni `--stdin-json` |
| `--stdin-json` | adaptateur Claude Code : sur `Bash` avec `git commit` → scanne le stagé ; sur `Write`/`Edit` → scanne le contenu écrit (fichiers allowlistés/extensions à ignorer exclus) | désactivé |

**Codes de sortie :** `0` propre · `2` secret potentiel trouvé → **bloquer**, masqué dans le rapport.

```bash
python3 hooks/secret-scan.py --staged
python3 hooks/secret-scan.py chemin/vers/fichier.env
```

### `destructive-guard.py`
**Intention :** repère les commandes shell destructrices larges (`find … -delete`, `-exec rm`,
etc.) — seule garde qui ne bloque pas mais **demande confirmation**.

| Paramètre | Effet | Défaut |
|---|---|---|
| `--command "<cmd>"` | commande à évaluer, mode universel | `""` |
| `--stdin-json` | adaptateur Claude Code : sur `Bash` destructrice → émet une réponse `permissionDecision: "ask"` (JSON sur stdout) au lieu de bloquer | désactivé |

**Codes de sortie :** mode universel — `0` inoffensive · `2` destructrice → **bloquer** (le mode non-interactif ne peut pas « demander », donc il bloque). Mode `--stdin-json` — toujours `0`, la décision est portée par le JSON émis (`ask` ou rien).

```bash
python3 hooks/destructive-guard.py --command "find . -name '*.tmp' -delete"
```

---

## Ce qui n'a PAS sa place ici

Les scripts **tech-spécifiques** du projet hôte (lint, tests, analyzers…) ne sont pas dans ce
framework — ils restent documentés par le projet lui-même. Ce fichier ne référence que ce que
`_meta/ai-workflow/` fournit. Pour en écrire un côté projet (comme `audit.py` du projet hôte de
référence) : `checks/GABARIT.md` donne la forme commune, pas le contenu tech-spécifique.

> **Attention à l'homonymie** : le projet hôte de référence a son **propre** `manifest.py`
> (`.claude/skills/project-index/manifest.py`) et son **propre** `doc-audit.py`
> (`.claude/skills/doc-audit/doc-audit.py`) — plus riches, câblés sur son arborescence réelle
> (`Assets/Project/`, `decisions/` avec le préfixe `Docs/`, `index-filter.txt`…). Le
> `index/manifest.py` **de ce framework** est un script distinct, généralisé sur
> `index-config.json` — il n'a pas de commande `check` (déléguée à `checks/index-check.py`) ni de
> filtre `index-filter.txt` dédié (couvert par `roots`/`extensions`/`ignore` de la config).
