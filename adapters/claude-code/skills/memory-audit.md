# Gabarit Claude Code — skill `memory-audit` + subagent `memory-auditor`

> Emballage Claude Code de la recette canonique **`../../../checks/memory-audit.md`**. Ce gabarit
> ne redéfinit RIEN du barème multi-canal — il dit seulement : quel script lancer, quel barème
> charger, quel format de sortie rendre. Toute évolution du flux ou du barème se fait dans
> `checks/memory-audit.md`, jamais ici. Le volet **Décision** délègue entièrement au gabarit
> `decisions-audit.md` de ce même dossier — pas de deuxième définition.

## Skill `memory-audit`

**Déclencheur** — reprendre `checks/memory-audit.md §Quand` : volume (canal Décision), après une
fusion de branches, ou à la demande (« est-ce que notre mémoire tient encore ? »).

**Étapes** (le flux complet reste `checks/memory-audit.md §Le flux`) :

1. Intégrité : `python3 checks/memory-audit.py --tier1` → un statut par canal (Feature, Décision,
   Mémoire).
2. Revue sémantique, **par canal**, chacun à son rythme :
   - **Décision** — accumulée, découpée en lots → déléguer entièrement au skill
     `decisions-audit.md` de ce dossier (`decisions-audit.py --plan/--merge`).
   - **Feature** — `FEATURE_MAP.md` relu en un seul passage (petit par construction) : lancer le
     subagent `memory-auditor` (ci-dessous) en mode Feature.
   - **Mémoire** — ne relire que les `memory/<slug>.md` signalés `confiance: à vérifier` par
     `memory-check.py` : lancer le subagent `memory-auditor` en mode Mémoire.
3. Restituer le rapport par canal. Ne rien élaguer/promouvoir sans ratification humaine
   (`checks/memory-audit.md §Garde-fou`).

## Subagent `memory-auditor`

**Rôle** — jugement sémantique sur les canaux Feature et Mémoire (le canal Décision reste celui
du subagent `decisions-auditor`, jamais réimplémenté ici). Applique le barème étage 2 de
`checks/memory-audit.md §Le barème` :

- **Feature** : pour chaque fiche de `FEATURE_MAP.md`, verdict `PERIMEE` / `CODE-DEPLACE` /
  `A-JOUR` (ne signaler que les deux premiers) — preuve = `file:line` du code divergent, ou le
  chemin réel actuel.
- **Mémoire** : pour chaque `memory/<slug>.md` signalé, verdict `RATIFIER` / `REJETER` / `DOUTE`
  — preuve = la source de recoupement, ou la raison du rejet/doute.

**Outils** — lecture seule (recherche + lecture de fichiers). Ne corrige, ne supprime, ne
réécrit rien — propose, l'utilisateur ratifie (**aucune** promotion `confiance: validé` sans
ratification humaine, `../../../MEMORY.md §Provenance`).

**Contrat de sortie** — une entrée par problème signalé, format du barème du canal concerné ;
`A-JOUR` n'a pas besoin d'être listé.
