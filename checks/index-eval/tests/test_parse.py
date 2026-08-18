# tests/test_parse.py
import unittest

from lib import parse
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


class TestTokenizerVocabulary(unittest.TestCase):
    """The tokenizer must serve a project whose intents are NOT in English. Both cases
    below fail SILENTLY when unhandled — they inflate a similarity or a contamination
    ratio rather than raising, so nothing but an assertion catches them."""

    def tearDown(self):
        parse.set_stopwords([])  # back to the English default for the next test

    def test_accented_word_stays_one_token(self):
        # Without Latin-1 in the separator class, `réécrire` splits into `r` + `crire`:
        # the real word is gone and the fragment matches nothing.
        self.assertIn("réécrire", content_tokens("Réécrire la ligne"))

    def test_project_stopwords_extend_the_english_default(self):
        parse.set_stopwords(["la", "les", "des"])
        toks = content_tokens("Applique les effets des cartes de la main")
        self.assertNotIn("les", toks)
        self.assertNotIn("des", toks)
        self.assertIn("applique", toks)
        self.assertIn("cartes", toks)
        self.assertNotIn("the", toks, "the English default must survive the extension")

    def test_set_stopwords_does_not_stack_across_loads(self):
        parse.set_stopwords(["alpha"])
        parse.set_stopwords(["beta"])
        toks = content_tokens("alpha beta")
        self.assertIn("alpha", toks, "the first config's words must not linger")
        self.assertNotIn("beta", toks)

    def test_extend_is_case_insensitive(self):
        parse.extend_stopwords(["Pour"])
        self.assertNotIn("pour", content_tokens("Pour chaque carte"))


if __name__ == "__main__":
    unittest.main()
