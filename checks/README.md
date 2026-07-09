# `checks/` — contrôles déterministes du process

> Premier étage du motif **deux niveaux** : un **script mécanique zéro faux positif** (il *constate*, ne juge pas) **→** une **revue sémantique** (le jugement, assuré par la **revue du projet**). Par défaut aucun ne corrige : ils **signalent** — seule exception assumée, le mode `--stamp` (`backlog-check.py`, `feature-map-check.py`, `memory-check.py` — mécanique, borné au champ `updated` et au scope stagé), voir « Câblage pré-commit » plus bas.
>
> **Écrire un nouveau contrôle** (agnostique ici, ou tech-spécifique côté projet hôte) → suivre
> [`GABARIT.md`](GABARIT.md) : la forme commune (`Finding`, deux verdicts, `collect()` git-aware,
> règles pures, code retour `0/1/2`) que tous les linters de ce type convergent vers, indépendamment.

## Fournis (agnostiques)

- **`backlog-check.py`** — intégrité du `backlog/` (canal Backlog du gabarit d'entrée, `GABARIT-ENTREE.md`) : chaque chantier doc-backed = un dossier `<id>/` dont l'`ETAT.md` porte un frontmatter complet (`id/title/status/milestone/after/docs/updated`, validé via `entrylib`) **et une rubrique `## Tâches`** (états `todo/in-progress/blocked/done`, libellé ≤ 30 mots ou renvoi `→ doc de travail`) ; `milestone`⟺groupe INDEX, `after`→id réel, `docs`⟺compagnons ; garde anti-accumulation *soft* (ETAT.md > 80 lignes ou rubrique hors canon → « du durable vit dans l'état »). Vues `--board` et `--state <id>` avec compteurs de tâches, `--json` possible. **`--stamp --staged`** : pose `updated = aujourd'hui` sur les ETAT.md stagés + re-stage — **à câbler au PRÉ-COMMIT**.
- **`feature-map-check.py`** — intégrité du canal **Feature** (un fichier par fiche `features/<slug>.md` + `FEATURE_MAP.md` en index) : concordance fichier↔index, frontmatter du canal (`entrylib`), clés-cœur du corps (une ligne `**Rôle`, ≥ 1 chemin de code, ≥ 1 réf durable), existence des ids `D-*` cités, aucune réf transitoire (`backlog/`), fraîcheur (`updated` vs dernier commit des chemins cités) et granularité en signal **soft**. Dead-path délégué à `doc-refs-check.py`. `--stamp --staged` sur `updated`.
- **`decisions-check.py`** — intégrité du canal **Décision** : concordance fichiers `D-*.md` ↔ lignes d'`INDEX.md` (D1/D2), frontmatter du canal via `entrylib` (D3), rubriques canoniques du corps (D4), `status` ⟺ section Actives/Archivées (D5), graphe de révocation `replaces`/`replaced-by` sain — réciprocité, pas de cycle (D6), liens croisés résolus (D7).
- **`memory-check.py`** — intégrité du canal **Mémoire** : un fait par fichier + frontmatter (`memory/<slug>.md`), `MEMORY.md` = index. Toute la logique vit dans `entrylib` (frontmatter du canal, concordance fichier↔index, liens croisés) ; `source: external:` sans `confidence` → bloquant ; `confidence: unverified` ou `verified` non `ratified` → candidate à l'étage 2. `--stamp --staged` sur `updated`. Suit `GABARIT.md` à la lettre.
- **`decisions-audit.py`** — orchestrateur d'**audit du journal de décisions** (déclencheur « Volume » quand l'INDEX gonfle — le seul canal qui accumule assez pour le justifier). `--tier1` enchaîne `decisions-check`/`backlog-check`/`doc-refs-check`/`index-check` ; `--plan` découpe `decisions/INDEX.md` en lots équilibrés (offset/limit) pour confier une tranche par reviewer ; `--merge` agrège les sorties de revue **avec contrôle de couverture** (chaque décision auditée exactement 1×). Étage 1 (mécanique) ; l'étage 2 (jugement : drift mémoire↔code, redondance, conflit) suit le **barème** de revue `decisions-audit.md`.
- **`memory-audit.py`** — orchestrateur **multi-canal** (Feature + Décision + Mémoire) : `--tier1` enchaîne `feature-map-check` + `decisions-audit --tier1` + `memory-check`, résume par canal. Pas de `--plan`/`--merge` propres — délégués à `decisions-audit.py` pour son seul canal qui en a besoin. Étage 2 (jugement, les 3 canaux) : barème `memory-audit.md`.
- **`doc-refs-check.py`** — **références mortes** dans la doc : un chemin de fichier cité dans un `.md` qui n'existe pas / plus. Tier ferme zéro-FP (heuristique git : a existé puis disparu → bloquant ; jamais créé → à-confirmer). La dérive *sémantique* reste à la revue.
- **`index-check.py`** — **intégrité de l'index par-fichier** (`manifest.tsv` ↔ fichiers réels). Le **projet** définit racines + extensions dans `index/index-config.json` (à l'installation) ; sans config, inactif. Cf. `../index/INDEX.md`. <!-- gabarit -->

Code retour ≠ 0 si dérive → exploitables en gate. Lancer à la main :

```bash
python3 checks/backlog-check.py
python3 checks/feature-map-check.py
python3 checks/decisions-check.py
python3 checks/memory-check.py
python3 checks/doc-refs-check.py
python3 checks/index-check.py             # nécessite index/index-config.json
python3 checks/decisions-audit.py         # tier1 décisions + plan d'audit du journal
python3 checks/memory-audit.py            # tier1 multi-canal (feature + décisions + mémoire)
```

## À câbler — tourner automatiquement

**Deux natures, deux régimes.** Le structurel (ces scripts) est bon marché et se branche pour tourner souvent ; le sémantique (l'audit `memory-audit`, étage 2) coûte un agent et **ne se hooke pas**.

**Structurel — déterministe, hookable :**
- **Claude Code** : `SessionStart` (dérive post-merge / inter-session — démarrer propre) et/ou `Stop` (fin de tour).
- **CI** : un job qui échoue si un check sort ≠ 0.
- **Sinon** : à la main avant de clôturer un chantier.

> **Règle du silence — sinon ça coûte cher.** La sortie d'un hook `SessionStart` est **injectée dans le contexte** = des tokens, payés toute la session. Un hook de check doit donc être **MUET sur succès** (rien imprimé → 0 token) et n'émettre qu'**une ligne terse par dérive**. Keyer sur le **code retour** ou un **marqueur ASCII** (pas de parsing d'en-têtes localisés/accentués — fragile selon la locale), jamais déverser le rapport complet.
>
> ```sh
> # sweep structurel muet + rapport en attente (SessionStart) — squelette agnostique
> PY=$(command -v python3 || command -v python); [ -z "$PY" ] && exit 0
> lines=""
> "$PY" checks/decisions-check.py >/dev/null 2>&1 || lines="${lines}• décisions: dérive\n"
> "$PY" checks/backlog-check.py   >/dev/null 2>&1; [ $? -eq 2 ] && lines="${lines}• backlog: erreur\n"
> "$PY" checks/doc-refs-check.py 2>/dev/null | grep -q BLOQUANT && lines="${lines}• doc: réf morte\n"
> [ -n "$lines" ] && printf "⚠️ dérive structurelle au démarrage :\n%b" "$lines"
> # rapport d'audit en attente (produit hors session par le cron OS, cf. §Sémantique) → l'agent DEMANDE
> REPORT="${UC_MEMORY_REPORT_DIR:-.memory-reports}/memory-report.md"
> [ -f "$REPORT" ] && printf "📋 rapport mémoire en attente: %s — DEMANDER à l'utilisateur de le traiter, puis le supprimer.\n" "$REPORT"
> exit 0          # MUET si ni dérive ni rapport → 0 token injecté
> ```
>
> Ce sweep est le **consommateur** de la boucle ; le **producteur** est `decisions-audit.py --report` lancé par le cron OS (§Sémantique) — le canal Décision est le seul dont le volume justifie ce rapport programmé. Producteur déterministe (sans LLM, hors session) + consommateur muet (surface, l'humain décide) = audit pendant l'absence **sans** dépense LLM autonome.

> **Câblage `Stop` — le rappel détaillé, PAR check (gated exit code).** Second patron
> read-only, distinct du sweep `SessionStart` : au lieu d'agréger plusieurs checks en une
> ligne globale, **un hook par check**, déclenché en fin de tour, qui se tait sur code
> retour propre et sinon relaie le rapport **du check lui-même** + la commande de
> correctif à lancer. Plus verbeux que le sweep `SessionStart`, donc réservé à la fin de
> session (pas à chaque tour ni à chaque outil) — c'est le dernier geste avant de clore,
> quand le coût de laisser dériver est le plus élevé.
>
> ```sh
> # Stop, un hook par check — squelette agnostique (ex. pour index-check.py)
> PY=$(command -v python3 || command -v python); [ -z "$PY" ] && exit 0
> report=$("$PY" checks/index-check.py 2>&1); code=$?
> [ "$code" -eq 0 ] && exit 0   # muet sur état propre
> printf '[index-check] dérive — %s\nCorrige avant de clore, ou relance `python3 checks/index-check.py`.\n' "$report"
> exit 0   # jamais bloquant — informe seulement
> ```
>
> Implémentation embarquée : `adapters/claude-code/hooks/stop-check.sh` — même patron, paramétré
> par le nom du check en argument (ex. `stop-check.sh index-check`, `stop-check.sh backlog-check`).
> Généralisable à tout check de ce dossier : un hook `Stop` de plus par check qu'on veut voir
> rappelé en détail avant la fin de session, au-delà de la ligne globale du sweep `SessionStart`.

> **Câblage pré-commit — le cas MUTANT (`--stamp`).** Un seul check de ce dossier ne se
> contente pas de signaler : `backlog-check.py --stamp --staged` **écrit** (date de
> fraîcheur `maj`) puis **re-stage**, AVANT que `git commit` ne s'exécute — la date du
> frontmatter devient mécaniquement la date du commit, sans bump manuel qui pourrit.
> Trois garde-fous qui en font une mutation sûre (pas une correction sémantique
> déguisée) : (1) scope **strictement stagé** (`--staged`) — ne tire jamais un fichier
> hors du commit en cours ; (2) le champ touché est **mécanique** (une date), jamais un
> jugement ; (3) **jamais bloquant** — si l'écriture échoue, le commit part quand même,
> non tamponné, à corriger au tour suivant.
>
> ```sh
> # PreToolUse(Bash), matcher "git commit*", AVANT l'exécution de la commande
> PY=$(command -v python3 || command -v python); [ -z "$PY" ] && exit 0
> "$PY" checks/backlog-check.py --stamp --staged >/dev/null 2>&1
> exit 0   # ne bloque jamais — la correction est silencieuse, git commit voit le stamp
> ```
>
> Implémentation embarquée : `adapters/claude-code/hooks/pre-commit-stamp.sh`.
> Généralisable à tout check qui gagnerait un mode `--stamp` sur un champ mécanique
> similaire (ex. une date de fraîcheur équivalente ailleurs) — même triple garde-fou.

**Sémantique — agent, mémoire↔code :** l'audit `memory-audit` (étage 2, les 3 canaux) **n'est pas un hook** — il exige un jugement *retrieve-then-verify* et ne peut pas tourner muet à chaque session. Son régime : **déclencheur Volume** (côté Décision, le seul canal qui gonfle assez pour ça), **ou planifié**, **ou à la demande**. Pour le planifié *pendant l'absence*, la boucle rapport (cf. `INSTALL.md` étape 5) : un **cron OS** lance `decisions-audit.py --report` → écrit un rapport **déterministe** (étage 1, **sans LLM**, 0 token) dans `$UC_MEMORY_REPORT_DIR` (défaut `.memory-reports/`, **à gitignorer**) ; le sweep `SessionStart` ci-dessus le **détecte et le surface** ; l'agent **demande**, l'utilisateur **décide** de réveiller l'étage 2 (LLM, à la demande — `memory-audit.py --tier1` d'abord si les canaux Feature/Mémoire sont aussi en doute). Dans tous les cas il **signale** ; l'élagage reste **ratifié par un humain** — un cron ne corrige jamais seul.

## Le projet apporte les SIENS

Les contrôles de **code** (lint, tests, analyzers, standards de style) sont **tech-spécifiques** → c'est le **projet** qui les amène et les câble, ainsi que la **revue sémantique** (sa skill de review). Ici, on ne fournit que les contrôles de **méthode**.

## Universels — sécurité + navigation (fournis)

**Sécurité — FOURNIE** dans `../hooks/` (gardes portables) : `poisoning-scan` (Unicode
invisible/bidi), `secret-scan` (clés/jetons), `destructive-guard` (commandes larges). À câbler au
bon déclencheur — table par outil dans `../hooks/README.md`.

<!-- gabarit -->
**Navigation / fraîcheur doc — FOURNIE** ici : `doc-refs-check.py` (références mortes) et
`index-check.py` (intégrité de l'index par-fichier — le projet définit racines+extensions dans
`index/index-config.json`).
<!-- /gabarit -->
Un projet adoptant garde la liberté d'avoir ses propres `manifest.py` / `doc-audit.py`, plus
riches et câblés sur son arborescence réelle — voir `SCRIPTS.md §Attention à l'homonymie`.
