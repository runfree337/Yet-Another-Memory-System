# tests/test_prefilter.py
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from prefilter import (derive_groups, entries_for_prefix, evaluate_group, load_config,
                        load_manifest, main)


class TestPrefilter(unittest.TestCase):
    def _manifest(self, rows):
        fd, path = tempfile.mkstemp(suffix=".tsv")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write("# header\n")
            for p, intent in rows:
                f.write(f"{p}\t{intent}\n")
        return path

    def test_emits_expected_keys(self):
        path = self._manifest([
            ("src/A.py", "orchestrates the phases"), ("src/B.py", "holds the deck"),
            ("src/C.py", "applies the damage"), ("src/D.py", "manages the statuses"),
            ("src/E.py", "computes the formulas"),
            ("other/X.py", "outside the group"),
        ])
        rows = load_manifest(path)
        out = evaluate_group("src/", rows)
        for k in ("group", "n_files", "max_pair_sim", "mean_pair_sim",
                  "confusable_pairs", "flagged", "too_small", "reason"):
            self.assertIn(k, out)
        self.assertEqual(out["n_files"], 5)  # only counts the src/ prefix
        self.assertFalse(out["too_small"])

    def test_small_group_is_too_small(self):
        path = self._manifest([
            ("src/A.py", "a"), ("src/B.py", "b"), ("src/C.py", "c"), ("src/D.py", "d"),
        ])
        out = evaluate_group("src/", load_manifest(path))
        self.assertTrue(out["too_small"])

    def test_prefix_normalised_without_trailing_slash(self):
        path = self._manifest([("src/A.py", "a"), ("src/B.py", "b")])
        out = evaluate_group("src", load_manifest(path))   # no trailing slash
        self.assertEqual(out["n_files"], 2)

    def test_entries_for_prefix_strips_prefix(self):
        rows = [("src/combat/A.py", "orchestrates the phases")]
        entries = entries_for_prefix(rows, "src/combat/")
        self.assertEqual(entries[0]["file"], "A.py")
        self.assertEqual(entries[0]["intent_prefixed"], "orchestrates the phases")

    def test_derive_groups_from_manifest_structure(self):
        rows = [("src/combat/A.py", "x"), ("src/combat/B.py", "y"),
                 ("docs/README.md", "z"), ("root_only.py", "w")]
        groups = derive_groups(rows)
        self.assertEqual(groups, ["src/", "docs/"])   # first-seen order, no duplicates

    def test_derive_groups_empty_when_manifest_is_flat(self):
        rows = [("A.py", "x"), ("B.py", "y")]
        self.assertEqual(derive_groups(rows), [])

    def test_load_config_missing_file_returns_none(self):
        self.assertIsNone(load_config("/nonexistent/index-config.json"))

    def test_main_without_config_exits_zero_with_message(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["prefilter.py", "--config", "/nonexistent/index-config.json"])
        self.assertEqual(code, 0)
        self.assertIn("no config", buf.getvalue())

    def test_main_with_config_and_explicit_group(self):
        manifest_path = self._manifest([
            ("src/A.py", "orchestrates the phases"), ("src/B.py", "holds the deck"),
            ("src/C.py", "applies the damage"), ("src/D.py", "manages the statuses"),
            ("src/E.py", "computes the formulas"),
        ])
        fd, config_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"manifest": manifest_path, "base": "."}, f)

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["prefilter.py", "--config", config_path, "src/"])
        self.assertEqual(code, 0)
        out = json.loads(buf.getvalue())
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["group"], "src/")
        self.assertEqual(out[0]["n_files"], 5)

    def test_main_with_config_falls_back_to_derived_groups(self):
        manifest_path = self._manifest([
            ("src/A.py", "orchestrates the phases"), ("src/B.py", "holds the deck"),
            ("src/C.py", "applies the damage"), ("src/D.py", "manages the statuses"),
            ("src/E.py", "computes the formulas"),
        ])
        fd, config_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"manifest": manifest_path, "base": "."}, f)  # no eval-groups key

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["prefilter.py", "--config", config_path])
        self.assertEqual(code, 0)
        out = json.loads(buf.getvalue())
        self.assertEqual([r["group"] for r in out], ["src/"])


if __name__ == "__main__":
    unittest.main()
