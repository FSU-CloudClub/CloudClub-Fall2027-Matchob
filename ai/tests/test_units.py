"""Lane 5 tests: synonyms.json and normalize().

Run from the repo root:  python -m unittest discover ai/tests -v
"""

import re
import unittest

from ai.matching.normalize import SYNONYMS, normalize


class TestNormalize(unittest.TestCase):

    # --- The three cases from the task checklist ---

    def test_alias_is_replaced(self):
        self.assertEqual(normalize("Built JS apps"), "built javascript apps")

    def test_multi_word_alias_is_replaced(self):
        self.assertEqual(normalize("AWS Lambda"), "lambda")

    def test_alias_inside_a_word_is_left_alone(self):
        self.assertEqual(normalize("JSON"), "json")

    # --- More cases: each pair is (input, expected output) ---

    def test_more_cases(self):
        cases = [
            # Longest alias wins, so "node.js" never becomes "node.javascript"
            ("Built Node.js apps", "built node apps"),
            ("React JS and React.js", "react and react"),
            ("Google Cloud Platform", "gcp"),
            ("Mongo DB and MongoDB", "mongo and mongo"),
            ("Continuous Integration/Continuous Deployment", "ci/cd"),
            # Punctuation and position in the sentence don't matter
            ("Experience with JS, TypeScript.", "experience with javascript, typescript."),
            ("JS", "javascript"),
            ("Amazon S3 and AWS EC2", "s3 and ec2"),
            # Ordinary words and look-alikes stay untouched
            ("TS/SCI clearance required", "ts/sci clearance required"),
            ("Go to market", "go to market"),
            ("", ""),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(normalize(text), expected)

    def test_running_twice_changes_nothing(self):
        once = normalize("Built Node.js apps on AWS Lambda with PostgreSQL")
        self.assertEqual(normalize(once), once)


class TestSynonymsFile(unittest.TestCase):
    """Checks on synonyms.json itself, so future edits can't break normalize."""

    def test_everything_is_lowercase(self):
        for name, aliases in SYNONYMS.items():
            self.assertEqual(name, name.lower())
            for alias in aliases:
                self.assertEqual(alias, alias.lower())

    def test_no_alias_is_listed_twice_or_is_also_a_name(self):
        seen = set()
        for aliases in SYNONYMS.values():
            for alias in aliases:
                self.assertNotIn(alias, seen, f"{alias!r} is listed more than once")
                self.assertNotIn(alias, SYNONYMS, f"{alias!r} is also a standard name")
                seen.add(alias)

    def test_aliases_start_and_end_with_a_letter_or_number(self):
        # The \b whole-word rule only works next to letters and numbers,
        # which is why C++ and C# are left out.
        for aliases in SYNONYMS.values():
            for alias in aliases:
                self.assertTrue(alias[0].isalnum() and alias[-1].isalnum(), alias)

    def test_no_standard_name_contains_an_alias(self):
        # If a name contained an alias, a later replacement would mangle it.
        # Example: a name "node.js" would become "node.javascript".
        for name in SYNONYMS:
            for aliases in SYNONYMS.values():
                for alias in aliases:
                    found = re.search(r"\b" + re.escape(alias) + r"\b", name)
                    self.assertIsNone(found, f"name {name!r} contains alias {alias!r}")


if __name__ == "__main__":
    unittest.main()