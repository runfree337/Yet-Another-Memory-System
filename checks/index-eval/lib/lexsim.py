# lib/lexsim.py
#
# Pure lexical similarity (Jaccard over content tokens) — the deterministic prefilter
# (Tier 0). Flags a group as worth spending an LLM-judged evaluation on, before any
# LLM call is made. See `../prefilter.py`.
from itertools import combinations

from lib.parse import content_tokens


def jaccard(a, b):
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def pairwise(entries, confusable_at=0.5):
    """Pairwise Jaccard similarity of intents within a group. Returns the max/mean
    similarity plus the list of pairs at or above `confusable_at` — two files whose
    intents overlap that much are a signal that at least one intent just paraphrases
    the file name instead of describing what makes the file distinct."""
    toks = {e["file"]: content_tokens(e["intent_prefixed"]) for e in entries}
    sims, confusable = [], []
    for x, y in combinations(entries, 2):
        s = jaccard(toks[x["file"]], toks[y["file"]])
        sims.append(s)
        if s >= confusable_at:
            confusable.append({"files": [x["file"], y["file"]], "sim": round(s, 3)})
    return {
        "max_pair_sim": round(max(sims), 3) if sims else 0.0,
        "mean_pair_sim": round(sum(sims) / len(sims), 3) if sims else 0.0,
        "confusable_pairs": confusable,
    }


def decide_flag(n_files, max_pair_sim, threshold=0.5):
    """A group is `too_small` (<= 4 files — an LLM evaluation would not be
    statistically meaningful), `flagged` (max pairwise similarity >= threshold — worth
    the LLM routing pass), or clean (skip it, the lexical signal already looks fine)."""
    too_small = n_files <= 4
    flagged = (not too_small) and max_pair_sim >= threshold
    reason = "too_small" if too_small else ("high_pair_sim" if flagged else "clean")
    return {"flagged": flagged, "too_small": too_small, "reason": reason}
