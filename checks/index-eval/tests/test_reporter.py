# tests/test_reporter.py
import unittest

from lib.reporter import render


class TestReporter(unittest.TestCase):
    def test_render_contains_recap_and_verdict(self):
        results = [{
            "group": "src/combat/",
            "n_files": 20, "diag_names": 0.55, "diag_name_intent": 0.85,
            "lift": 0.30, "ci": [0.22, 0.38], "n_queries": 100, "verdict": "Keep",
            "partial": False,
            "rewrite": [{"file": "ResultType.py", "misses": 3, "into": "SlotCondition.py"}],
            "confusions": {"ResultType.py": {"SlotCondition.py": 3}},
        }]
        md = render(results)
        self.assertIn("| Group | Verdict | lift", md)   # recap
        self.assertIn("Keep", md)
        self.assertIn("ResultType.py", md)               # rewrite line cited

    def test_render_tolerates_none_lift(self):
        results = [
            {
                "group": "X/", "n_files": 4, "verdict": "Not evaluated",
                "diag_names": None, "diag_name_intent": None, "lift": None,
                "ci": [None, None], "n_queries": 0, "rewrite": [],
                "confusions": {}, "partial": False,
            },
            {
                "group": "Y/", "n_files": 20, "diag_names": 0.5,
                "diag_name_intent": 0.7, "lift": 0.2, "ci": [0.1, 0.3],
                "n_queries": 200, "verdict": "Keep", "partial": False,
                "rewrite": [], "confusions": {},
            },
        ]
        md = render(results)   # must not raise
        self.assertIn("`X/`", md)
        self.assertIn("`Y/`", md)

    def test_partial_flag_rendered(self):
        results = [{
            "group": "X/", "n_files": 88, "diag_names": 0.5, "diag_name_intent": 0.7,
            "lift": 0.2, "ci": [0.1, 0.3], "n_queries": 200, "verdict": "Keep",
            "partial": True, "rewrite": [], "confusions": {},
        }]
        md = render(results)
        self.assertIn("partial", md.lower())


if __name__ == "__main__":
    unittest.main()
