# tests/test_scorer.py
import unittest

from lib.scorer import classify, diag, mcnemar_ci, score_group, wald_ci


class TestScorer(unittest.TestCase):
    def test_diag_counts_hits(self):
        truth = {"q1": "A", "q2": "A", "q3": "B"}
        route = {"q1": "A", "q2": "B", "q3": "B"}
        self.assertAlmostEqual(diag(truth, route), 2 / 3)

    def test_wald_ci_brackets_point(self):
        lo, hi = wald_ci(lift=0.20, p1=0.80, p2=0.60, n=100)
        self.assertLess(lo, 0.20)
        self.assertGreater(hi, 0.20)

    def test_mcnemar_ci_uses_only_discordant_pairs(self):
        # 10 queries: the intent fixes 2 (b=2), breaks 0 (c=0), the rest concordant.
        # Expected lift = (2-0)/10 = 0.2; the CI brackets the point.
        truth = {f"q{i}": "A" for i in range(10)}
        route_names = dict(truth)
        route_names["q0"] = "B"
        route_names["q1"] = "B"
        route_ni = dict(truth)  # name+intent gets everything right
        lift, (lo, hi) = mcnemar_ci(truth, route_names, route_ni)
        self.assertAlmostEqual(lift, 0.2)
        self.assertLess(lo, 0.2)
        self.assertGreater(hi, 0.2)
        # Paired CI strictly tighter than the independent Wald CI here (c=0, strong correlation)
        wlo, whi = wald_ci(lift, 1.0, 0.8, 10)
        self.assertGreaterEqual(lo, wlo)

    def test_classify_delete_ci_below_floor(self):
        # CI entirely below T_DELETE (0.02) -> the intent doesn't help
        v = classify(lift=-0.02, ci=(-0.06, 0.01), diag_ni=0.5, n_files=20)
        self.assertEqual(v, "Delete")

    def test_classify_keep_ci_above_keep_floor(self):
        # CI lower bound >= T_KEEP (0.10) AND diag_ni >= 0.80
        v = classify(lift=0.30, ci=(0.22, 0.38), diag_ni=0.9, n_files=20)
        self.assertEqual(v, "Keep")

    def test_classify_marginal_ci_strictly_positive(self):
        # CI strictly > 0 but lower bound < T_KEEP -> the intent helps, modestly
        v = classify(lift=0.05, ci=(0.01, 0.09), diag_ni=0.85, n_files=20)
        self.assertEqual(v, "Marginal")

    def test_classify_undetermined_ci_straddles_zero(self):
        # CI straddles 0 -> sign undeterminable
        v = classify(lift=0.0, ci=(-0.05, 0.05), diag_ni=0.85, n_files=20)
        self.assertEqual(v, "Undetermined")

    def test_classify_not_evaluated_small(self):
        v = classify(lift=0.30, ci=(0.2, 0.4), diag_ni=0.9, n_files=4)
        self.assertEqual(v, "Not evaluated")

    def test_axis_b_lists_concentrated_failures(self):
        # A misses 2/2 towards B (concentrated) — each file's own queries
        truth = {"a1": "A", "a2": "A", "b1": "B", "b2": "B"}
        route_ni = {"a1": "B", "a2": "B", "b1": "B", "b2": "B"}
        route_names = {"a1": "A", "a2": "A", "b1": "B", "b2": "B"}
        res = score_group(truth, route_names, route_ni, n_files=10, qpf=2)
        rewrite_files = {r["file"] for r in res["rewrite"]}
        self.assertIn("A", rewrite_files)

    def test_empty_truth_is_not_evaluated(self):
        self.assertEqual(
            score_group({}, {}, {}, n_files=10)["verdict"], "Not evaluated")


if __name__ == "__main__":
    unittest.main()
