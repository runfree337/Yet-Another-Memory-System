# Framework de process IA — déploiement

Un **process de travail avec une IA**, **agnostique** à l'outil (Claude Code, Copilot, autre) et à la techno/architecture. Dérivé de la méthode The Undeath Curse. Cœur : **`WORKFLOW.md`**.

## L'idée

On fournit **comment travailler et mémoriser** : la boucle de travail + les mémoires (feature / décision / préférences) + la navigation + la capitalisation. Le **projet** fournit son archi, ses outils de code, sa doc et sa revue. Le process s'y *branche*, il ne les apporte pas.

## Déposer selon l'outil (le cœur est le même)

`WORKFLOW.md` est du Markdown brut qu'un agent lit comme contexte/instructions. Seul le **placement** change :

| Outil | Où l'accrocher |
|---|---|
| **Claude Code** | `CLAUDE.md` (ou une skill `.claude/skills/…`) qui inclut/pointe `WORKFLOW.md` |
| **GitHub Copilot** | `.github/copilot-instructions.md` + `AGENTS.md` qui pointent `WORKFLOW.md` |
| **Autre agent** | system prompt / fichier de contexte qui inclut `WORKFLOW.md` |

**Adapter** = renvoyer vers la doc et les outils **du projet** partout où le process dit « les standards du projet », et brancher la clôture sur le rituel existant (ex. la skill de review).

> **Adopter dans un projet → [`INSTALL.md`](INSTALL.md)** : le chemin d'adoption (échafaudage, config d'index, **câblage des checks là où l'utilisateur veut**, trigger de l'audit sémantique). Principe : *détecter + signaler, l'utilisateur décide quand les checks tournent*. L'`install.py` interactif reste à bâtir ; `INSTALL.md` en tient la spec et sert de guide manuel d'ici là.

## Contenu

- `WORKFLOW.md` — la boucle + les principes (**le cœur**).
- `backlog/` — le **travail en cours** (le todo + la DoD de clôture).
- `FEATURE_MAP.md` — mémoire « feature » (gabarit).
- `decisions/` — mémoire « décision » (protocole + INDEX).
- `MEMORY.md` — mémoire « préférences / apprentissages » (partagé vs perso).
- `index/INDEX.md` — navigation (gabarit) ; `index/manifest.py` maintient le détail par-fichier en écriture (`set`/`rm`/`get`/`stamp`).
- `checks/` — **contrôles déterministes** du process (intégrité backlog / décisions / index…) à câbler en hook ou CI.
- `hooks/` — **gardes universelles** (sécurité : secrets, empoisonnement, commandes destructrices), portables.
- `SCRIPTS.md` — **référence** de chaque script de `checks/`, `hooks/` et `index/` : intention + paramétrage + codes de sortie.
- `capitalisation.md` — routage agnostique d'un apprentissage de méthode (gate « faut-il outiller ? » + fonction → mécanisme par outil).

## Amender

C'est une **graine**. Le projet et l'utilisateur ajustent : placement, conventions, rôles de délégation, branchement sur la revue/clôture existante. Le process est fait pour être **modifié**, pas subi.
