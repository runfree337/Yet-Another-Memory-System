# lib/guard.py
#
# Deterministic anti-co-derivation guard (index-eval, Tier 1). Protects the LLM-judged
# routing pass from a leak: if a generated query recopies too much vocabulary from the
# file's own intent, the lift measurement becomes circular — the intent would end up
# scoring itself instead of being tested against an independent query. See
# `../README.md §Anti-leakage rule`.
from lib.parse import content_tokens


def overlap_ratio(query, source_intent):
    """Share of the query's content words that are also present in the source
    intent (0.0 if the query has no content words at all)."""
    q = content_tokens(query)
    if not q:
        return 0.0
    src = content_tokens(source_intent)
    return len(q & src) / len(q)


def is_contaminated(query, source_intent, threshold=0.5):
    """True if the query leaks the source intent's vocabulary (overlap ratio >=
    threshold) — the orchestrator must regenerate this query (see the orchestration
    recipe, step 6: guard, <= 2 retries, then "vocabulary saturated" exclusion)."""
    return overlap_ratio(query, source_intent) >= threshold
