# lib/sufficiency.py
#
# "Sufficiency" axis (axis B') — complementary to the disambiguation axis
# (`scorer.py`). Instead of "does the intent help CHOOSE the right file?", it measures
# "does the intent carry enough information to ACT without OPENING the file?".
#
# Protocol (orchestrated by the skill/agent, not by this module): for each file, a
# generator produces factual questions about its BEHAVIOR (derived from the code,
# never from the intent) plus a short reference answer. Two closed-book responders
# attempt to answer them — one given the intent alone, the other the file name alone —
# with the right to abstain ("information unavailable", counted as incorrect, never a
# guessed answer). A blind grader scores each answer against the reference. This
# module only does the SCORING: it takes the grading verdicts and computes sufficiency
# + lift +/- a paired confidence interval.
#
# Why a separate axis: the disambiguation axis has a ceiling effect (file names are
# already discriminative on a well-named repo), so it underestimates the index's real
# value to an agent — which is mostly reading-time savings ("can I skip opening this
# file?").
from lib.scorer import mcnemar_ci

# Sufficiency-axis verdict thresholds. suff_intent = fraction of behavior questions
# correctly answered from the intent alone; the lift is suff_intent - suff_names.
SUFF_RICH = 0.60   # the intent alone answers >= 60% of the behavior questions
SUFF_FLOOR = 0.05  # below this, the intent adds ~nothing over the bare file name


def classify_sufficiency(lift, ci, suff_intent, n_files):
    """Verdict driven by the paired CI of the lift, nuanced by absolute sufficiency.
      - Rich intent : CI strictly positive AND suff_intent >= SUFF_RICH.
      - Useful intent: CI strictly positive without reaching "rich".
      - Poor intent  : CI entirely < SUFF_FLOOR (adds ~nothing over the file name).
      - Undetermined : CI straddles 0.
      - Not evaluated: too few files."""
    if n_files <= 4:
        return "Not evaluated"
    lo, hi = ci
    if lo > 0 and suff_intent >= SUFF_RICH:
        return "Rich intent"
    if hi < SUFF_FLOOR:
        return "Poor intent"
    if lo > 0:
        return "Useful intent"
    return "Undetermined"


def score_sufficiency(per_question, n_files):
    """`per_question`: list of dicts `{ "qid", "file", "intent_ok": bool, "names_ok":
    bool }` — binary grading verdicts (abstention already folded in as `False`).
    Returns the same key shape as `scorer.score_group` to stay reporter-compatible,
    plus `suff_intent` / `suff_names` / `weak_files`."""
    if not per_question:
        return {
            "suff_intent": None, "suff_names": None, "lift": None,
            "ci": [None, None], "n_queries": 0, "verdict": "Not evaluated",
            "weak_files": [],
        }
    n = len(per_question)
    suff_intent = sum(1 for r in per_question if r["intent_ok"]) / n
    suff_names = sum(1 for r in per_question if r["names_ok"]) / n

    # Paired CI: truth = every question "should" be answered OK; a routing "hits" iff
    # its answer was graded correct.
    truth = {r["qid"]: "OK" for r in per_question}
    route_names = {r["qid"]: "OK" if r["names_ok"] else "X" for r in per_question}
    route_intent = {r["qid"]: "OK" if r["intent_ok"] else "X" for r in per_question}
    lift, ci = mcnemar_ci(truth, route_names, route_intent)
    verdict = classify_sufficiency(lift, ci, suff_intent, n_files)

    # Files whose intent answers NONE of its questions (>= 2 asked) even though the
    # code carries the answer -> candidates for a richer intent.
    by_file = {}
    for r in per_question:
        by_file.setdefault(r["file"], []).append(r)
    weak_files = []
    for f, rs in by_file.items():
        if len(rs) >= 2 and not any(r["intent_ok"] for r in rs):
            weak_files.append({"file": f, "questions": len(rs)})

    return {
        "suff_intent": round(suff_intent, 3), "suff_names": round(suff_names, 3),
        "lift": round(lift, 3), "ci": [round(ci[0], 3), round(ci[1], 3)],
        "n_queries": n, "verdict": verdict, "weak_files": weak_files,
    }
