# tests/test_sufficiency.py
import unittest

from lib.sufficiency import classify_sufficiency, score_sufficiency


def _pq(file, intent_ok, names_ok, k=1):
    return [{"qid": f"{file}_{i}", "file": file,
             "intent_ok": intent_ok, "names_ok": names_ok} for i in range(k)]


class TestSufficiency(unittest.TestCase):
    def test_classify_rich(self):
        v = classify_sufficiency(lift=0.5, ci=(0.4, 0.6), suff_intent=0.7, n_files=20)
        self.assertEqual(v, "Rich intent")

    def test_classify_useful_below_rich_floor(self):
        # CI > 0 but suff_intent below the "rich" threshold
        v = classify_sufficiency(lift=0.3, ci=(0.2, 0.4), suff_intent=0.45, n_files=20)
        self.assertEqual(v, "Useful intent")

    def test_classify_poor(self):
        v = classify_sufficiency(lift=0.0, ci=(-0.03, 0.02), suff_intent=0.2, n_files=20)
        self.assertEqual(v, "Poor intent")

    def test_classify_undetermined(self):
        v = classify_sufficiency(lift=0.05, ci=(-0.1, 0.2), suff_intent=0.5, n_files=20)
        self.assertEqual(v, "Undetermined")

    def test_classify_not_evaluated(self):
        v = classify_sufficiency(lift=0.5, ci=(0.4, 0.6), suff_intent=0.9, n_files=4)
        self.assertEqual(v, "Not evaluated")

    def test_score_computes_sufficiency_and_lift(self):
        # 10 questions: the intent answers 8, the name answers 2.
        pq = []
        for i in range(10):
            pq.append({"qid": f"q{i}", "file": "A",
                       "intent_ok": i < 8, "names_ok": i < 2})
        res = score_sufficiency(pq, n_files=20)
        self.assertAlmostEqual(res["suff_intent"], 0.8)
        self.assertAlmostEqual(res["suff_names"], 0.2)
        self.assertAlmostEqual(res["lift"], 0.6)
        self.assertGreater(res["ci"][0], 0)  # CI strictly positive

    def test_weak_file_flagged_when_intent_answers_nothing(self):
        pq = _pq("Weak.py", intent_ok=False, names_ok=False, k=3)
        pq += _pq("Good.py", intent_ok=True, names_ok=False, k=3)
        res = score_sufficiency(pq, n_files=20)
        weak = {w["file"] for w in res["weak_files"]}
        self.assertIn("Weak.py", weak)
        self.assertNotIn("Good.py", weak)

    def test_empty_is_not_evaluated(self):
        self.assertEqual(score_sufficiency([], n_files=20)["verdict"], "Not evaluated")


if __name__ == "__main__":
    unittest.main()
