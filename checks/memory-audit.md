# Audit mémoire multi-canal — recette + barème (deux niveaux)

> Le **script** `memory-audit.py` (étage 1, mécanique) ne *juge* pas — il enchaîne les
> trois contrôles d'intégrité (`feature-map-check`, `decisions-audit --tier1` — qui
> couvre déjà lui-même décisions/doc/index/backlog — et `memory-check`) et résume, sans
> dupliquer aucun des trois. Ce document porte le **barème de revue**
> (étage 2, sémantique) pour les **trois canaux** de `WORKFLOW.md §Les trois mémoires` —
> la part qu'aucun script ne peut trancher.
>
> *Équivalent, en format Claude Code, du couple skill `memory-audit` + subagent
> `memory-auditor`.*

## Quand

- **Volume** — le journal de décisions gonfle (déclencheur détaillé : `decisions-audit.md`).
- **Après une fusion de branches** — dérive possible sur les trois canaux à la fois.
- **À la demande** — « est-ce que notre mémoire tient encore ? »

**Jamais par âge / TTL seul** (« pas utilisé » ≠ « inutile », `decisions/README.md §pruning`).

## Le flux

1. **Intégrité** (mécanique) : `python3 checks/memory-audit.py --tier1` → un statut par canal.
2. **Revue sémantique, PAR CANAL** — chacun a son propre rythme, aucun besoin d'un
   passage unique sur les trois :
   - **Décision** — accumulée, donc **découpée en lots** : suivre `decisions-audit.md`
     (`decisions-audit.py --plan/--merge`, un reviewer par lot).
   - **Feature** — `FEATURE_MAP.md` reste volontairement assez petit pour être **relu en
     entier** (`WORKFLOW.md`) : pas de découpage, un seul passage.
   - **Mémoire** — ne relire que les `memory/<slug>.md` que `memory-check.py` repère
     candidates : `confidence: unverified` (`R-UNVERIFIED`) OU `confidence: verified` sans
     `ratified` (`R-VERIFIED-NOT-RATIFIED`) ; le reste (`verified` + `ratified` tracé) n'a
     rien à revoir.

## Le barème (étage 2)

### Canal Décision

Barème complet, format de sortie, contrôle de couverture → `decisions-audit.md`. Ce script
délègue entièrement ce volet — il ne le réimplémente pas.

### Canal Feature

Chaque fiche vit dans `features/<slug>.md` (un fichier par fiche, indexé par `FEATURE_MAP.md`) :
décrit-elle encore la réalité du code qu'elle cite ? Le pré-filtre mécanique s'est enrichi de
`FM-FRESH` (`feature-map-check.py` : `updated` de la fiche antérieur au dernier commit d'un
chemin cité en `**Code :**`) — l'étage 2 **traite ces fiches en priorité**, sans s'y limiter
(une fiche fraîche peut quand même avoir dérivé sémantiquement).

| Verdict | Condition | Preuve attendue |
|---|---|---|
| `PERIMEE` | le **Rôle** décrit un comportement que le code ne fait plus | `file:line` du code divergent |
| `CODE-DEPLACE` | un chemin cité existe encore mais **ailleurs** — la fiche pointe faux sans être « morte » (dead-path, lui, est mécanique — `doc-refs-check.py`) | le chemin réel actuel |
| `A-JOUR` | rien à signaler | — |

Ne signaler QUE `PERIMEE` et `CODE-DEPLACE` — `A-JOUR` n'a pas besoin d'être listé.

### Canal Mémoire (préférences)

Pour chaque `memory/<slug>.md` signalé par `memory-check.py` (`confidence: unverified` →
`R-UNVERIFIED`, `confidence: verified` sans `ratified` → `R-VERIFIED-NOT-RATIFIED`, ou
`source: external:...`) — les verdicts décrivent désormais l'**écriture de frontmatter
attendue**, pas juste un jugement en prose :

| Verdict | Condition | Preuve attendue |
|---|---|---|
| `RATIFIER` | recoupée avec le code/une source fiable, elle tient → l'agent **propose** le diff de frontmatter qui pose `confidence: verified` + `ratified: <qui>, <AAAA-MM-JJ>` | la source de recoupement |
| `REJETER` | recoupée, elle ne tient pas (obsolète, contredite, jamais vérifiée) → retrait du fichier + de sa ligne d'index, **journalisé** (raison + historique git) | pourquoi elle ne tient pas |
| `DOUTE` | non concluant en l'état | 1 phrase de raison |

**Aucune écriture sans ratification humaine** (`MEMORY.md §Provenance` : « rien n'est promu en
partagé sans passer par le cycle de vie tracé »). `RATIFIER` n'est **jamais** une
auto-application : l'agent propose le diff (`confidence: verified` + `ratified:`), c'est
l'humain qui le pose.

## Garde-fou

Le mécanisme **signale**, sur les trois canaux. Aucun élagage (suppression, fiche
réécrite, entrée promue/retirée) n'est appliqué sans **ratification humaine**. Un
`DRIFT-CODE` (canal Décision) ou une `PERIMEE` (canal Feature) se tranchent par
l'utilisateur — l'IA n'aligne jamais silencieusement la mémoire sur le code ni l'inverse.

## Emballage par outil

| | Le flux (recette) | Le barème (étage 2) |
|---|---|---|
| **Claude Code** | un **skill** (`memory-audit`) | un **subagent** (`memory-auditor`), jugement multi-canal |
| **Copilot / autre** | une instruction / commande | un **prompt de revue** (system prompt) par canal |
| **Tout outil** | le **script** `memory-audit.py` est portable tel quel (Python, sans dépendance) | ce barème, inchangé |

Cette recette est la **définition canonique** ; des **installeurs par outil** la
matérialiseront en artefacts concrets sans la réécrire. Gabarit embarqué Claude Code :
`adapters/claude-code/skills/memory-audit.md` (délègue son volet décisions au gabarit
`adapters/claude-code/skills/decisions-audit.md`).
