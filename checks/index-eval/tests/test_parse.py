# tests/test_parse.py
import unittest

from lib.parse import content_tokens, parse_subindex

SAMPLE = """# Index — Orders
- `OrderManager.py` — Orchestrates the 5 checkout phases.

## Validators/
- `CartValidator.py` — True if the cart holds an item.
- `TaxLineEffect.py` — Applies a tax line for a region.
- `TaxLineEffect.py` — Tax line effect (duplicate line).
"""


class TestParse(unittest.TestCase):
    def test_extracts_file_and_intent(self):
        e = parse_subindex(SAMPLE)
        files = [x["file"] for x in e]
        self.assertIn("OrderManager.py", files)
        self.assertIn("CartValidator.py", files)

    def test_section_prefix_applied(self):
        e = parse_subindex(SAMPLE)
        slot = next(x for x in e if x["file"] == "CartValidator.py")
        self.assertTrue(slot["intent_prefixed"].startswith("[Validators]"))
        mgr = next(x for x in e if x["file"] == "OrderManager.py")
        self.assertEqual(mgr["section"], None)

    def test_duplicates_flagged(self):
        e = parse_subindex(SAMPLE)
        dups = [x for x in e if x["file"] == "TaxLineEffect.py"]
        self.assertEqual(len(dups), 2)
        self.assertEqual([d["dup"] for d in dups], [False, True])

    def test_content_tokens_drops_stopwords(self):
        toks = content_tokens("True if the cart holds an item and the order")
        self.assertIn("cart", toks)
        self.assertIn("item", toks)
        self.assertNotIn("the", toks)
        self.assertNotIn("and", toks)


if __name__ == "__main__":
    unittest.main()
