"""Lane 5 tests: synonyms.json, normalize() and split_resume().

Run from the repo root:  python -m unittest discover ai/tests -v
"""

import re
import unittest
from pathlib import Path

from ai.matching.normalize import SYNONYMS, normalize
from ai.matching.units import split_resume

# Lane 2's sample resume, and the text the PDF parser pulls out of alex.pdf.
RESUMES = Path(__file__).resolve().parents[1] / "fixtures" / "resumes"
ALEX_PATH = RESUMES / "alex.txt"
ALEX_PARSED_PATH = RESUMES / "alex_parsed.txt"


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

    def test_dash_without_space_is_not_a_marker(self):
        # "-5" is a number, not a bullet marker, so the "-" stays in the text.
        # (With no markers in the resume, the line is still a plain bullet.)
        units = split_resume("EXPERIENCE\n-5 degrees outside\n")
        self.assertEqual([u["text"] for u in units], ["-5 degrees outside"])

    def test_empty_resume_has_no_units(self):
        self.assertEqual(split_resume(""), [])

    def test_technical_skills_is_the_skills_section(self):
        units = split_resume("TECHNICAL SKILLS\nPython, SQL\n")
        self.assertEqual(units, [
            {"id": "u1", "section": "skills", "text": "Python, SQL", "start": 17, "end": 28},
        ])

    def test_all_caps_company_name_is_not_a_heading(self):
        units = split_resume("EXPERIENCE\nGOOGLE\n- Built Python tools\n")
        self.assertEqual(units, [
            {"id": "u1", "section": "experience", "text": "Built Python tools", "start": 20, "end": 38},
        ])

    def test_heading_with_colon_or_extra_spaces_still_counts(self):
        for heading in ["Skills:", "SKILLS:", "TECHNICAL  SKILLS", "Technical Skills"]:
            with self.subTest(heading=heading):
                units = split_resume(heading + "\nPython, SQL\n")
                self.assertEqual(len(units), 1)
                self.assertEqual(units[0]["section"], "skills")
                self.assertEqual(units[0]["text"], "Python, SQL")


class TestHeadings(unittest.TestCase):
    """Headings are found by their last word, so real resumes' many names work."""

    def test_heading_names_from_real_resumes(self):
        cases = {
            "NURSING EXPERIENCE": "experience",
            "ACADEMIC EXPERIENCE": "experience",
            "Volunteer Experience": "experience",
            "RESEARCH & PROJECTS": "projects",
            "SOFTWARE": "skills",
            "PERSONAL SKILLS": "skills",
            "CORE COMPETENCIES": "skills",
            "Technical Skills:": "skills",
            "Licenses & Certifications": "certifications",
            "Honors and Awards": "awards",
        }
        for heading, section in cases.items():
            with self.subTest(heading=heading):
                units = split_resume(heading + "\n- Built a CLI tool.\n")
                self.assertEqual(units[0]["section"], section)

    def test_projects_heading_right_after_skills_ends_the_skills(self):
        resume = "SKILLS\nPython, SQL\nRESEARCH & PROJECTS\nBuilt a resume parser.\n"
        units = split_resume(resume)
        self.assertEqual([(u["section"], u["text"]) for u in units], [
            ("skills", "Python, SQL"),
            ("projects", "Built a resume parser."),
        ])

    def test_summary_after_skills_is_not_more_skills(self):
        resume = "SKILLS\nPython, SQL\nPROFESSIONAL SUMMARY\nHard-working student\n"
        units = split_resume(resume)
        self.assertEqual([u["text"] for u in units], ["Python, SQL"])

    def test_lines_that_are_not_headings(self):
        # A job title ends in "Engineer", not a section word, and GOOGLE has no
        # section word, so neither changes the section of the bullet after them.
        resume = ("EXPERIENCE\n"
                  "SOFTWARE ENGINEER INTERN\n"
                  "Software Engineer\n"
                  "GOOGLE\n"
                  "- Built a CLI tool.\n")
        units = split_resume(resume)
        self.assertEqual([(u["section"], u["text"]) for u in units], [
            ("experience", "Built a CLI tool."),
        ])

    def test_sentence_with_a_section_word_is_not_a_heading(self):
        # Not Title Case, so it's a bullet, not a heading that starts "experience".
        resume = "PROJECTS\nGained experience in sales\n"
        units = split_resume(resume)
        self.assertEqual([(u["section"], u["text"]) for u in units], [
            ("projects", "Gained experience in sales"),
        ])

    def test_skills_line_with_section_words_is_still_skills(self):
        resume = "SKILLS\nSoftware testing, project planning\n"
        units = split_resume(resume)
        self.assertEqual(units[0]["text"], "Software testing, project planning")


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


# ================== split_resume() on real PDF text ======================

class TestSplitResumePdfText(unittest.TestCase):
    """Made-up lines that look like what the PDF parser gives back."""

    def test_plain_lines_under_experience_are_bullets(self):
        resume = "EXPERIENCE\nBuilt a REST API in Python.\nFixed 12 bugs.\n"
        self.assertEqual(split_resume(resume), [
            {"id": "u1", "section": "experience", "text": "Built a REST API in Python.", "start": 11, "end": 38},
            {"id": "u2", "section": "experience", "text": "Fixed 12 bugs.", "start": 39, "end": 53},
        ])

    def test_job_and_project_headers_are_not_bullets(self):
        resume = ("EXPERIENCE\n"
                  "Junior Web Developer, Oakline Print Shop, Jan 2026 - Present\n"
                  "Fixed 12 bugs.\n"
                  "PROJECTS\n"
                  "Weather Dashboard (JavaScript, HTML, CSS), Jun 2025\n"
                  "Added a dark mode toggle.\n")
        texts = [u["text"] for u in split_resume(resume)]
        self.assertEqual(texts, ["Fixed 12 bugs.", "Added a dark mode toggle."])

    def test_education_lines_are_not_bullets(self):
        resume = "EDUCATION\nGPA 3.6; Dean's List\nRelevant coursework: Databases\n"
        self.assertEqual(split_resume(resume), [])

    def test_wrapped_bullet_is_joined_with_its_line_break(self):
        resume = ("EXPERIENCE\n"
                  "Rebuilt the order form and reduced page\n"
                  "load time by 30%.\n"
                  "Fixed 12 bugs.\n")
        units = split_resume(resume)
        self.assertEqual(units[0]["text"], "Rebuilt the order form and reduced page\nload time by 30%.")
        self.assertEqual(resume[units[0]["start"]:units[0]["end"]], units[0]["text"])
        self.assertEqual(units[1]["text"], "Fixed 12 bugs.")

    def test_finished_bullet_does_not_take_the_next_line(self):
        # The first bullet ends with a period, so "built" starts a new bullet
        # even though it's lowercase.
        resume = "EXPERIENCE\nFixed 12 bugs.\nbuilt a CLI tool\n"
        texts = [u["text"] for u in split_resume(resume)]
        self.assertEqual(texts, ["Fixed 12 bugs.", "built a CLI tool"])

    def test_capitalized_line_after_unfinished_bullet_is_a_new_bullet(self):
        # Many resumes leave off the period, so a capital letter starts a new one.
        resume = "EXPERIENCE\nFixed 12 bugs\nBuilt a CLI tool\n"
        texts = [u["text"] for u in split_resume(resume)]
        self.assertEqual(texts, ["Fixed 12 bugs", "Built a CLI tool"])

    def test_dot_bullets_from_pdfs(self):
        for marker in ["\u2022", "\u2013", "\u25aa", "*"]:
            with self.subTest(marker=marker):
                resume = f"EXPERIENCE\n{marker} Built a REST API\n"
                units = split_resume(resume)
                self.assertEqual(units, [
                    {"id": "u1", "section": "experience", "text": "Built a REST API", "start": 13, "end": 29},
                ])

    def test_two_line_skills_stay_one_unit(self):
        resume = "SKILLS\nPython, SQL\nAWS, Docker\n"
        self.assertEqual(split_resume(resume), [
            {"id": "u1", "section": "skills", "text": "Python, SQL\nAWS, Docker", "start": 7, "end": 30},
        ])

    def test_skills_end_at_the_next_heading(self):
        resume = "SKILLS\nPython, SQL\nAWS\nPROJECTS\nBuilt a CLI tool.\n"
        units = split_resume(resume)
        self.assertEqual([u["text"] for u in units], ["Python, SQL\nAWS", "Built a CLI tool."])

    def test_trailing_spaces_are_not_part_of_a_unit(self):
        resume = "EXPERIENCE\nFixed 12 bugs.   \nSKILLS\nPython, SQL  \n"
        self.assertEqual(split_resume(resume), [
            {"id": "u1", "section": "experience", "text": "Fixed 12 bugs.", "start": 11, "end": 25},
            {"id": "u2", "section": "skills", "text": "Python, SQL", "start": 36, "end": 47},
        ])

    def test_indented_skills_line(self):
        resume = "SKILLS\n    Python, SQL\n"
        self.assertEqual(split_resume(resume), [
            {"id": "u1", "section": "skills", "text": "Python, SQL", "start": 11, "end": 22},
        ])

    def test_windows_line_breaks_in_a_wrapped_bullet(self):
        resume = "EXPERIENCE\r\nRebuilt the order form and\r\ncut load time.\r\n"
        units = split_resume(resume)
        self.assertEqual(units[0]["text"], "Rebuilt the order form and\r\ncut load time.")
        self.assertEqual(resume[units[0]["start"]:units[0]["end"]], units[0]["text"])

    def test_line_of_invisible_characters_is_blank(self):
        resume = "EXPERIENCE\nRebuilt the order form and\n\u200b\ncut load time.\n"
        texts = [u["text"] for u in split_resume(resume)]
        self.assertEqual(texts, ["Rebuilt the order form and", "cut load time."])


class TestSplitResumeOnAlexParsed(unittest.TestCase):
    """alex_parsed.txt: exactly what the PDF parser gives back for alex.pdf."""

    def setUp(self):
        self.resume = ALEX_PARSED_PATH.read_text(encoding="utf-8")
        self.units = split_resume(self.resume)

    def test_same_16_units_as_alex_txt(self):
        # Same bullets in the same order; only the line breaks inside differ.
        from_txt = split_resume(ALEX_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(self.units), 16)
        self.assertEqual(
            [(u["section"], " ".join(u["text"].split())) for u in self.units],
            [(u["section"], " ".join(u["text"].split())) for u in from_txt],
        )

    def test_every_unit_slices_back_to_its_text(self):
        for u in self.units:
            with self.subTest(id=u["id"]):
                self.assertEqual(self.resume[u["start"]:u["end"]], u["text"])

    def test_wrapped_bullet_keeps_its_second_line(self):
        first = self.units[0]
        self.assertTrue(first["text"].startswith("Rebuilt the online order form"))
        self.assertTrue(first["text"].endswith("splitting code."))

    def test_aws_lambda_stays_in_one_skills_unit(self):
        skills = [u for u in self.units if u["section"] == "skills"]
        self.assertEqual(len(skills), 1)
        # Line breaks are "\n" or "\r\n" depending on the computer, so compare words.
        self.assertIn("AWS Lambda, Linux", " ".join(skills[0]["text"].split()))

    def test_job_and_project_headers_are_left_out(self):
        texts = " ".join(u["text"] for u in self.units)
        self.assertNotIn("Oakline Print Shop", texts)
        self.assertNotIn("Weather Dashboard", texts)


if __name__ == "__main__":
    unittest.main()