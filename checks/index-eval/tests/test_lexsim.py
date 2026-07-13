# tests/test_lexsim.py
import unittest

from lib.lexsim import decide_flag, jaccard, pairwise


class TestLexsim(unittest.TestCase):
    def test_jaccard_identical_is_one(self):
        self.assertEqual(jaccard({"a", "b"}, {"a", "b"}), 1.0)

    def test_jaccard_disjoint_is_zero(self):
        self.assertEqual(jaccard({"a"}, {"b"}), 0.0)

    def test_pairwise_finds_confusable(self):
        entries = [
            {"file": "A.py", "intent_prefixed": "apply fee region north"},
            {"file": "B.py", "intent_prefixed": "apply fee region south"},
            {"file": "C.py", "intent_prefixed": "orchestrates the order phases"},
        ]
        res = pairwise(entries)
        self.assertGreater(res["max_pair_sim"], 0.5)
        pair_files = {tuple(sorted(p["files"])) for p in res["confusable_pairs"]}
        self.assertIn(("A.py", "B.py"), pair_files)

    def test_decide_flag_too_small(self):
        f = decide_flag(n_files=4, max_pair_sim=0.0, threshold=0.5)
        self.assertTrue(f["too_small"])
        self.assertFalse(f["flagged"])

    def test_decide_flag_high_similarity(self):
        f = decide_flag(n_files=10, max_pair_sim=0.7, threshold=0.5)
        self.assertTrue(f["flagged"])
        self.assertFalse(f["too_small"])


if __name__ == "__main__":
    unittest.main()
