# `adapters/claude-code/` — matérialisation Claude Code du câblage

> **Rôle.** `checks/README.md` et `hooks/README.md` décrivent le câblage sous forme de **tables**
> (quelle garde, quel déclencheur, quel outil) et de squelettes `sh` illustratifs — agnostiques par
> construction, pour rester valables hors Claude Code. Ce dossier est la **matérialisation
> concrète** de ces tables pour **Claude Code** : des fichiers de hook réels, exécutables, plus un
> fragment `settings.json` qui les câble. C'est la **première brique** du futur `install.py`
> (`INSTALL.md §Forme cible`) : quand l'installeur détectera Claude Code comme hôte, il copiera ce
> dossier et proposera ce fragment plutôt que de générer la glu à la volée.
>
> Rien ici ne réimplémente une garde ou un check — chaque script de ce dossier ne fait
> qu'**appeler** un script de `../../checks/` ou `../../hooks/` avec les bons arguments, au bon
> déclencheur. La logique reste **canonique** dans `checks/`/`hooks/` ; ici, seule la glu.

## Inventaire

| Fichier | Émballe | Déclencheur Claude Code |
|---|---|---|
| `hooks/session-start-sweep.sh` | `checks/*.py` (6 checks structurels), agrégés | `SessionStart` |
| `hooks/stop-check.sh <nom-du-check>` | un `checks/<nom-du-check>.py`, en détail | `Stop` (un hook par check voulu) |
| `hooks/pre-commit-stamp.sh` | `checks/backlog-check.py --stamp --staged` | `PreToolUse(Bash)`, avant `git commit` |
| `hooks/security-guards.sh` | `hooks/poisoning-scan.py`, `hooks/secret-scan.py`, `hooks/destructive-guard.py` | `PreToolUse(Write\|Edit\|Bash)` |
| `skills/decisions-audit.md` | recette `checks/decisions-audit.md` | skill + subagent (à la demande / volume) |
| `skills/memory-audit.md` | recette `checks/memory-audit.md` | skill + subagent (à la demande / volume) |

Tous les `.sh` sont **muets sur succès**, sauf `security-guards.sh` (bloque avec un message sur
`exit 2`, comme le prescrivent les gardes qu'il appelle) et `pre-commit-stamp.sh` (n'écrit jamais
bloquant — cf. `checks/README.md §Câblage pré-commit`). Chaque script détecte `python3`/`python` et
résout la racine du dépôt via `$CLAUDE_PROJECT_DIR` (fourni par Claude Code) ou, à défaut,
`git rev-parse --show-toplevel` — aucun chemin absolu codé en dur.

## Fragment `settings.json`

<!-- gabarit -->
À fusionner dans `.claude/settings.json` (ou `.claude/settings.local.json`) du projet qui adopte
le framework — chemins **côté projet adoptant**, pas dans ce dépôt (YAMS n'est pas lui-même
consommateur de Claude Code).
<!-- /gabarit -->

Comme partout dans ce framework (`INSTALL.md §Principe directeur`) : ceci est une
**proposition**, pas un câblage imposé — chaque bloc peut être adopté séparément.

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/session-start-sweep.sh\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/stop-check.sh\" index-check"
          },
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/stop-check.sh\" backlog-check"
          },
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/stop-check.sh\" decisions-check"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/security-guards.sh\""
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/security-guards.sh\""
          },
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/adapters/claude-code/hooks/pre-commit-stamp.sh\""
          }
        ]
      }
    ]
  }
}
```

**Notes de lecture :**
- `Stop` liste 3 checks en exemple (`index-check`, `backlog-check`, `decisions-check`) — un hook
  de plus par check qu'on veut voir rappelé en détail avant la fin de session ; le sweep
  `SessionStart` couvre déjà les 6 en agrégé. Ajouter `memory-check`/`feature-map-check`/
  `doc-refs-check` de la même façon si voulu.
- `PreToolUse(Bash)` porte **deux** hooks : `security-guards.sh` (secret-scan + destructive-guard,
  chacun lit `tool_name`/`tool_input` sur son propre `--stdin-json`) et `pre-commit-stamp.sh`
  (n'agit que si la commande contient `git commit`, sinon no-op immédiat). Les deux reçoivent le
  même JSON sur stdin, indépendamment.
- L'audit sémantique (`skills/decisions-audit.md`, `skills/memory-audit.md`) n'apparaît **jamais**
  dans `settings.json` — ce n'est pas un hook, cf. `checks/README.md §Sémantique — agent,
  mémoire↔code`. Il se déclenche par skill (à la demande) ou par la boucle rapport du cron OS
  (`INSTALL.md étape 5`).

## Gabarits skill/subagent

`skills/decisions-audit.md` et `skills/memory-audit.md` ne sont **pas** des scripts — ce sont des
gabarits texte au format skill/subagent Claude Code, qui **pointent** vers le barème canonique
(`checks/decisions-audit.md`, `checks/memory-audit.md`) sans jamais le dupliquer : ils précisent
seulement quel script lancer, quel barème charger, quel format de sortie rendre. Adapter au format
concret d'un skill/subagent Claude Code (frontmatter, nom de fichier sous `.claude/skills/` /
`.claude/agents/`) relève de l'installeur ou d'une copie manuelle — le contenu métier ne change
pas.
