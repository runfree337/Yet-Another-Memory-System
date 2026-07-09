# YAMS — Yet Another Memory System

Un **orchestrateur méthodologique** pour travailler avec une IA sur un projet logiciel.
**Agnostique** à l'outil (Claude Code, Copilot, autre) et à la techno/architecture. Le projet
apporte son archi, ses outils de code, sa doc et sa revue ; YAMS apporte **comment travailler et
mémoriser** — il s'y *branche*, il ne les remplace pas.

## L'idée

YAMS fournit cinq briques qui tiennent ensemble :

- une **boucle de travail** — se repérer et vérifier avant de coder, développer selon les
  standards du projet, valider, mettre à jour le durable, capitaliser, rendre la main ;
- une **mémoire temporaire** (`backlog/`) — le travail pas-encore-fait, distinct de tout canal
  mémoire ;
- une **mémoire long terme** en trois canaux — **feature** (`FEATURE_MAP.md`, où est le code),
  **décision** (`decisions/`, le pourquoi d'un choix structurel) et **préférences**
  (`MEMORY.md`, règles et apprentissages, partagés vs personnels) ;
- une **navigation** (`index/`) — retrouver un fichier sans tout lire ;
- des **contrôles déterministes** (`checks/`) qui gardent l'ensemble cohérent — orphelins,
  pointeurs morts, statuts incohérents — et signalent sans jamais corriger à la place de l'humain.

Le détail de la boucle et l'articulation entre ces briques : **[`WORKFLOW.md`](WORKFLOW.md)** —
c'est le cœur du framework.

## Déposer selon l'outil (le cœur est le même)

`WORKFLOW.md` est du Markdown brut qu'un agent lit comme contexte/instructions. Seul le
**placement** change :

| Outil | Où l'accrocher |
|---|---|
| **Claude Code** | `CLAUDE.md` (ou une skill `.claude/skills/…`) qui inclut/pointe `WORKFLOW.md` |
| **GitHub Copilot** | `.github/copilot-instructions.md` + `AGENTS.md` qui pointent `WORKFLOW.md` |
| **Autre agent** | system prompt / fichier de contexte qui inclut `WORKFLOW.md` |

**Adapter** = renvoyer vers la doc et les outils **du projet** partout où le process dit « les
standards du projet », et brancher la clôture sur le rituel existant (ex. la skill de review).

> **Adopter dans un projet → [`INSTALL.md`](INSTALL.md)** : le chemin d'adoption (échafaudage,
> config d'index, **câblage des checks là où l'utilisateur veut**, trigger de l'audit sémantique).
> Principe : *détecter + signaler, l'utilisateur décide quand les checks tournent*. L'`install.py`
> interactif reste à bâtir ; `INSTALL.md` en tient la spec et sert de guide manuel d'ici là.

## Contenu

- `WORKFLOW.md` — la boucle + les principes (**le cœur**).
- `backlog/` — le **travail en cours** (le todo + la DoD de clôture).
- `FEATURE_MAP.md` — mémoire « feature » (gabarit).
- `decisions/` — mémoire « décision » (protocole + INDEX).
- `MEMORY.md` — mémoire « préférences / apprentissages » (partagé vs perso).
- `index/INDEX.md` — navigation (gabarit) ; `index/manifest.py` maintient le détail par-fichier
  en écriture (`set`/`rm`/`get`/`stamp`).
- `checks/` — **contrôles déterministes** du process (intégrité backlog / décisions / index…) à
  câbler en hook ou CI.
- `hooks/` — **gardes universelles** (sécurité : secrets, empoisonnement, commandes
  destructrices), portables.
- `SCRIPTS.md` — **référence** de chaque script de `checks/`, `hooks/` et `index/` : intention +
  paramétrage + codes de sortie.
- `capitalisation.md` — routage agnostique d'un apprentissage de méthode (gate « faut-il
  outiller ? » + fonction → mécanisme par outil).

## Amender

C'est une **graine**. Le projet et l'utilisateur ajustent : placement, conventions, rôles de
délégation, branchement sur la revue/clôture existante. Le process est fait pour être
**modifié**, pas subi.
