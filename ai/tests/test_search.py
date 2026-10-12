"""     Test_Search: Used for keyword search and rank fusion

This chunk of code runs the code just written with known input
and checks the answer to what is expected.

"""

import unittest

#Functions from to test the task
from ai.matching.fusion import reciprocal_rank_fusion
from ai.matching.search import keyword_search, tokenize

#Define the mock resumes dataset with different lines to test functionality
FAKE_RESUME = [
    "Built a REST API in Python and Flask",
    "Led a team of four on a semester class project",
    "Designed a mobile app screen in Figma",
    "Wrote SQL queries to clean sales data",
    "Tutored first year students in C++",
]

#Test the suite to varified the tokenize() function
class TestTokenize(unittest.TestCase):
    #Test that text is lowercased and punctuation
    def test_lowercase_and_drops_punctuation(self):
        self.assertEqual(tokenize("Built APIs, FAST!"), ["built", "apis", "fast"])

    #Test common filler words are filtered
    def test_drops_filler_words(self):
        self.assertEqual(tokenize("Experience with Python"), ["python"])

    #Test important symbols in technical programming names are preserved
    def test_keeps_symbols_in_language_names(self):
        self.assertEqual(tokenize("C++ and C#"), ["c++", "c#"])

#Test suite for verifying the keyword_search() function
class TestKeywordSearch(unittest.TestCase):
    #Test basic search query successfully finds and returns correct top line
    def test_example_from_the_task(self):
        results = keyword_search("Python", FAKE_RESUME)
        self.assertEqual(results[0] ["text"], "Built a REST API in Python and Flask")

    #Test uppercase search queries match lowercase resume text
    def test_capital_letters_do_not_matter(self):
        results = keyword_search("PYTHON", FAKE_RESUME)
        self.assertEqual(results[0]["line_index"], 0)

    #Test resume lines completely unrelated to the query terms
    def test_lines_with_no_shared_words_are_left_out(self):
        results = keyword_search("Python", FAKE_RESUME)
        self.assertEqual([r["line_index"] for r in results], [0])

    #Test searching for a term that doesn't exist anywhere returns an empty list
    def test_no_match_returns_empty_list(self):
        self.assertEqual(keyword_search("Kubernetes", FAKE_RESUME), [])

    #Test empty search queries or empty resume lists safely return
    def test_empty_inputs_return_empty_list(self):
        self.assertEqual(keyword_search("", FAKE_RESUME), [])
        self.assertEqual(keyword_search("Python", []),[])

    #Test BM25 scoring correctly prioritizes lines containing rarer and multiple matching terms
    def test_rare_words_count_more(self):
        resume = [
            "Automated reports using Python",
            "Wrote Python scripts to clean data",
            "Built a web app in Python and Flask",
        ]
        results = keyword_search("Python Flask", resume)
        self.assertEqual(results[0]["line_index"], 2)
        self.assertEqual(len(results), 3)

    #Test the top_k parameter successfully limits the maximum number of returned results
    def test_top_k_limits_how_many_come_back(self):
        resume = ["Python one", "Python two", "Python three"]
        self.assertEqual(len(keyword_search("Python", resume, top_k = 2)), 2)

    #Test returned search results are properly sorted in descending order by relevance score
    def test_results_are_sorted_best_first(self):
        results = keyword_search("Python Flask SQL data", FAKE_RESUME)
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse = True))


#Test suite for verifying the reciprocal_rank_fusion() function
class TestFusion(unittest.TestCase):

    #Test a line appearing near the top in multiple separate rank lists gets boosted to the top
    def test_line_in_both_lists_wins(self):
        keyword_list = [0, 3, 4]
        meaning_list = [2, 0, 1]
        fused = reciprocal_rank_fusion([keyword_list, meaning_list])
        self.assertEqual(fused[0]["line_index"], 0)

    #Test fusing lists includes all unique line indexes without dropping any items
    def test_every_line_shows_up_once(self):
        fused = reciprocal_rank_fusion([[0, 3, 4], [2, 0, 1]])
        self.assertEqual(sorted(r["line_index"] for r in fused), [0, 1, 2, 3, 4])

    #Test if only a single list is passed to fusion, it preserves its original ranking order
    def test_one_list_keeps_its_order(self):
        fused = reciprocal_rank_fusion([[4, 1, 3]])
        self.assertEqual([r["line_index"] for r in fused], [4, 1, 3])

    #Test passing an empty list of rankings returns an empty fused result
    def test_no_lists_returns_empty(self):
        self.assertEqual(reciprocal_rank_fusion([]), [])

    #Test real output from keyword_search can be successfully chained/fed directly into fusion
    def test_search_results_can_feed_fusion(self):
        results = keyword_search("Python Flask", FAKE_RESUME)
        keyword_list = [r["line_index"] for r in results]
        fused = reciprocal_rank_fusion([keyword_list, [0, 2]])
        self.assertEqual(fused[0]["line_index"], 0)

#Entry point to execute the unit tests from the terminal
if __name__ == "__main__":
    unittest.main()