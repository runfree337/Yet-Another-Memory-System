# tests/test_decisions_check.py
#
# Regression test for D5 — an archival gist that cites its ACTIVE successor (the form the
# protocol requires: "invariant migré au successeur D-…") must not make that successor look
# "referenced under ## Archived". Only ENTRY lines (`- [<id>](…)`) count as a section
# reference; inline mentions do not. Symmetric for an active line mentioning an archived id.
import importlib.util
import os
import tempfile
import unittest

CHECKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module():
    """decisions-check.py has a hyphen — not importable by name; load it by path."""
    path = os.path.join(CHECKS_DIR, "decisions-check.py")
    spec = importlib.util.spec_from_file_location("decisions_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


INDEX_WITH_INLINE_CITATIONS = """# Decisions — INDEX

## Active
- [D-2026-07-11-02](D-2026-07-11-02.md) — successor · carries the invariant now, replaces D-2026-07-10-01.

## Archived
- [D-2026-07-10-01](D-2026-07-10-01.md) — old decision · invariant migré au successeur D-2026-07-11-02.
"""


class TestIndexSections(unittest.TestCase):
    def setUp(self):
        self.mod = _load_module()

    def _sections_for(self, text):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(text)
            tmp = fh.name
        self.addCleanup(os.unlink, tmp)
        self.mod.INDEX = tmp
        return self.mod._index_sections()

    def test_inline_citation_does_not_leak_across_sections(self):
        actives, archived = self._sections_for(INDEX_WITH_INLINE_CITATIONS)
        # The active successor is cited inline inside the archived entry's gist, and the
        # archived id is cited inline inside the active entry's gist. Neither inline mention
        # is an entry line, so each id belongs ONLY to its own entry-line section.
        self.assertEqual(actives, {"D-2026-07-11-02"})
        self.assertEqual(archived, {"D-2026-07-10-01"})

    def test_no_d5_false_positive_on_active_successor(self):
        actives, archived = self._sections_for(INDEX_WITH_INLINE_CITATIONS)
        findings = self.mod.rule_d5(
            "D-2026-07-11-02", "decisions/D-2026-07-11-02.md",
            {"status": "active"}, actives, archived,
        )
        self.assertEqual(findings, [], "active successor cited in an archival gist must not trip D5")

    def test_d5_still_catches_a_real_mismatch(self):
        # A genuinely archived file whose ENTRY line sits under ## Active is still blocking.
        actives, archived = self._sections_for(INDEX_WITH_INLINE_CITATIONS)
        findings = self.mod.rule_d5(
            "D-2026-07-11-02", "decisions/D-2026-07-11-02.md",
            {"status": "archived"}, actives, archived,
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "D5")


if __name__ == "__main__":
    unittest.main()
