# tests/test_measures_check.py
#
# Regression tests for `measures-check.py` — a number in the docs checked against the measure
# its marker names.
#
# The invariant: a marked number that no longer equals its measure is reported, and a marked
# number that does is silent. Both halves matter — a check that also fires on correct numbers
# gets turned off, and the stale ones go unseen again.
#
# `test_the_founding_incident` reproduces the real case that motivated the check: a work-item
# doc kept a class size (607) after the class grew, and nothing said so until a daily audit
# re-measured it by hand a day later.
import importlib.util
import os
import sys
import tempfile
import textwrap
import unittest

CHECKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module():
    """measures-check.py has a hyphen — not importable by name; load it by path."""
    path = os.path.join(CHECKS_DIR, "measures-check.py")
    spec = importlib.util.spec_from_file_location("measures_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MC = _load_module()

MEASURES = {
    "size": lambda arg: {"Scorer.cs": 640, "Context.cs": 602}[arg],
    "cards": lambda _: 80,
}


def rules(text: str):
    return [(f.rule, f.line) for f in MC.rule_markers("doc.md", text.splitlines(), MEASURES)]


class TestMarkers(unittest.TestCase):
    def test_matching_number_is_silent(self):
        self.assertEqual(rules("80 player cards <!-- measure: cards -->"), [])

    def test_the_founding_incident(self):
        doc = "- [todo] `Scorer.cs` (**607 lines of code <!-- measure: size:Scorer.cs --> on 10-02**, 350 on 09-18)"
        self.assertEqual(rules(doc), [("MS-STALE", 1)])

    def test_last_number_before_the_marker_is_the_one_checked(self):
        # the 600 threshold and the date sit BEFORE the number in the same line: ignored
        doc = "threshold 600, on 2026-10-02: 602 <!-- measure: size:Context.cs -->"
        self.assertEqual(rules(doc), [])

    def test_two_markers_on_one_line_each_read_their_own_number(self):
        doc = "602 <!-- measure: size:Context.cs --> and 79 <!-- measure: cards -->"
        self.assertEqual(rules(doc), [("MS-STALE", 1)])

    def test_unknown_measure_is_blocking(self):
        f = MC.rule_markers("d.md", ["80 <!-- measure: card -->"], MEASURES)
        self.assertEqual([(x.rule, x.severity) for x in f], [("MS-UNKNOWN", MC.BLOCKING)])

    def test_marker_without_number_is_blocking(self):
        self.assertEqual(rules("cards <!-- measure: cards -->"), [("MS-NO-NUMBER", 1)])

    def test_vanished_target_is_unmeasurable(self):
        self.assertEqual(rules("12 <!-- measure: size:Gone.cs -->"), [("MS-UNMEASURABLE", 1)])

    def test_marker_in_a_code_fence_is_an_example(self):
        doc = "```\n1 <!-- measure: cards -->\n```"
        self.assertEqual(rules(doc), [])

    def test_marker_quoted_as_inline_code_declares_nothing(self):
        self.assertEqual(rules("write `<!-- measure: cards -->` after the number"), [])

    def test_decimal_with_comma(self):
        m = {"ratio": lambda _: 2.5}
        f = MC.rule_markers("d.md", ["2,5 <!-- measure: ratio -->"], m)
        self.assertEqual(f, [])


class TestLoadMeasures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _module(self, body: str):
        with open(os.path.join(self.tmp, "m.py"), "w", encoding="utf-8") as fh:
            fh.write(textwrap.dedent(body))
        return {"measures": {"module": "m.py"}}

    def test_no_key_is_inactive(self):
        self.assertEqual(MC.load_measures({}, self.tmp), (None, None))

    def test_declared_module_is_loaded(self):
        cfg = self._module("MEASURES = {'n': lambda a: 3}\n")
        measures, err = MC.load_measures(cfg, self.tmp)
        self.assertIsNone(err)
        self.assertEqual(measures["n"](""), 3)

    def test_missing_module_is_an_error(self):
        _, err = MC.load_measures({"measures": {"module": "absent.py"}}, self.tmp)
        self.assertIn("not found", err)

    def test_module_without_measures_is_an_error(self):
        _, err = MC.load_measures(self._module("X = 1\n"), self.tmp)
        self.assertIn("MEASURES", err)

    def test_module_that_raises_is_an_error(self):
        _, err = MC.load_measures(self._module("raise RuntimeError('boom')\n"), self.tmp)
        self.assertIn("failed to load", err)


if __name__ == "__main__":
    unittest.main()
