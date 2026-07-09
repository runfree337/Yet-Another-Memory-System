# tests/test_parse.py
import unittest

from lib.parse import content_tokens, parse_subindex

SAMPLE = """# Index — Combat
- `CombatManager.py` — Orchestrates the 5 combat phases.

## Conditions/
- `SlotCondition.py` — True if the slot holds a card.
- `StatusDamageTickEffect.py` — Applies a damage tick for a status.
- `StatusDamageTickEffect.py` — Status damage tick effect (duplicate line).
"""


class TestParse(unittest.TestCase):
    def test_extracts_file_and_intent(self):
        e = parse_subindex(SAMPLE)
        files = [x["file"] for x in e]
        self.assertIn("CombatManager.py", files)
        self.assertIn("SlotCondition.py", files)

    def test_section_prefix_applied(self):
        e = parse_subindex(SAMPLE)
        slot = next(x for x in e if x["file"] == "SlotCondition.py")
        self.assertTrue(slot["intent_prefixed"].startswith("[Conditions]"))
        mgr = next(x for x in e if x["file"] == "CombatManager.py")
        self.assertEqual(mgr["section"], None)

    def test_duplicates_flagged(self):
        e = parse_subindex(SAMPLE)
        dups = [x for x in e if x["file"] == "StatusDamageTickEffect.py"]
        self.assertEqual(len(dups), 2)
        self.assertEqual([d["dup"] for d in dups], [False, True])

    def test_content_tokens_drops_stopwords(self):
        toks = content_tokens("True if the slot holds a card and the deck")
        self.assertIn("slot", toks)
        self.assertIn("card", toks)
        self.assertNotIn("the", toks)
        self.assertNotIn("and", toks)


if __name__ == "__main__":
    unittest.main()
