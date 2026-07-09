# Gabarit d'un contrôle déterministe — comment en écrire un nouveau

> **Pour qui.** Ce fichier ne fournit **pas** un script — c'est le **patron** que suit chaque
> contrôle mécanique zéro faux positif de ce framework, à réutiliser quand **le projet hôte**
> écrit son propre linter tech-spécifique (le sien : lint, standards de code, analyzers — hors
> périmètre du framework, cf. `checks/README.md §Le projet apporte les SIENS`), ou quand ce
> framework lui-même gagne un nouveau check agnostique.
>
> **Provenance :** extrait par observation du code réel de deux linters du projet initial dont
> YAMS a été extrait — un linter de standards de code C#/Unity (nommé `audit.py` côté projet) et
> un linter de fraîcheur de doc (nommé `doc-audit.py` côté projet) — qui convergent
> indépendamment vers la même forme. Déduit par l'IA, pas encore ratifié humainement comme règle
> d'équipe ; à recouper avant de le traiter comme un fait acquis (le projet d'origine n'est pas
> embarqué dans ce dépôt — ces deux scripts n'y sont pas consultables).

## Pourquoi un gabarit

Chaque check de ce dossier (et les linters tech-spécifiques du projet hôte) répond à la même
question : *« cette dérive est-elle prouvée, ou seulement probable ? »* — et devrait toujours
répondre avec la **même forme**, pour que n'importe quel outil (hook, CI, humain) puisse
brancher n'importe quel check sans apprendre une convention par script. Écrire un nouveau
check sans repartir de ce gabarit, c'est reproduire à la main un choix déjà tranché 2 fois de
façon identique dans le projet de référence.

## Les 5 pièces

### 1. Deux niveaux de verdict, jamais plus

```python
BLOQUANT = "BLOQUANT-AUTO"   # zéro faux positif PROUVÉ sur le dépôt — verdict ferme
CONFIRMER = "À-CONFIRMER"    # pré-filtre de localisation — l'agent ou l'humain tranche
```

`BLOQUANT-AUTO` : la règle ne peut **pas** se tromper (ex. un chemin cité qui a existé puis
disparu — l'historique git le prouve). `À-CONFIRMER` : la règle **repère un candidat plausible**
mais ne peut pas exclure le faux positif seule (ex. un chemin jamais créé — peut-être une
coquille, peut-être un planifié légitime). Ne jamais inventer un troisième niveau : le script
**constate**, il ne juge pas — le jugement fin est le travail de l'étage 2 (agent/revue).

### 2. Le `Finding`, une struct minimale

```python
from collections import namedtuple
Finding = namedtuple("Finding", "severity rule path line msg")
```

Toujours ces 5 champs, dans cet ordre. `rule` est un identifiant stable (`R-DEAD-PATH`,
`FM1`…) — grep-able, cité dans la doc du check, stable d'une version à l'autre du script (les
docs et les tests s'y référencent).

### 3. Les règles sont des fonctions PURES

```python
def rule_xxx(path, lines, text) -> list[Finding]:
    ...
```

Aucun effet de bord, aucun I/O au-delà de la lecture déjà faite. Ça les rend **testables en
isolation** (`tests/` peut appeler `rule_xxx` directement sans passer par `main`) et
**composables** (`RULES = [rule_a, rule_b, ...]`, une boucle simple les enchaîne).

### 4. `collect()` — rassembler les cibles, git-aware

```python
def collect(targets, diff, staged):
    raw = []
    if diff:   raw += git_diff_names(staged=False)   # modifiés, non stagés
    if staged: raw += git_diff_names(staged=True)    # stagés
    for t in targets:
        raw += walk(t) if os.path.isdir(t) else [t]
    return dedupe_existing_files(raw, filtered_by=EXTENSIONS_OR_SUFFIX)
```

Trois façons d'alimenter un check, **jamais mutuellement exclusives** : chemins explicites,
`--diff` (ce qu'on vient de changer), `--staged` (ce qui va être commité). Filtrer par extension/
suffixe auditable et dédupliquer avant d'auditer — un fichier ne s'audite jamais deux fois même
s'il apparaît par deux voies à la fois.

### 5. `main(argv)` — la même interface pour tous

```python
def main(argv):
    as_json = "--json" in argv
    diff = "--diff" in argv
    staged = "--staged" in argv
    targets = [a for a in argv if not a.startswith("--")]
    if not (targets or diff or staged):
        print("usage: <script>.py <chemin...> | --diff | --staged [--json]", file=sys.stderr)
        return 0

    findings = [f for path in collect(targets, diff, staged) for f in audit_file(path)]
    bloq = [f for f in findings if f.severity == BLOQUANT]
    conf = [f for f in findings if f.severity == CONFIRMER]

    if as_json:
        print(json.dumps([f._asdict() for f in findings], ensure_ascii=False, indent=2))
    else:
        for f in sorted(findings, key=lambda f: (f.severity != BLOQUANT, f.path, f.line)):
            print(f"{f.severity:14} {f.path}:{f.line}  {f.rule}  {f.msg}")
        print(f"\n— {len(findings)} finding(s) : {len(bloq)} bloquant-auto, {len(conf)} à-confirmer")

    return 2 if bloq else (1 if conf else 0)
```

**Code retour, la convention à ne jamais rompre** — la même dans les 6 checks de ce dossier ET
dans les linters tech-spécifiques du projet hôte : `0` propre, `1` seulement des À-CONFIRMER,
`2` au moins un BLOQUANT. C'est ce qui permet à `checks/README.md §À câbler` de gater n'importe
quel check sur son seul code retour, sans connaître sa sémantique interne.

## Ce que ce framework applique déjà, ou pas

*(Les deux linters cités en provenance ci-dessus ne sont pas embarqués dans ce dépôt — ils ont
servi de référence de départ pour dégager le gabarit, pas de base de comparaison ligne à ligne.)*

| Script | Finding (namedtuple) | `collect` git-aware (`--diff`+`--staged`) | `--json` | Conforme au gabarit |
|---|---|---|---|---|
| `checks/doc-refs-check.py` (ce framework) | tuple simple | `--staged` seul, pas `--diff` | non | **dilué** — à réaligner si l'occasion se présente |
| `hooks/poisoning-scan.py`, `hooks/secret-scan.py` | tuple simple | `--staged` seul | non | dilué — mais gardes courtes, la simplicité prime ici |
| `checks/memory-check.py` (ce framework) | ✅ | n/a (compare toujours l'index au dossier en entier, même motif que `decisions-check.py` — pas de sous-ensemble à cibler) | ✅ | **conforme** — premier check écrit à partir de ce gabarit, pas redécouvert |

**Le mot d'ordre n'est pas de tout réaligner rétroactivement** — un script qui marche et dont la
dérive n'a jamais coûté cher ne mérite pas un refacto au nom de la seule cohérence stylistique.
Ce gabarit sert le **prochain** check à écrire (ce framework ou le projet hôte) : lui, part de
la forme complète dès le premier jet, plutôt que de redécouvrir empiriquement les mêmes 5 pièces.
`memory-check.py` en est la première preuve concrète.
