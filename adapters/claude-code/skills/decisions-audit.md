# Gabarit Claude Code — skill `decisions-audit` + subagent `decisions-auditor`

> Emballage Claude Code de la recette canonique **`../../../checks/decisions-audit.md`**. Ce
> gabarit ne redéfinit RIEN du barème — il dit seulement : quel script lancer, quel barème
> charger, quel format de sortie rendre. Toute évolution du flux ou du barème se fait dans
> `checks/decisions-audit.md`, jamais ici (sinon duplication qui diverge silencieusement).

## Skill `decisions-audit`

**Déclencheur** — reprendre `checks/decisions-audit.md §Quand` : volume (l'INDEX des décisions
gonfle), après une fusion de branches, ou à la demande (« audit des décisions », « est-ce que nos
décisions tiennent encore ? »).

**Étapes** (le flux complet reste `checks/decisions-audit.md §Le flux` — ceci n'en est que
l'exécution outillée) :

1. Lancer `python3 checks/decisions-audit.py` (tier1 + plan). Paramètres → `SCRIPTS.md`.
2. Charger le barème étage 2 : `checks/decisions-audit.md §Le barème` (verdicts, format de
   sortie, garde-fou).
3. Pour chaque lot renvoyé par `--plan` (offset/limit), lancer un subagent `decisions-auditor`
   (ci-dessous) sur ce lot.
4. Agréger : `python3 checks/decisions-audit.py --merge <sorties-des-lots…>` — contrôle de
   couverture (chaque décision auditée exactement 1×).
5. Restituer le rapport agrégé à l'utilisateur. Ne rien élaguer/archiver sans ratification
   humaine (`checks/decisions-audit.md §Garde-fou`).

## Subagent `decisions-auditor`

**Rôle** — un reviewer par lot. Recoupe chaque décision du lot avec le **code réel**
(retrieve-then-verify, jamais conclure sans preuve grep/lecture) et rend le format strict défini
par `checks/decisions-audit.md §Le barème` :

```
D-AAAA-MM-JJ-NN | VERDICT | gist ≤8 mots | preuve | confiance:haute|moyenne|basse
```

puis, en dernière ligne : `GARDÉES: <n> — <ids sans problème>`.

**Outils** — lecture seule (recherche + lecture de fichiers, `grep`/`glob`). Ne corrige, ne
supprime, n'archive rien.

**Contrat de sortie** — strictement le format ci-dessus, rien avant, rien après : c'est ce que
`decisions-audit.py --merge` parse tel quel pour le contrôle de couverture.
