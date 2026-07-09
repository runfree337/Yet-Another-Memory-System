# tests/test_guard.py
import unittest

from lib.guard import is_contaminated, overlap_ratio


class TestGuard(unittest.TestCase):
    def test_overlap_ratio_full(self):
        # the whole query is contained in the source intent
        r = overlap_ratio("tick damage status", "applies a damage tick for a burn status")
        self.assertAlmostEqual(r, 1.0)

    def test_overlap_ratio_none(self):
        r = overlap_ratio("where to reduce damage taken via armor", "holds the draw pile")
        self.assertEqual(r, 0.0)

    def test_contaminated_above_threshold(self):
        self.assertTrue(is_contaminated("tick damage status",
                                        "tick of damage for a status", threshold=0.5))

    def test_clean_below_threshold(self):
        self.assertFalse(is_contaminated("where to reduce damage taken via armor",
                                         "tick of damage for a status", threshold=0.5))


if __name__ == "__main__":
    unittest.main()
