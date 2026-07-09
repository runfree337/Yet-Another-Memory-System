# Audit du journal de décisions — recette + barème (deux niveaux)

> Le **script** `decisions-audit.py` (étage 1, mécanique) ne *juge* pas. Ce document porte la
> **recette d'orchestration** et le **barème de revue** (étage 2, sémantique) — la part qu'aucun
> script ne peut trancher. Tout est **agnostique** : chaque outil l'emballe à sa façon (voir
> « Emballage par outil »).
>
> *Équivalent, en format Claude Code, du couple skill `decisions-audit` + subagent
> `decisions-auditor`.* Portée = le journal de décisions uniquement. Pour l'audit multi-canal
> (feature + décision + préférences), voir `memory-audit.md`, qui délègue son volet décisions
> à cette recette.

## Quand

Déclencheur **« Volume »** du modèle de pruning (`../decisions/README.md`) : l'INDEX des décisions
gonfle (proxy : il approche ~2× l'effectif actif), ou après une fusion de branches, ou sur demande.
**Jamais par âge / TTL seul** (« pas utilisé » ≠ « inutile »).

## Le flux

1. **Intégrité + plan** (mécanique) : `python3 checks/decisions-audit.py` → enchaîne les contrôles
   d'intégrité (`--tier1`) puis **découpe l'INDEX en lots équilibrés** (`--plan` : offset/limit/ids
   par lot). Supprime le découpage manuel.
2. **Revue par lot** (sémantique) : **un reviewer par lot** applique le barème ci-dessous — recoupe
   chaque décision avec le **code réel** (retrieve-then-verify), sort le format strict.
3. **Agrégation** : `python3 checks/decisions-audit.py --merge <sorties…>` → rapport classé +
   **contrôle de couverture** (chaque décision auditée **exactement une fois** — rien sauté en silence).

## Le barème (étage 2)

Pour chaque décision : recouper avec le dépôt (**jamais conclure sans preuve grep/lecture**), puis
classer — n'émettre **que** les entrées à problème :

| Verdict | Condition | Preuve |
|---|---|---|
| `ARCHIVER-1` | sujet code **disparu** du dépôt | `grep vide: <terme>` |
| `ARCHIVER-4` | entrée révoquée/remplacée dont l'invariant vit **entièrement** dans le successeur | l'id successeur |
| `REDONDANTE` | invariant **déjà porté** par une autorité vivante (test, doc d'archi, fiche feature) | la référence |
| `DRIFT-CODE` | la décision dit X, le **code fait Y** — **l'utilisateur tranche**, aucun correctif proposé | la divergence |
| `CONFLIT` | contredit une autre décision **sans** lien de révocation | l'autre id |
| `DOUTE` | suspect, non concluant | la raison |

**Discernement** (sinon : faux positifs) : une décision de **process** n'a jamais de « sujet
disparu » ; une **suppression actée** (`grep` vide *conforme* à la décision) n'est pas un problème ;
une archi **à bâtir** (spec) que le code n'a pas encore n'est pas un drift. Erre vers le signalement
(`DOUTE` plutôt que silence), mais ne crie pas au loup.

**Format de sortie** (l'agrégateur le lit) — une ligne par problème, rien avant :

```
D-AAAA-MM-JJ-NN | VERDICT | gist ≤8 mots | preuve | confiance:haute|moyenne|basse
```

puis, en dernière ligne (sert au contrôle de couverture) : `GARDÉES: <n> — <ids sans problème>`.

## Garde-fou

Le mécanisme **signale**. Aucun élagage (suppression, archivage, tombstone) ni alignement
**code↔doc** n'est appliqué sans **ratification humaine** ; un `DRIFT-CODE` / `CONFLIT` se tranche
par l'utilisateur ; tout élagage retenu reste **journalisé** (successeur + raison + historique).

## Emballage par outil

La recette est agnostique ; chaque outil la **package** à sa main (même logique que la table de
`capitalisation.md`) :

| | Le flux (recette) | Le barème (étage 2) |
|---|---|---|
| **Claude Code** | un **skill** (`decisions-audit`) | un **subagent** (`decisions-auditor`), un par lot |
| **Copilot / autre** | une instruction / commande | un **prompt de revue** (system prompt) par lot |
| **Tout outil** | le **script** `decisions-audit.py` est portable tel quel (Python, sans dépendance) | ce barème, inchangé |

Cette recette est la **définition canonique** ; des **installeurs par outil** (Claude Code, Copilot —
à venir) la matérialiseront en artefacts concrets (skill, subagent, hook) sans la réécrire.
Gabarit embarqué Claude Code : `adapters/claude-code/skills/decisions-audit.md`.
