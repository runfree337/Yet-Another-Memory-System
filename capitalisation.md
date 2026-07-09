# Capitalisation — router un apprentissage de méthode

> Complète la §Capitalisation de `WORKFLOW.md`. À la clôture d'un chantier : *ce travail a-t-il révélé un apprentissage de **méthode** réutilisable ?*
> **La logique (étapes 1–2) est agnostique** ; seul le **dernier pas** (étape 3 : quel mécanisme concret) dépend de l'outil → c'est le même adaptateur que le placement du framework (`README.md`).
> Périmètre = apprentissage de **méthode / process** (comment on travaille). L'apprentissage de *contenu* (ce qu'est le projet) va déjà dans sa doc d'archi.

## 1. Faut-il seulement le capter ? (le gate)

Ne pas outiller au ressenti — **un déclencheur vérifiable suffit** :

- **Répétition** : même procédure refaite **≥ 3×**.
- **Tâtonnement** : même commande corrigée **≥ 2×** avant de marcher → capter l'invocation juste.
- **Procédure longue déterministe** : **≥ 5 étapes** reproductibles (même entrée → même sortie).
- **Invariant vérifié à la main** : une règle contrôlée manuellement qui doit *toujours* tenir.
- **Régression** : une erreur déjà vue revient.
- **Étape de process oubliée** puis rattrapée.

**Anti-déclencheurs (ne PAS outiller)** : vrai one-off · la vérification exige un **jugement** (→ pas de script, sinon faux positifs) · coût de maintenance > gain cumulé. La réponse **« rien à capitaliser »** est légitime — mais la question est *posée*, jamais sautée par défaut.

## 2. Quelle FONCTION ? (agnostique)

Classer l'apprentissage par ce qu'il doit *devenir* — une **fonction**, pas un outil :

| L'apprentissage est… | → Fonction durable |
|---|---|
| une règle/préférence normative, courte | **règle partagée** |
| un invariant **mécanique**, vérifiable sans jugement | **contrôle déterministe** (zéro faux positif) |
| un jugement **sémantique** récurrent qu'aucun script ne tranche | **rôle de revue / délégation** |
| une procédure/recette réutilisable, non mécanisable | **recette documentée** |
| un invariant à ne jamais re-casser | **test de non-régression** |
| un choix structurel | **décision** (`decisions/`) |
| perso, machine-local | **mémoire personnelle** (hors dépôt) |
| un trou dans la méthode elle-même | **améliorer le protocole concerné** |

> Plusieurs fonctions à la fois sont possibles (ex. un contrôle déterministe **+** la règle qu'il protège). Le foyer le plus léger qui capte vraiment l'apprentissage gagne.

## 3. Mapper la fonction au mécanisme (le SEUL pas tool-spécifique)

| Fonction | Claude Code | GitHub Copilot | Autre agent |
|---|---|---|---|
| recette documentée | skill | prompt file | doc / fichier de contexte |
| contrôle déterministe | script + hook (auto) | script + job CI | script + ton ordonnanceur |
| rôle de revue / délégation | subagent | chat mode | rôle / prompt dédié |
| règle partagée | `CLAUDE.md` / `.claude/rules/` | `copilot-instructions` / `.github/instructions` | system prompt / doc partagée |
| test de non-régression | suite de tests du projet | idem | idem |
| mémoire personnelle | auto-memory | custom instructions perso | la mémoire de ton outil |

> La logique (**1 + 2**) ne change **pas** d'un outil à l'autre. Seule la **colonne** du tableau **3** change. Remplir/adapter cette colonne pour ton outil = la même opération que choisir où déposer le framework.
