import unittest

from ai.guardrails.claims import find_numbers, find_scope_words, find_titles
from ai.guardrails.span_check import span_exists
from ai.guardrails.text import clean

SOURCE = ("- Helped migrate weekly reports from Excel to SQL.\n"
          "- Rebuilt the order form and reduced page load time by 30%.")


class TestClean(unittest.TestCase):
    def test_pdf_spacing_and_invisible_characters(self):
        self.assertEqual(clean("data\u200bbase\t\u00a0\ufeffskills"), "database skills")
        self.assertEqual(clean("Dean\u2019s\u00ad List"), "Dean's List")

    def test_range_separators(self):
        for separator in (" - ", "\u2011", "\u2014", "\u2212", " to ", " TO ", " through "):
            with self.subTest(separator=separator):
                self.assertEqual(clean(f"20{separator}40%"), "20-40%")


class TestSpanExists(unittest.TestCase):
    def test_exact_words(self):
        self.assertTrue(span_exists("reduced page load time by 30%", SOURCE))

    def test_ignores_capitals_and_extra_spaces(self):
        self.assertTrue(span_exists("Helped  MIGRATE weekly\nreports", SOURCE))

    def test_one_changed_word(self):
        self.assertFalse(span_exists("Led migrate weekly reports", SOURCE))

    def test_number_not_in_source(self):
        self.assertFalse(span_exists("40%", SOURCE))

    def test_whole_words_only(self):
        self.assertTrue(span_exists("led", "Led a team of 3."))
        self.assertTrue(span_exists("C++", "Used C++ daily"))
        self.assertFalse(span_exists("led", "Scheduled weekly meetings"))
        self.assertFalse(span_exists("c", "Used C# and C++ daily"))
        self.assertFalse(span_exists("js", "Built it with Node.js"))

    def test_whole_numbers_only(self):
        self.assertTrue(span_exists("$2,000", "Saved $2,000 a year"))
        self.assertFalse(span_exists("3", "Graduated in 2023"))
        self.assertFalse(span_exists("3", "GPA 3.6"))
        self.assertFalse(span_exists("5", "3-5 years"))
        self.assertFalse(span_exists("40%", "Grew sign-ups by 140%"))
        self.assertFalse(span_exists("40%", "Grew sign-ups by 20-40%"))
        self.assertFalse(span_exists("30", SOURCE))  # the resume says 30%, not 30
        self.assertFalse(span_exists("5", "Cut time by .5 seconds"))
        self.assertFalse(span_exists("5", "The reading was -5"))
        self.assertFalse(span_exists("5", "The reading was +5"))
        self.assertFalse(span_exists("40", "Cut time by 40 percent"))
        self.assertFalse(span_exists("40%", "Cut time by 20 to 40%"))
        self.assertFalse(span_exists("40%", "Cut time by between 20 and 40%"))

    def test_pdf_characters(self):
        self.assertTrue(span_exists("Dean's List", "Dean’s List"))
        self.assertTrue(span_exists("2020-2021", "2020–2021"))
        self.assertTrue(span_exists("café", "café"))
        self.assertTrue(span_exists("database", "data​base"))

    def test_part_of_a_larger_amount(self):
        self.assertFalse(span_exists("$5M", "Managed $3M-$5M budgets"))
        self.assertFalse(span_exists("5k", "Handled 3k-5k requests"))
        self.assertFalse(span_exists("5", "Produced 5 dozen reports"))
        self.assertTrue(span_exists("$5M", "Managed $5M budgets"))
        for span, source in (("500", "Served 500 + users"), ("40", "Reduced costs by 40 %"),
                             ("5k", "Handled 3k to 5k requests"), ("$5M", "Managed $3M to $5M budgets"),
                             ("$5M+", "Managed $3M-$5M+ budgets")):
            with self.subTest(span=span, source=source):
                self.assertFalse(span_exists(span, source))

    def test_empty_or_punctuation_span(self):
        self.assertFalse(span_exists("", SOURCE))
        self.assertFalse(span_exists("   ", SOURCE))
        self.assertFalse(span_exists("...", SOURCE))


class TestFindNumbers(unittest.TestCase):
    def test_units_magnitudes_and_number_words(self):
        cases = {
            "Served 5k customers and 5 million users": ["5000", "5000000"],
            "Raised $5M and made queries 10x faster": ["$5000000", "10x"],
            "Cut time by forty percent and .5 seconds": ["40%", "0.5"],
            "Worked with ten people, then 3, then twenty-five": ["10", "3", "25"],
            "Fixed dozens of bugs": ["dozens"],
            "Counted one hundred and twenty-five records": ["125"],
            "Processed one thousand five hundred records": ["1500"],
            "Served 5 hundred users": ["500"],
            "Served a hundred users, then a thousand": ["100", "1000"],
            "Saved $2,000.50": ["$2000.5"],
            "Reduced time by 20% to 40%": ["20-40%"],
            "Counted three to five people": ["3-5"],
            "Counted between three and five people": ["3-5"],
            "Reduced time by between 20 and 40%": ["20-40%"],
            "Reduced time by 20 through 40 percent": ["20-40%"],
            "Served 2FA, S3, EC2, HTML5 and Python3 users": [],
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(find_numbers(text), expected)

    def test_long_amounts_do_not_round_to_the_same_claim(self):
        first = "1234567890123456789012345678901"
        second = "1234567890123456789012345678902"
        self.assertEqual(find_numbers(first), [first])
        self.assertNotEqual(find_numbers(first), find_numbers(second))

    def test_checklist_examples(self):
        self.assertEqual(find_numbers("cut costs by 40%"), ["40%"])
        self.assertEqual(find_numbers("saved $2,000"), ["$2000"])
        self.assertEqual(find_numbers("a team of 3."), ["3"])

    def test_every_number_in_order(self):
        self.assertEqual(find_numbers("GPA 3.6, class of 2023, 3 interns"), ["3.6", "2023", "3"])

    def test_a_range_is_one_number(self):
        # Otherwise "40%" would look backed by a resume that only says "20-40%".
        self.assertEqual(find_numbers("cut time by 20-40%"), ["20-40%"])
        self.assertEqual(find_numbers("tutored 20–30 students"), ["20-30"])  # PDF en dash

    def test_names_with_digits_are_not_numbers(self):
        self.assertEqual(find_numbers("Stored files in S3 and ran EC2 jobs with Python3"), [])

    def test_plus_amounts_and_places_are_numbers(self):
        # Otherwise an invented "500+ users" or "1st place" would have nothing to check.
        self.assertEqual(find_numbers("Served 500+ users and 10,000+ rows"), ["500+", "10000+"])
        self.assertEqual(find_numbers("Raised $5k+"), ["$5000+"])
        self.assertNotEqual(find_numbers("500+ users"), find_numbers("500 users"))
        self.assertEqual(find_numbers("Won 1st place, then 2nd"), ["1st", "2nd"])

    def test_currency_ranges_and_spaced_plus(self):
        # A changed currency, or a range written two ways, must not decide the label.
        pound, euro = "Saved \u00a35000", "Saved \u20ac5000"
        self.assertEqual(len({str(find_numbers(t)) for t in (pound, euro, "Saved $5000")}), 3)
        self.assertEqual(find_numbers("Handled 3-5k and 3k-5k requests"), ["3000-5000", "3000-5000"])
        self.assertNotEqual(find_numbers("3-5k"), find_numbers("3-5000"))
        self.assertEqual(find_numbers("Managed $3-5M"), find_numbers("Managed $3M-$5M"))
        self.assertEqual(find_numbers("Served 500 + users"), ["500+"])
        self.assertEqual(find_numbers("Saved \u20ac 5,000"), ["\u20ac5000"])
        self.assertEqual(find_numbers("Managed 3-5 hundred volunteers"), ["300-500"])
        self.assertEqual(find_numbers("three to five million"), find_numbers("3 to 5 million"))
        self.assertEqual(find_numbers("Cut costs by 20 per cent"), ["20%"])
        self.assertEqual(find_numbers("Handled 3k to 5k requests"), ["3000-5000"])

    def test_a_lone_one_is_a_word(self):
        # "one of the first" and "one-click" don't claim a count; compound numbers still do.
        self.assertEqual(find_numbers("Built one of the first one-click forms"), [])
        self.assertEqual(find_numbers("one hundred users, twenty-one people"), ["100", "21"])

    def test_range_cleanup_is_shared(self):
        for separator in (" - ", "\u2011", "\u2014", "\u2212", " to "):
            with self.subTest(separator=separator):
                self.assertEqual(find_numbers(f"Cut time by 20{separator}40%"), ["20-40%"])
                self.assertFalse(span_exists("40%", f"Cut time by 20{separator}40%"))


    def test_rare_ranges_and_spelled_plus(self):
        for text, expected in (("Packed 3-5 dozen orders per shift", ["36-60"]),
                               ("Reached two to three hundred thousand users", ["200000-300000"]),
                               ("Ranked 1st-3rd in regional competitions", ["1st-3rd"]),
                               ("Placed 1st to 3rd", ["1st-3rd"]),
                               ("Served 500-plus users", ["500+"]),
                               ("Served 500 Plus users", ["500+"]),
                               ("Served 500 + users", ["500+"])):
            with self.subTest(text=text):
                self.assertEqual(find_numbers(text), expected)
        self.assertNotEqual(find_numbers("3-5 dozen"), find_numbers("3-60"))
        self.assertEqual(find_numbers("3 to five hundred thousand"), ["300000-500000"])
        self.assertTrue(span_exists("500+", "Served 500 + users"))
        self.assertFalse(span_exists("500", "Served 500-plus users"))
        for text, expected in (("Brought five-plus years of retail experience", ["5+"]),
                               ("Raised $5 million-plus", ["$5000000+"]),
                               ("Managed budgets of two hundred to three hundred thousand", ["200000-300000"]),
                               ("Managed two hundred to three hundred volunteers", ["200-300"]),
                               ("Maintained 100 plus-size clothing listings", ["100"])):
            with self.subTest(text=text):
                self.assertEqual(find_numbers(text), expected)
        self.assertEqual(clean("Maintained 100 plus-size listings"), "Maintained 100 plus-size listings")


class TestFindScopeWords(unittest.TestCase):
    def test_verb_forms_and_co_led(self):
        for word, name in (("Lead", "led"), ("leads", "led"), ("leading", "led"),
                           ("managing", "managed"), ("Oversaw", "oversaw"),
                           ("overseeing", "oversaw"), ("Headed", "headed")):
            with self.subTest(word=word):
                self.assertEqual(find_scope_words(f"{word} the project"), {name})
        self.assertEqual(find_scope_words("Co-led and co-leading the project"), set())
        self.assertEqual(find_scope_words("Used design patterns in my own project"), set())

    def test_finds_scope_verbs(self):
        self.assertEqual(find_scope_words("Led a team"), {"led"})
        self.assertEqual(find_scope_words("Designed and owned the API"), {"designed", "owned"})

    def test_weaker_verbs_give_nothing(self):
        self.assertEqual(find_scope_words("Helped the team"), set())

    def test_whole_words_only(self):
        self.assertEqual(find_scope_words("Handled tickets"), set())
        self.assertEqual(find_scope_words("Scheduled meetings"), set())



class TestFindTitles(unittest.TestCase):
    def test_hyphenated_title_stays_whole(self):
        # "co-founder" is its own claim, so "Founder" isn't backed by it.
        self.assertEqual(find_titles("Co-founder of a campus club"), {"co-founder"})
        self.assertNotEqual(find_titles("Founder"), find_titles("Co-founder"))

    def test_titles_at_the_start_and_in_lowercase(self):
        self.assertEqual(find_titles("Supervisor at the campus office"), {"supervisor"})
        self.assertEqual(find_titles("worked as software engineer"), {"engineer"})
        self.assertEqual(find_titles("Worked with engineers and interned"), set())
