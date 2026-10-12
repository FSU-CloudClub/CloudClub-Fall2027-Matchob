import unittest

from ai.matching.fusion import rrf
from ai.matching.search import keyword_search


class KeywordSearchTests(unittest.TestCase):
    def test_ranks_ids_by_shared_words_and_limits_results(self):
        units = [
            {"id": "partial", "text": "python python"},
            {"id": "unrelated", "text": "java"},
            {"id": "best", "text": "Python, SQL!"},
            {"id": "tie", "text": "sql"},
        ]
        self.assertEqual(
            keyword_search("PYTHON; sql.", units), ["best", "partial", "tie"]
        )
        self.assertEqual(keyword_search("python sql", units, top_k=1), ["best"])

    def test_punctuation_on_either_side_matches(self):
        self.assertEqual(
            keyword_search("python", [{"id": "a", "text": "python,"}]), ["a"]
        )
        self.assertEqual(
            keyword_search("python,", [{"id": "a", "text": "python"}]), ["a"]
        )

    def test_empty_or_unmatched_search_returns_no_ids(self):
        units = [{"id": "a", "text": "python"}]
        for requirement in ("", "!!!", "java"):
            with self.subTest(requirement=requirement):
                self.assertEqual(keyword_search(requirement, units), [])
        self.assertEqual(keyword_search("python", []), [])

    def test_nonpositive_limit_returns_no_ids(self):
        units = [{"id": "a", "text": "python"}]
        for top_k in (0, -1):
            with self.subTest(top_k=top_k):
                self.assertEqual(keyword_search("python", units, top_k), [])


class RrfTests(unittest.TestCase):
    def test_b_ranks_first_across_reordered_lists(self):
        # Test that "b" ranks first when it appears in both lists, even if the order is different.
        self.assertEqual(rrf(["a", "b", "c"], ["b", "c", "a"])[0], "b")

    def test_includes_items_from_a_separate_list(self):
        # Test that "c" is included in the results when it appears in a separate list.
        self.assertIn("c", rrf(["a", "b"], ["c"]))
