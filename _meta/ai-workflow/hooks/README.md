# `hooks/` — gardes universelles (portables) + câblage par outil

> Deuxième famille de contrôles, à côté de `checks/`. Un **hook** = une **garde** (logique
> portable, ici en Python stdlib) **+** un **point de déclenchement** (mécanisme spécifique à
> l'outil). La garde vit ici, **canonique** ; un **installeur par outil** la câble au bon
> déclencheur. Aucune ne corrige : elles **signalent** / demandent confirmation.

## Les gardes fournies (universelles, agnostiques)

| Garde | Ce qu'elle attrape | Verdict |
|---|---|---|
| `poisoning-scan.py` | Unicode **invisible/bidi** dans les fichiers d'instruction & de mémoire (vecteur « TrapDoor ») | exit 2 = bloquer |
| `secret-scan.py` | **clés/jetons** commités (18 motifs) — Anthropic, AWS, GitHub, Slack, Stripe… | exit 2 = bloquer |
| `destructive-guard.py` | commandes shell **destructrices** larges (`find -delete`, `-exec rm`) | « ask » (confirmer) |

Chacune est **portable** (stdlib, sans dépendance) et offre deux entrées :
- **universelle** : `--staged` (contenu git stagé — pré-commit / CI) ou des chemins en argument ;
- **adaptateur Claude Code** : `--stdin-json` (lit le JSON `tool_name`/`tool_input` du hook).

```bash
python3 hooks/poisoning-scan.py --staged
python3 hooks/secret-scan.py --staged
python3 hooks/destructive-guard.py --command "find . -name '*.tmp' -delete"
```

## Câblage par outil — ce que l'installeur matérialise

Le **déclencheur** est spécifique à l'outil ; la garde, non. Table de matérialisation :

| Garde | Quand | Claude Code | Git / CI |
|---|---|---|---|
| poisoning-scan | début de session · avant écriture d'un fichier d'instruction | hook `SessionStart` / `PreToolUse(Write\|Edit)` → `--stdin-json` | `pre-commit` → `--staged` |
| secret-scan | avant un commit · avant écriture | hook `PreToolUse(Bash\|Write\|Edit)` → `--stdin-json` | `pre-commit` → `--staged` |
| destructive-guard | avant une commande shell | hook `PreToolUse(Bash)` → `--stdin-json` (décision « ask ») | `pre-commit` (exit 2 = bloquer) |

> Les **contrôles de méthode** de `checks/` (`backlog-check`, `decisions-check`, `memory-audit`)
> se câblent aussi en hook — typiquement `Stop` (fin de tâche) / `SessionStart` (dérive
> post-fusion) côté Claude Code, ou un job CI. Voir `../checks/README.md`.

## Ce qui N'est PAS ici — le projet l'apporte

Les gardes/contrôles **tech-spécifiques** (lint, tests, analyzers, standards de style du
langage hôte) sont au **projet**, pas au process. Ici : seulement les gardes **universelles**
(sécurité, intégrité) que toute équipe veut, quel que soit le langage.

## Modèle d'installeur (à venir)

Un installeur par outil (Claude Code, Copilot…) lira ce dossier + `../checks/` et **générera**
les artefacts concrets — fichiers de hook, entrées de config (`settings.json`,
`.pre-commit-config.yaml`, workflow CI…) — en pointant chaque garde sur son déclencheur via la
table ci-dessus. La logique n'est **jamais** réécrite : seule la glue de câblage diffère.
Implémentations de référence Claude Code dans le projet hôte : `.claude/hooks/`.
