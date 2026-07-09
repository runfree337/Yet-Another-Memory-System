# Carte des features — mémoire « feature »

> Routeur **« feature → comprendre le sujet : ce qu'elle fait, le code à voir, la doc d'archi »**. Quand une tâche touche une feature listée ici, **lire sa fiche avant de chercher**. Mettre la fiche à jour **au même moment que le code** — une fiche qui ment est pire qu'absente.
> **Référence DURABLE uniquement** : doc d'archi/spec + code + décisions. **Jamais** un doc transitoire (backlog, spec/plan en cours) — le « planifié » vit au backlog. Une fiche dit ce qui *existe*.
> Une fiche ≈ « un seul sujet qu'on comprend d'un coup ». Trop longue → probablement deux features (test **sémantique**, pas un simple compte de lignes).

---

## <Feature> — <sous-titre> *(gabarit)*

**Rôle :** <ce que la feature fait, en 1 phrase — pour comprendre le sujet> *(cœur)*
**Code :** <les fichiers clés à regarder, regroupés par rôle du projet> *(cœur)*
**Doc (durable) :** <renvoi vers la doc d'archi/spec DURABLE du projet — jamais transitoire> *(cœur)*
**Tests :** <…>
**Décisions liées :** <ids dans `decisions/`>
**Motif d'ajout :** <recette de réplication — optionnel, utile surtout en data-driven>

<!-- Dupliquer ce gabarit par feature réelle, supprimer ce commentaire.
     Clés-cœur : Rôle + Code + Doc durable. Le reste est contextuel.
     Aucune hypothèse d'architecture : "rôle" = le découpage du projet. -->
