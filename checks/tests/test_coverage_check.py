# tests/test_coverage_check.py
#
# Regression tests for `coverage-check.py` — the recount of a table against the list it
# claims to cover.
#
# The invariant: an item enumerated in a declared set and cited by no row of the table
# covering it is BLOCKING, and everything else stays silent. The two halves matter equally —
# a check that finds the gap but also fires on documents claiming nothing would be turned
# off, and then the gap goes unseen again.
#
# `test_the_founding_incident` reproduces the real document that motivated the check
# (17 findings, 5 batches cut by source file, finding 12 living outside every cited file).
# It is the only test that proves the check earns its keep: it must fail on the state of the
# document BEFORE a human question caught the gap, and pass on the state after.
import importlib.util
import os
import sys
import tempfile
import unittest

CHECKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module():
    """coverage-check.py has a hyphen — not importable by name; load it by path."""
    path = os.path.join(CHECKS_DIR, "coverage-check.py")
    spec = importlib.util.spec_from_file_location("coverage_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SET_AND_TABLE = """\
<!-- coverage-check: items; column: Items -->

| Batch | Subject | Items | State |
|---|---|---|---|
| 1 | The blockers | 0, 0 bis | done |
| 2 | The rest | 1, 2 | done |

## The list
<!-- coverage-set: items -->

### 0. First
### 0 bis. Variant
### 1. Second
### 2. Third
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.mod = _load_module()

    def rules(self, text):
        return {f.rule for f in self.mod.rule_coverage("doc.md", text.splitlines())}

    def findings(self, text):
        return self.mod.rule_coverage("doc.md", text.splitlines())

    def report(self, text, name="items"):
        return self.mod.report("doc.md", text.splitlines())[name]


class TestSilenceByDefault(Base):
    def test_document_without_markers_is_not_parsed(self):
        # The whole zero-FP premise: nothing is inferred. A document with a table AND a
        # numbered list, but no marker, must produce nothing at all.
        text = "| A | B |\n|---|---|\n| 1 | x |\n\n### 1. One\n### 2. Two\n"
        self.assertEqual(self.findings(text), [])

    def test_complete_coverage_is_silent(self):
        self.assertEqual(self.findings(SET_AND_TABLE), [])


class TestQuotedMarkersAreNotDeclarations(Base):
    # Found for real: this check fired on `checks/README.md`, the file that DOCUMENTS the
    # markers — every example there sits between backticks. A guard that cannot tell its own
    # documentation from a declaration would make every project describing it non-compliant.
    def test_marker_in_a_code_span_is_ignored(self):
        text = "Write `<!-- coverage-set: items -->` before the list.\n"
        self.assertEqual(self.findings(text), [])

    def test_marker_in_a_fenced_block_is_ignored(self):
        text = "```\n<!-- coverage-set: items -->\n<!-- coverage-check: items; column: X -->\n```\n"
        self.assertEqual(self.findings(text), [])

    def test_a_bare_marker_next_to_a_quoted_one_still_counts(self):
        # The rule must not become an escape hatch: one quoted example on the page does not
        # disarm a real declaration elsewhere in it.
        text = "Doc says `<!-- coverage-set: other -->`.\n\n" + SET_AND_TABLE
        gaps = [f for f in self.findings(text.replace("| 1, 2 |", "| 1 |"))
                if f.rule == "R-COVERAGE-GAP"]
        self.assertEqual(len(gaps), 1)


class TestGap(Base):
    def test_uncovered_item_is_blocking(self):
        text = SET_AND_TABLE.replace("| 2 | The rest | 1, 2 | done |",
                                     "| 2 | The rest | 1 | done |")
        f = [x for x in self.findings(text) if x.rule == "R-COVERAGE-GAP"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, self.mod.BLOCKING)
        self.assertIn("2", f[0].msg)

    def test_compound_id_is_not_confused_with_its_prefix(self):
        # `0 bis` must be its own item; dropping it while `0` stays covered is a real gap.
        text = SET_AND_TABLE.replace("| 0, 0 bis |", "| 0 |")
        gaps = [x.msg for x in self.findings(text) if x.rule == "R-COVERAGE-GAP"]
        self.assertEqual(len(gaps), 1)
        self.assertIn("0 bis", gaps[0])

    def test_exempt_item_does_not_fire(self):
        text = SET_AND_TABLE.replace(
            "## The list",
            "<!-- coverage-exempt: items; ids: 2; reason: out of scope -->\n\n## The list"
        ).replace("| 1, 2 |", "| 1 |")
        self.assertNotIn("R-COVERAGE-GAP", self.rules(text))
        self.assertIn("2", self.report(text)["exempt"])

    def test_id_only_in_another_column_does_not_count_as_covered(self):
        # The reason the table is parsed AS a table: a naive text scan would find "2" in the
        # Subject column and declare it covered — hiding the very gap being looked for.
        text = SET_AND_TABLE.replace("| 2 | The rest | 1, 2 | done |",
                                     "| 2 | Covers 2 as well | 1 | done |")
        gaps = [x.msg for x in self.findings(text) if x.rule == "R-COVERAGE-GAP"]
        self.assertEqual(len(gaps), 1)


class TestUnknown(Base):
    def test_cited_id_absent_from_the_set_is_to_confirm(self):
        text = SET_AND_TABLE.replace("| 1, 2 |", "| 1, 2, 99 |")
        f = [x for x in self.findings(text) if x.rule == "R-COVERAGE-UNKNOWN"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, self.mod.CONFIRM)
        self.assertIn("99", f[0].msg)


class TestDeclarationProblems(Base):
    # A marker that silently does nothing is a guard the reader believes is standing —
    # each of these is reported rather than passed over.
    def test_check_naming_an_undeclared_set(self):
        text = SET_AND_TABLE.replace("coverage-set: items", "coverage-set: others")
        self.assertIn("R-COVERAGE-DECL", self.rules(text))

    def test_set_covered_by_no_table(self):
        text = "<!-- coverage-set: items -->\n\n### 1. One\n"
        self.assertIn("R-COVERAGE-DECL", self.rules(text))

    def test_missing_column_option(self):
        text = SET_AND_TABLE.replace("; column: Items", "")
        self.assertIn("R-COVERAGE-DECL", self.rules(text))

    def test_column_absent_from_the_headers(self):
        text = SET_AND_TABLE.replace("column: Items", "column: Ghost")
        msgs = [f.msg for f in self.findings(text) if f.rule == "R-COVERAGE-DECL"]
        self.assertTrue(any("Ghost" in m for m in msgs), msgs)

    def test_no_table_after_the_marker(self):
        text = "<!-- coverage-check: items; column: Items -->\n\nno table here\n" \
               "<!-- coverage-set: items -->\n### 1. One\n"
        self.assertIn("R-COVERAGE-DECL", self.rules(text))

    def test_unreadable_pattern(self):
        text = SET_AND_TABLE.replace("coverage-set: items",
                                     "coverage-set: items; pattern: ^(unclosed")
        self.assertIn("R-COVERAGE-DECL", self.rules(text))

    def test_pattern_without_capture_group(self):
        text = SET_AND_TABLE.replace("coverage-set: items",
                                     "coverage-set: items; pattern: ^### ")
        self.assertIn("R-COVERAGE-DECL", self.rules(text))

    def test_exempt_naming_an_undeclared_set(self):
        text = SET_AND_TABLE + "\n<!-- coverage-exempt: ghosts; ids: 4 -->\n"
        msgs = [f.msg for f in self.findings(text) if f.rule == "R-COVERAGE-DECL"]
        self.assertTrue(any("ghosts" in m for m in msgs), msgs)


class TestCustomPattern(Base):
    def test_pattern_overrides_the_default(self):
        text = """\
<!-- coverage-check: reqs; column: Reqs -->

| Phase | Reqs |
|---|---|
| A | REQ-1 |

<!-- coverage-set: reqs; pattern: ^- \\[(REQ-\\d+)\\] -->

- [REQ-1] first
- [REQ-2] second
"""
        gaps = [f.msg for f in self.findings(text) if f.rule == "R-COVERAGE-GAP"]
        self.assertEqual(len(gaps), 1)
        self.assertIn("REQ-2", gaps[0])


class TestReport(Base):
    def test_report_exposes_who_covers_what(self):
        # The sets are a deliverable, not a by-product: the question after "is anything
        # missing?" is always "what covers what?".
        r = self.report(SET_AND_TABLE)
        self.assertEqual(r["items"], ["0", "0 bis", "1", "2"])
        self.assertEqual(r["rows"]["1"], ["0", "0 bis"])
        self.assertEqual(r["rows"]["2"], ["1", "2"])
        self.assertEqual(r["missing"], [])


class TestFoundingIncident(Base):
    """The document that motivated the check — it must fail before, pass after."""
    HEADER = """\
<!-- coverage-check: findings; column: Findings -->

| Lot | Sujet | Findings | État |
|---|---|---|---|
| **1** | Les deux bloquants | 0, 0 bis | **soldé** |
| **2** | La carte a-t-elle résolu ? | 3, 5, 7, 16, 4 | **soldé** |
| **3** | Rien ne casse en silence | 1, 6, 13, 14, 15 | **soldé** |
| **4** | Ce que l'écran montre est faux | 2 | **soldé** |
| **5** | Les mineurs restants | 8, 10, 11 | **soldé** |
{lot6}
<!-- coverage-exempt: findings; ids: 9; reason: dette du lot 19, hors périmètre -->

## Findings vérifiés
<!-- coverage-set: findings -->

### 0. Deux morts Concluding
### 0 bis. Variante
"""
    BODY = "".join(f"### {i}. Finding {i}\n" for i in list(range(1, 17)))

    def doc(self, with_lot6):
        lot6 = ("| **6** | La mort qui s'arme avant son coup | 12 | **soldé** |\n"
                if with_lot6 else "")
        return self.HEADER.format(lot6=lot6) + self.BODY

    def test_the_founding_incident(self):
        before = self.findings(self.doc(with_lot6=False))
        gaps = [f for f in before if f.rule == "R-COVERAGE-GAP"]
        self.assertEqual(len(gaps), 1, [f.msg for f in before])
        self.assertIn("12", gaps[0].msg)
        self.assertEqual(gaps[0].severity, self.mod.BLOCKING)

        # And the state after the sixth batch was added: silent.
        self.assertEqual(self.findings(self.doc(with_lot6=True)), [])


class TestCLI(Base):
    def test_exit_codes_follow_the_convention(self):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))

        def run(text, *flags):
            p = os.path.join(d, "doc.md")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
            return self.mod.main([p, *flags])

        self.assertEqual(run(SET_AND_TABLE), 0)
        self.assertEqual(run(SET_AND_TABLE.replace("| 1, 2 |", "| 1, 2, 99 |")), 1)
        self.assertEqual(run(SET_AND_TABLE.replace("| 1, 2 |", "| 1 |")), 2)

    def test_no_target_prints_usage_and_returns_zero(self):
        self.assertEqual(self.mod.main([]), 0)


if __name__ == "__main__":
    unittest.main()
