import unittest

from ai.matching.fusion import rrf


class RrfTests(unittest.TestCase):
    def test_b_ranks_first_across_reordered_lists(self):
        # Test that "b" ranks first when it appears in both lists, even if the order is different.
        self.assertEqual(rrf(["a", "b", "c"], ["b", "c", "a"])[0], "b")

    def test_includes_items_from_a_separate_list(self):
        # Test that "c" is included in the results when it appears in a separate list.
        self.assertIn("c", rrf(["a", "b"], ["c"]))