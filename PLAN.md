# PLAN — rendre YAMS autonome, puis formaliser la mémoire

> **Statut : plan, rien d'implémenté.** Deux étapes ordonnées — l'étape 1 (cohérence,
> déplacement de fichiers) change des chemins cités partout, elle passe **avant** l'étape 2.
> Chaque item référence les documents à modifier et les scripts à améliorer. Les choix encore
> ouverts sont marqués **[à trancher]** avec une recommandation.
>
> Origine : audit de cohérence du portage depuis le projet initial (TheUndeathCurse), session
> du 2026-07-09. Trois écarts relevés (emballage, statut du backlog, triptyque de pilotage)
> + un constat : la formalisation des entrées mémoire est inégale selon les canaux.

---

## Étape 1 — Cohérence : YAMS autonome hors du projet initial

### 1.1 Emballage — le framework EST le produit

**Problème.** `_meta/README.md` est copié verbatim du projet hôte (parle du jeu *Souvenir
d'outre-mort*, d'`Assets/Project/`, des linters du jeu). Le `README.md` racine (2 lignes) ne
pointe même pas vers `_meta/ai-workflow/`. Dans YAMS, le framework n'est pas « hors périmètre » —
il est le dépôt entier.

**Modifications :**

| Fichier | Action |
|---|---|
| `_meta/ai-workflow/**` | **[à trancher]** — recommandé : **promouvoir tout le contenu à la racine** du dépôt (`WORKFLOW.md`, `backlog/`, `decisions/`, `memory/`, `checks/`, `hooks/`, `index/`, etc.). Alternative : garder `_meta/ai-workflow/` et se contenter de READMEs corrects — plus simple mais l'emballage « méta » reste un vestige. |
| `_meta/README.md` | **Supprimer** (vestige de l'hôte). Rien de son contenu ne s'applique à YAMS. |
| `README.md` (racine) | **Réécrire** : présenter YAMS (l'orchestrateur méthodologique : boucle de travail + mémoire temporaire/long terme + contrôles), pointer `WORKFLOW.md` (le cœur), `INSTALL.md` (adopter), `SCRIPTS.md` (référence). Absorber l'actuel `_meta/ai-workflow/README.md` (placement par outil) ou le garder comme doc de déploiement séparée. |
| tous les `.md` du framework | après le déplacement : **repasser tous les chemins relatifs** cités (`../checks/`, `_meta/ai-workflow/…`) — vérification mécanique par `checks/doc-refs-check.py` une fois lancé depuis la nouvelle racine. |

**Scripts :** aucun changement de logique — vérifier que les défauts de chemins
(`decisions/INDEX.md`, `../MEMORY.md`, `index/index-config.json`) tiennent depuis la nouvelle
racine (ils sont relatifs au script, a priori OK).

### 1.2 Statut du backlog dans `WORKFLOW.md` — contradiction interne

**Problème.** Le diagramme mermaid (`WORKFLOW.md:61-66`) et la ligne 87 placent `backlog/` dans
« Apporté par LE PROJET — pas par le framework », alors que le framework le **fournit** (listé
dans `README.md:26`, échafaudé par `INSTALL.md` étape 2, contrôlé par `backlog-check.py`).
L'idée voulue — « le backlog n'est pas une *mémoire* » — dit autre chose que « le projet
l'apporte ».

**Modifications :**

| Fichier | Action |
|---|---|
| `WORKFLOW.md` (diagramme, l.61-75) | Sortir `backlog/` du sous-graphe « Apporté par LE PROJET » ; créer une case propre « TRANSITOIRE — fourni par le framework, pas une mémoire » (le `Fait`/doc d'archi durable, lui, reste bien côté projet). |
| `WORKFLOW.md` l.87 | Réécrire : le backlog est **fourni par le framework** mais n'est **pas un canal mémoire** (transitoire vs durable) — supprimer le « Même chose pour le backlog ». |

**Scripts :** aucun.

### 1.3 Triptyque de pilotage — restaurer l'« état courant »

**Problème.** Le projet initial pilote avec trois documents : le **plan** (séquenceur), l'**état
courant** (tableau de bord) et le **todo** (backlog). YAMS n'a porté que le todo ; la DoD est
passée de 5 à 4 étapes en perdant « mettre à jour l'état ». Or l'intention de YAMS est « se
souvenir **et reprendre** » — la reprise s'appuie sur l'état courant.

**Modifications :**

| Fichier | Action |
|---|---|
| `TABLEAU_DE_BORD.md` (nouveau, gabarit) | Créer : l'**état courant** en 1 page — avancement par jalon, points chauds, dernière session (date + gist). Maintenu **court** ; la vue détaillée live reste **générée** (`backlog-check.py --board`), jamais dupliquée à la main. |
| `WORKFLOW.md` | Nouvelle section « Le pilotage — plan / état / todo » : le **plan** = les groupes *jalon* de `backlog/INDEX.md` (pas de doc séparé — le jalon ordonne, c'est le séquenceur) ; l'**état** = `TABLEAU_DE_BORD.md` ; le **todo** = `backlog/INDEX.md`. Trois rôles, jamais confondus. |
| `backlog/README.md` (DoD) | Repasser à **5 étapes** : durable écrit → décision si structurel → backlog vidé → **état mis à jour (`TABLEAU_DE_BORD.md`)** → capitalisation. |
| `INSTALL.md` étape 2 | Ajouter `TABLEAU_DE_BORD.md` à l'échafaudage. |

**Scripts :**

| Script | Amélioration |
|---|---|
| `checks/backlog-check.py` | (optionnel, soft) règle « fraîcheur du tableau de bord » : si un chantier est retiré/clos et que `TABLEAU_DE_BORD.md` n'a pas bougé dans le même commit → à-confirmer. Réutiliser le motif `--stamp` pour sa ligne de date. |

### 1.4 Purger les références au projet hôte — autonomie documentaire

**Problème.** Plusieurs documents renvoient à des artefacts du projet initial que YAMS
n'embarque pas : `SCRIPTS.md:119` cite une décision de l'hôte (`D-2026-07-01-04`) introuvable
ici ; `checks/README.md`, `hooks/README.md`, `memory-audit.md`, `decisions-audit.md` et
`GABARIT.md` pointent vers `.claude/hooks/*.sh`, `.claude/skills/*`, `audit.py`, `doc-audit.py`
du dépôt hôte. Un adoptant ne peut pas suivre ces renvois.

**Modifications :**

| Fichier | Action |
|---|---|
| `SCRIPTS.md` | Supprimer la mention `D-2026-07-01-04` (l'historique du renommage n'apporte rien à un adoptant) et la note d'homonymie finale qui décrit les scripts de l'hôte — ou la réduire à une phrase générique. |
| `checks/README.md` | Les « implémentations de référence Claude Code dans le projet hôte » deviennent des exemples **embarqués** : créer `adapters/claude-code/` avec les squelettes de hooks complets (sweep `SessionStart`, hook `Stop` par check, pré-commit `--stamp`, gardes sécurité) — les blocs `sh` déjà présents dans le README y migrent en fichiers réels. Le README pointe vers `adapters/`. |
| `hooks/README.md` | Idem : la ligne « Implémentations de référence … `.claude/hooks/` » pointe vers `adapters/claude-code/`. |
| `checks/memory-audit.md`, `checks/decisions-audit.md` | Les paragraphes « Implémentation de référence Claude Code dans le projet hôte » deviennent : gabarits de skill/subagent livrés sous `adapters/claude-code/` (le barème reste la définition canonique, l'adaptateur ne fait que l'emballer). |
| `checks/GABARIT.md` | Garder la **provenance** (extrait de deux linters du projet initial — honnête et conforme à la règle de provenance) mais réécrire pour ne plus **dépendre** de leur lecture : le gabarit doit se suffire. La table « Ce que ce framework applique déjà » ne liste plus que les scripts de CE dépôt. |
| `adapters/claude-code/README.md` (nouveau) | Contenu : fragments `settings.json`, fichiers de hooks, gabarits skill/subagent pour `memory-audit`/`decisions-audit`. C'est la matérialisation concrète de la table « Câblage par outil » — et la première brique du futur `install.py`. |
| `_meta/ai-workflow/README.md` §Adapter | Renvoyer vers `adapters/` pour Claude Code ; Copilot/autre restent des tables (adaptateurs à venir). |

**Scripts :**

| Script | Amélioration |
|---|---|
| `checks/doc-refs-check.py` | Le check s'auto-applique au framework et remonte ~24 « à-confirmer » sur les chemins de **gabarit** (`<id>/`, `index-config.json` pas encore créé…). Ajouter un mécanisme d'exemption **explicite** : marqueur en ligne (ex. un chemin dans un bloc `<!-- gabarit -->…<!-- /gabarit -->` ou suffixe `*(gabarit)*` sur la ligne) ignoré par le scan. Jamais d'allowlist cachée dans le script. |

---

## Étape 2 — Mémoire : entrées uniformisées, backlog formalisé, contrôles renforcés

**Constat de départ.** La formalisation est inégale : `memory/` (frontmatter `source`/`confiance`
+ `memory-check`) > backlog (frontmatter chantier) > feature (clés textuelles regex) > décisions
(concordance fichier↔index seulement — rubriques, statut, révocation, provenance : invérifiables).

### 2.1 Un gabarit commun d'« entrée mémoire »

Il existe un gabarit pour la forme des **checks** (`checks/GABARIT.md`) — pas pour la forme des
**entrées**. Le créer, et en faire dériver chaque canal.

| Fichier | Action |
|---|---|
| `GABARIT-ENTREE.md` (nouveau) | Le méta-schéma : toute entrée mémoire = **un fichier + une ligne d'index**, frontmatter commun : `id`, `statut` (valeurs propres au canal), `source: déduite\|humain\|externe:<réf>`, `confiance: validé\|à vérifier`, `cree`, `maj` (stampé mécaniquement, jamais à la main), `liens: [ids]` (références croisées inter-canaux). Ligne d'index uniforme : `- [<id>](<chemin>) — <résumé ≤ 1 ligne>`. Le corps reste de la prose libre propre au canal. |
| `MEMORY.md`, `decisions/README.md`, `FEATURE_MAP.md`, `backlog/README.md` | Chacun déclare son canal comme **instance** du gabarit : quelles valeurs de `statut`, quel corps, quelles rubriques. Ne plus redéfinir localement ce que le gabarit porte. |

**Scripts :**

| Script | Amélioration |
|---|---|
| `checks/entrylib.py` (nouveau, lib partagée) | Parseur de frontmatter + validation du schéma commun, utilisé par `memory-check`, `decisions-check`, `backlog-check` (et `feature-map-check` selon 2.3). Supprime la duplication de regex entre checks ; un seul endroit qui définit ce qu'est une entrée valide. |

### 2.2 Canal Décision — le rattraper au niveau du canal Mémoire

| Fichier | Action |
|---|---|
| `decisions/README.md` | Format d'un `D-*.md` : ajouter le **frontmatter** (`id`, `statut: active\|révoquée\|archivée`, `remplace:`/`remplacee-par:` (ids), `source`, `confiance`, `cree`, `maj`) au-dessus des trois rubriques (Décision / Pourquoi / Invariant), qui restent la partie prose. La révocation et l'archivage cessent d'être de la pure discipline : ils deviennent des transitions de `statut` + liens, vérifiables. |
| `decisions/INDEX.md` | Sections Actives/Archivées inchangées — mais désormais **réconciliées** avec le `statut` du frontmatter (même motif que backlog `jalon:` ⟺ groupe d'INDEX). |

**Scripts :**

| Script | Amélioration |
|---|---|
| `checks/decisions-check.py` | Passer de 2 à ~7 règles : `D3` frontmatter complet et valide (via `entrylib`) ; `D4` rubriques canoniques présentes (Décision/Pourquoi/Invariant) ; `D5` `statut` ⟺ section de l'INDEX (une `archivée` n'est pas sous Actives, et réciproquement) ; `D6` graphe de révocation sain — `remplacee-par:` pointe un id existant, réciprocité avec `remplace:`, pas de cycle ; `D7` `source: externe:` sans `confiance:` = bloquant (aligné sur `R-EXT-NO-CONF` de `memory-check`). |
| `checks/decisions-audit.py` / `checks/decisions-audit.md` | Le barème étage 2 exploite le frontmatter : `ARCHIVER-4` se pré-filtre mécaniquement (`statut: révoquée` + successeur indexé), le reviewer ne juge plus que le reste. `--plan` peut prioriser par `maj` ancienne. |

### 2.3 Canal Feature — uniformiser

**[à trancher]** — deux options :

- **Recommandé : aligner sur le motif commun** — un fichier par fiche (`features/<slug>.md`,
  frontmatter du gabarit + corps Rôle/Code/Doc/Tests/Motif d'ajout), `FEATURE_MAP.md` devient
  l'index (une ligne par fiche). Uniformité totale des 4 canaux, `maj` stampable par fiche,
  granularité naturelle (« une fiche trop longue → deux fichiers »).
- **Alternative légère** : garder le fichier unique, ajouter une ligne `maj:` par fiche et durcir
  le check. Moins de churn, mais le canal reste l'exception du motif.

| Fichier | Action |
|---|---|
| `FEATURE_MAP.md` (+ `features/` si option recommandée) | Selon l'option ; dans les deux cas la fiche gagne `maj` + `liens` (ids `D-*`). |

**Scripts :**

| Script | Amélioration |
|---|---|
| `checks/feature-map-check.py` | (a) valider l'**existence** des ids `D-*` cités — aujourd'hui seul le motif regex est exigé (`FM1-durable`), pas le fichier ; (b) si option recommandée : basculer sur `entrylib` + concordance fichier↔index (même motif que `memory-check`) ; (c) fraîcheur : `maj` plus ancien que le dernier commit touchant un des chemins `Code:` cités → à-confirmer (signal de priorisation pour l'étage 2, pas un verdict). |
| `checks/backlog-check.py --stamp` | Généraliser le stamp `maj` aux fiches feature stagées (ou extraire le stamp dans `entrylib` et l'appeler des deux). |

### 2.4 Backlog — l'état d'un chantier clairement formalisé

**Exigence.** L'`ETAT.md` d'un chantier = un frontmatter + une **liste de tâches courtes**, chacune
avec son **sous-état** et soit une **référence vers un document de travail**, soit une **description
courte bornée**. Aujourd'hui le suivi « par tâche » vit en rubriques libres — invérifiable.

| Fichier | Action |
|---|---|
| `backlog/README.md` | Définir le **format canonique de ligne de tâche** dans une rubrique `## Tâches` obligatoire : `- [<état>] <libellé ≤ 15 mots>` ou `- [<état>] <libellé court> → <doc-de-travail.md>`. Sous-états : `à faire` / `en cours` / `bloqué` / `fait`. Règles : une tâche simple tient dans le libellé (plafond de mots) ; au-delà → doc de travail **dans le dossier du chantier**, référencé, et le libellé reste court. Cohérence chantier⟺tâches : chantier `en cours` ⇒ ≥ 1 tâche entamée ; toutes `fait` ⇒ chantier prêt à clore. |
| `backlog/ETAT.gabarit.md` (nouveau, ou intégré au README) | Le gabarit concret d'un `ETAT.md` : frontmatter + `## Tâches` + rubriques restantes réduites au minimum (voir 2.5). |

**Scripts :**

| Script | Amélioration |
|---|---|
| `checks/backlog-check.py` | Nouvelles règles : `E-TASK-STATE` état de tâche hors vocabulaire ; `E-TASK-LEN` libellé au-delà du plafond **sans** doc de travail référencé ; `E-TASK-REF` doc de travail cité introuvable dans le dossier du chantier ; `E-TASK-SYNC` incohérence statut chantier ⟺ états des tâches (toutes `fait` mais chantier `en cours` → signal « prêt à clore », déjà l'esprit de `--checklist`). `--state <id>` et `--board` affichent les compteurs de tâches par sous-état. |

### 2.5 Capitalisation de la doc en fin de TÂCHE — et jamais dans l'état

**Problème observé sur le projet initial.** La doc durable se capitalise souvent en fin de tâche
plutôt qu'en fin de chantier — c'est **sain** — mais elle finit alors par vivre dans l'`ETAT.md`,
qui gonfle et devient un doublon transitoire du durable.

| Fichier | Action |
|---|---|
| `WORKFLOW.md` (§boucle, étape 4) | Expliciter : « mettre à jour le durable » se fait **à la fin de chaque tâche** qui produit du savoir durable, pas seulement à la clôture du chantier. La clôture (DoD étape 1) devient un **contrôle** (« reste-t-il du durable non migré ? »), pas un gros œuvre. |
| `backlog/README.md` | Règle nouvelle : **l'`ETAT.md` ne porte jamais de contenu durable** — uniquement l'état (frontmatter + tâches) et des **références** (vers les docs de travail du chantier, et vers le durable déjà écrit). Une tâche finie qui a produit de la doc → la doc part immédiatement dans son foyer durable, la tâche passe `[fait]` avec la référence. |

**Scripts :**

| Script | Amélioration |
|---|---|
| `checks/backlog-check.py` | Garde anti-accumulation, **soft** (à-confirmer, jamais bloquant — c'est un jugement) : `ETAT.md` dépassant un plafond de lignes, ou contenant des rubriques hors canon → candidat « du durable vit dans l'état ». Le verdict ferme reste à la revue. |

### 2.6 Cycle de vie de la confiance + contrôles croisés

| Fichier | Action |
|---|---|
| `GABARIT-ENTREE.md` / `MEMORY.md` | Formaliser les **transitions** de `confiance` : `à vérifier → validé` exige `ratifie: <qui>, <date>` dans le frontmatter (la ratification humaine devient traçable, pas déclarative) ; `validé → périmé` passe par la revue étage 2 + décision utilisateur, journalisée. |
| `checks/memory-audit.md`, `checks/decisions-audit.md` | Les verdicts `RATIFIER`/`REJETER` décrivent l'écriture attendue du frontmatter (qui/quoi/où) — l'agent propose le diff, l'humain ratifie. |

**Scripts :**

| Script | Amélioration |
|---|---|
| `checks/memory-check.py` | `confiance: validé` sans `ratifie:` → à-confirmer (une validation non tracée) ; `liens:` vers un id inexistant (tout canal) → bloquant. |
| `checks/memory-audit.py` | Résumé par canal enrichi des nouveaux compteurs (tâches, ratifications manquantes, liens morts inter-canaux). |

---

## Étape 3 — Réécriture intégrale en anglais (tâche finale)

Une fois les étapes 1 et 2 stabilisées (structure et contenus figés — traduire avant serait du
travail jeté), **tout le framework passe en anglais** : YAMS s'adresse à des adoptants au-delà du
projet initial francophone.

| Périmètre | Action |
|---|---|
| Tous les `.md` du framework (`WORKFLOW.md`, `README.md`, protocoles, gabarits, barèmes, `adapters/`) | Réécrire en anglais — pas une traduction mot à mot : reformuler les concepts (chantier → *work item* ou *initiative*, jalon → *milestone*, durable/transitoire → *durable/transient*, capitalisation → *knowledge capture*…) et fixer ce **glossaire** en tête de `WORKFLOW.md` pour que tous les docs emploient les mêmes termes. |
| Scripts `checks/*.py`, `hooks/*.py`, `index/manifest.py` | Messages de sortie, aide `usage:`, commentaires et noms de règles en anglais. **Attention aux contrats** : les identifiants de règles (`R-EXT-NO-CONF`, `FM1`, `D1`…), les valeurs de frontmatter (`statut`/`confiance` → `status`/`confidence`, `à vérifier` → `unverified`…) et les marqueurs parsés par les hooks sont des **API** — les renommer implique de mettre à jour d'un même geste les docs, `entrylib.py`, les barèmes et les gabarits (un seul lot cohérent, checks verts avant/après). |
| Frontmatter des entrées (`GABARIT-ENTREE.md` et instances) | Clés et vocabulaires en anglais dès la **conception** en étape 2 si possible (moins de renommage d'API ensuite) — sinon migration ici avec script de conversion jetable. |
| `PLAN.md` | Supprimé en fin de parcours (transitoire — son contenu aura migré dans les docs durables et le backlog du framework). |

## Récapitulatif

**Documents** — modifiés : `README.md` (racine), `WORKFLOW.md`, `backlog/README.md`,
`backlog/INDEX.md`, `MEMORY.md`, `FEATURE_MAP.md`, `decisions/README.md`, `decisions/INDEX.md`,
`INSTALL.md`, `SCRIPTS.md`, `checks/README.md`, `checks/GABARIT.md`, `checks/memory-audit.md`,
`checks/decisions-audit.md`, `hooks/README.md`. Créés : `TABLEAU_DE_BORD.md`,
`GABARIT-ENTREE.md`, `backlog/ETAT.gabarit.md`, `adapters/claude-code/**`. Supprimé :
`_meta/README.md`.

**Scripts** — améliorés : `checks/backlog-check.py` (tâches, anti-accumulation, stamp élargi),
`checks/decisions-check.py` (frontmatter, statut⟺INDEX, graphe de révocation),
`checks/feature-map-check.py` (existence des `D-*`, fraîcheur, option motif commun),
`checks/memory-check.py` (ratification tracée, liens croisés), `checks/doc-refs-check.py`
(exemption gabarit), `checks/memory-audit.py` / `checks/decisions-audit.py` (exploitation du
frontmatter). Créé : `checks/entrylib.py` (lib frontmatter partagée).

**À trancher avant d'implémenter :**
1. Promotion du contenu à la racine du dépôt vs conserver `_meta/ai-workflow/` (1.1 — recommandé : racine).
2. Canal Feature : un fichier par fiche + index vs fichier unique enrichi (2.3 — recommandé : un fichier par fiche).
3. Plafond de mots d'un libellé de tâche (2.4 — proposé : 15) et plafond de lignes d'un `ETAT.md` (2.5 — à calibrer sur les chantiers réels du projet initial).

**Ordre d'exécution** : 1.1 (déménagement) → 1.2–1.4 → 2.1 (gabarit + `entrylib`) → 2.2/2.3/2.4
(canaux, parallélisables) → 2.5 → 2.6 → **3 (anglais, en dernier)**. Chaque lot ≤ 5 fichiers,
checks verts entre chaque lot.
