import unittest

from ai.matching.fusion import rrf
from ai.matching.search import keyword_search


class KeywordSearchTests(unittest.TestCase):
    def test_ranks_ids_by_bm25_and_limits_results(self):
        units = [
            {"id": "partial", "text": "python python"},
            {"id": "unrelated", "text": "java"},
            {"id": "best", "text": "Python, SQL!"},
            {"id": "tie", "text": "sql"},
            {"id": "other", "text": "rust"},
        ]
        #Javi mods to test
        #shorten and put expected list on one line
        self.assertEqual(keyword_search("PYTHON; sql.", units), ["best", "partial", "tie"])
        self.assertEqual(keyword_search("python sql", units, top_k=1), ["best"])

    def test_punctuation_on_either_side_matches(self):
        for requirement, text in (("PYTHON", "python,"), ("python,", "Python")):
            with self.subTest(requirement=requirement, text=text):
                units = [
                    {"id": "b", "text": "java"},
                    {"id": "a", "text": text},
                    {"id": "c", "text": "rust"},
                ]
                self.assertEqual(keyword_search(requirement, units, top_k=1), ["a"])

    #Javi mods to test
    #renames to follow with the empty return implementation in search
    def test_no_shared_words_return_empty(self):
        units = [{"id": "a", "text": "python"}]
        #added "Terraform" from Noah's example: a skill resume never mentions
        for requirement in ("", "!!!", "java", "Terraform"):
            with self.subTest(requirement=requirement):
                #no unit shares a word so nothing comes back for no fake matches
                self.assertEqual(keyword_search(requirement, units), [])

    def test_empty_corpus(self):
        self.assertEqual(keyword_search("python", []), [])
        units = [{"id": "a", "text": ""}, {"id": "b", "text": "!!!"}]
        self.assertEqual(keyword_search("python", units, top_k=1), [])

    def test_term_frequency_affects_ranking(self):
        units = [
            {"id": "single", "text": "python java"},
            {"id": "repeated", "text": "python python"},
            {"id": "other1", "text": "java"},
            {"id": "other2", "text": "rust"},
            {"id": "other3", "text": "sql"},
        ]
        self.assertEqual(keyword_search("python", units, top_k=2), ["repeated", "single"])

    #Add two extra test functions
    def test_word_in_half_the_units_still_counts(self):
        #BM25Plus ranks closer matches first compared to BM25Okapi which scores every unit 0
        units = [ 
            {"id": "a", "text": "python java"},
            {"id": "b", "text": "rust"},
            {"id": "c", "text": "python"},
            {"id": "d", "text": "go"}
        ]
        self.assertEqual(keyword_search("python", units), ["c", "a"])

    def test_ties_keep_input_order(self):
        units = [{"id": "a", "text": "python"}, {"id": "b", "text": "python"}]
        self.assertEqual(keyword_search("python", units), ["a" ,"b"])

    
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

    #Javier mods to fit test new tests

    def test_example_from_review(self):
        self.assertEqual(rrf(["a", "b", "c"], ["b", "c", "a"]), ["b", "a", "c"])

    def test_no_lists_returns_empty(self):
        self.assertEqual(rrf(), [])

