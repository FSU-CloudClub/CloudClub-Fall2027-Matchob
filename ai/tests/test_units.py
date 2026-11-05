"""Lane 5 tests: synonyms.json, normalize() and split_resume().

Run from the repo root:  python -m unittest discover ai/tests -v
"""

import re
import unittest
from pathlib import Path

from ai.matching.normalize import SYNONYMS, normalize
from ai.matching.units import split_resume

# Lane 2's sample resume (from noah/fake-resumes-and-mocks).
ALEX_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "resumes" / "alex.txt"


# ===================== normalize() and synonyms.json =====================

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
           # Longest alias wins, so "google cloud platform" never becomes "gcp platform"
            ("Built Node.js apps", "built node apps"),
            ("React JS and React.js", "react and react"),
            ("Google Cloud Platform", "gcp"),
            ("Mongo DB and MongoDB", "mongo and mongo"),
            ("Continuous Integration/Continuous Deployment", "ci/cd"),
            # Punctuation and position in the sentence don't matter
            ("Experience with JS, TypeScript.", "experience with javascript, typescript."),
            ("JS", "javascript"),
            ("Amazon S3 and AWS EC2", "s3 and ec2"),
            # The same alias twice, and both DynamoDB spellings
            ("JS and JS", "javascript and javascript"),
            ("AWS Dynamo DB", "dynamodb"),
            ("AWS DynamoDB", "dynamodb"),
            # Ordinary words and look-alikes stay untouched
            ("TS/SCI clearance required", "ts/sci clearance required"),
            ("Go to market", "go to market"),
            ("", ""),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(normalize(text), expected)

    def test_dot_names_are_left_alone(self):
        for text in ["Vue.js", "Next.js"]:
            with self.subTest(text=text):
                self.assertEqual(normalize(text), text.lower())

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
        # The whole-word rule only works when an alias starts and ends with a
        # letter or number, which is why C++ and C# are left out.
        for aliases in SYNONYMS.values():
            for alias in aliases:
                self.assertTrue(alias[0].isalnum() and alias[-1].isalnum(), alias)

    def test_no_standard_name_contains_an_alias(self):
        # If a name contained an alias, a later replacement would mangle it
         # Example: a name "react js" would become "react javascript".
        for name in SYNONYMS:
            for aliases in SYNONYMS.values():
                for alias in aliases:
                    found = re.search(r"(?<![\w.])" + re.escape(alias) + r"(?!\w)", name)
                    self.assertIsNone(found, f"name {name!r} contains alias {alias!r}")


# ============================ split_resume() =============================

# A small made-up resume covering the tricky cases: an indented bullet with
# extra spaces, an empty "-" line, and a blank line between SKILLS and its line.
SAMPLE = """ALEX KIM
alex.kim@email.com | Tallahassee, FL

EXPERIENCE
Software Engineering Intern, Acme Corp | Summer 2026
- Built a REST API in Python
- Cut page load time by 40%

PROJECTS
  -   Wrote a resume parser
-

SKILLS

Python, AWS, SQL
"""


class TestSplitResume(unittest.TestCase):
    """Tests on the made-up SAMPLE resume above."""

    def test_finds_every_bullet_and_the_skills_line(self):
        texts = [u["text"] for u in split_resume(SAMPLE)]
        self.assertEqual(texts, [
            "Built a REST API in Python",
            "Cut page load time by 40%",
            "Wrote a resume parser",
            "Python, AWS, SQL",
        ])

    def test_units_get_their_section_and_numbered_ids(self):
        units = split_resume(SAMPLE)
        self.assertEqual([u["section"] for u in units],
                         ["experience", "experience", "projects", "skills"])
        self.assertEqual([u["id"] for u in units], ["u1", "u2", "u3", "u4"])

    def test_start_and_end_point_at_the_exact_text(self):
        for line_break in ["\n", "\r\n"]:  # Mac/Linux and Windows
            resume = SAMPLE.replace("\n", line_break)
            for u in split_resume(resume):
                with self.subTest(line_break=repr(line_break), id=u["id"]):
                    self.assertEqual(resume[u["start"]:u["end"]], u["text"])

    def test_all_caps_skills_line_is_not_a_heading(self):
        units = split_resume("SKILLS\nAWS, SQL, GCP\n")
        self.assertEqual(units, [
            {"id": "u1", "section": "skills", "text": "AWS, SQL, GCP", "start": 7, "end": 20},
        ])

    def test_empty_skills_section_does_not_swallow_next_heading(self):
        units = split_resume("SKILLS\n\nEXPERIENCE\n- Built Python tools\n")
        self.assertEqual(units, [
            {"id": "u1", "section": "experience", "text": "Built Python tools", "start": 21, "end": 39},
        ])

    def test_empty_bullet_does_not_steal_the_skills_line(self):
        units = split_resume("SKILLS\n- \nPython, SQL\n")
        self.assertEqual(units, [
            {"id": "u1", "section": "skills", "text": "Python, SQL", "start": 10, "end": 21},
        ])

    def test_dash_without_space_is_not_a_bullet(self):
        self.assertEqual(split_resume("EXPERIENCE\n-5 degrees outside\n"), [])

    def test_empty_resume_has_no_units(self):
        self.assertEqual(split_resume(""), [])


class TestSplitResumeOnAlex(unittest.TestCase):
    """The checklist tests on Lane 2's alex.txt."""

    def setUp(self):
        self.resume = ALEX_PATH.read_text(encoding="utf-8")
        self.units = split_resume(self.resume)

    def test_unit_count_is_bullets_plus_skills_line(self):
        # Count bullets with a simpler rule than split_resume, so the test checks it
        bullets = sum(1 for line in self.resume.splitlines() if line.lstrip().startswith("- "))
        self.assertEqual(len(self.units), bullets + 1)

    def test_every_unit_slices_back_to_its_text(self):
        for u in self.units:
            with self.subTest(id=u["id"]):
                self.assertEqual(self.resume[u["start"]:u["end"]], u["text"])

    def test_bullet_under_experience_has_experience_section(self):
        heading_at = self.resume.index("EXPERIENCE")
        first_after = next(u for u in self.units if u["start"] > heading_at)
        self.assertEqual(first_after["section"], "experience")


if __name__ == "__main__":
    unittest.main()