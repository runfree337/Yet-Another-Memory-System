# lib/scorer.py
#
# Pure scorer for the disambiguation axis (axis A): given the ground truth and the two
# routing outcomes (names-only vs. name+intent) for a group's queries, computes the
# lift and its confidence interval, and renders the verdict.
import math
from collections import Counter, defaultdict

# Verdict thresholds (recalibrated after the first real sweep on the reference host
# project — see `../README.md §Notes`). Realistic scale: on a repo with descriptive
# file names, `diag_names` is already close to the ceiling (0.76-0.98) => the lift
# margin is small. The verdict is driven by the paired confidence interval (McNemar),
# not the point estimate alone.
#  - Keep         : CI lower bound >= T_KEEP AND diag_name_intent >= DIAG_FLOOR.
#  - Delete        : CI upper bound < T_DELETE (the intent doesn't help, may even hurt).
#  - Marginal      : CI strictly positive (lower bound > 0) without reaching Keep.
#  - Undetermined  : CI straddles 0 (can't even settle the sign).
T_DELETE, T_KEEP, DIAG_FLOOR = 0.02, 0.10, 0.80


def diag(truth, route):
    """Diagonal accuracy: share of queries a routing sends to the file they actually
    came from."""
    if not truth:
        return 0.0
    hits = sum(1 for q, f in truth.items() if route.get(q) == f)
    return hits / len(truth)


def wald_ci(lift, p1, p2, n, z=1.96):
    """Wald CI under an independence assumption — kept for reference/diagnostics only.
    NOT used for the verdict: the two routings share the same queries (positively
    correlated), which inflates this CI. The verdict uses `mcnemar_ci` instead."""
    if n == 0:
        return (lift, lift)
    se = math.sqrt(p1 * (1 - p1) / n + p2 * (1 - p2) / n)
    return (lift - z * se, lift + z * se)


def mcnemar_ci(truth, route_a, route_b, z=1.96):
    """Paired CI of the difference of correlated proportions (McNemar test). `route_a`
    = baseline (names only), `route_b` = treatment (name+intent). lift = p_b - p_a =
    (b - c) / n, where over the n paired queries:
      b = route_a is wrong AND route_b is right (the intent fixes the routing),
      c = route_a is right AND route_b is wrong (the intent breaks the routing).
    Only the discordant pairs (b+c) carry variance -> a much tighter CI than Wald when
    the two routings agree often. Returns `(lift, (lo, hi))`."""
    n = len(truth)
    if n == 0:
        return (0.0, (0.0, 0.0))
    b = c = 0
    for q, f in truth.items():
        a_ok = route_a.get(q) == f
        b_ok = route_b.get(q) == f
        if b_ok and not a_ok:
            b += 1
        elif a_ok and not b_ok:
            c += 1
    lift = (b - c) / n
    var = (b + c - (b - c) ** 2 / n) / n ** 2
    se = math.sqrt(max(var, 0.0))
    return (lift, (lift - z * se, lift + z * se))


def classify(lift, ci, diag_ni, n_files):
    """Verdict driven by the paired CI. `lift` is only the CI's point estimate; the
    bounds (lo, hi) settle the call."""
    if n_files <= 4:
        return "Not evaluated"
    lo, hi = ci
    if lo >= T_KEEP and diag_ni >= DIAG_FLOOR:
        return "Keep"
    if hi < T_DELETE:
        return "Delete"
    if lo > 0:
        return "Marginal"
    return "Undetermined"


def score_group(truth, route_names, route_name_intent, n_files, qpf=5):
    """Score one group's disambiguation axis. `truth` / `route_names` /
    `route_name_intent` are three `{query_id: file}` mappings — the orchestrator has
    already de-anonymized `candidate_id -> file` before calling this. `qpf` = expected
    queries-per-file, used only to document the rewrite heuristic below (not enforced
    here). Returns `{ diag_names, diag_name_intent, lift, ci, n_queries, verdict,
    rewrite, confusions }`; a dict with neutral values (verdict "Not evaluated") if
    `truth` is empty."""
    if not truth:
        return {
            "diag_names": None, "diag_name_intent": None, "lift": None,
            "ci": [None, None], "n_queries": 0, "verdict": "Not evaluated",
            "rewrite": [], "confusions": {},
        }
    p_names = diag(truth, route_names)
    p_ni = diag(truth, route_name_intent)
    lift, ci = mcnemar_ci(truth, route_names, route_name_intent)
    n = len(truth)
    verdict = classify(lift, ci, p_ni, n_files)

    by_file = defaultdict(list)
    for q, f in truth.items():
        by_file[f].append(q)
    rewrite, confusions = [], {}
    for f, qs in by_file.items():
        misses = [route_name_intent.get(q) for q in qs if route_name_intent.get(q) != f]
        confusions[f] = dict(Counter(m for m in misses if m))
        # Axis B (rewrite candidates): a file misses >= 2 of its queries AND >= 2 of
        # those misses land on the same neighbor (concentrated confusion) -> signal
        # that its intent needs clarifying, not that the file should be deleted.
        if len(misses) >= 2 and confusions[f] and max(confusions[f].values()) >= 2:
            top = max(confusions[f], key=confusions[f].get)
            rewrite.append({"file": f, "misses": len(misses), "into": top})

    return {
        "diag_names": round(p_names, 3), "diag_name_intent": round(p_ni, 3),
        "lift": round(lift, 3), "ci": [round(ci[0], 3), round(ci[1], 3)],
        "n_queries": n, "verdict": verdict,
        "rewrite": rewrite, "confusions": confusions,
    }
