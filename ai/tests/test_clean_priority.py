import unittest

from ai.extraction.clean import clean_posting
from ai.extraction.priority import priority    

class TestCleanPosting(unittest.TestCase):
    def test_priority_inherits_heading_and_resets_at_next_section(self):
        posting = (
            "Python experience\n"
            "Preferred Qualifications:\n"
            "- Experience with Terraform\n"
            "- Experience with AWS\n"
            "Benefits:\nWe offer:\n- Health insurance\n- 401(k) matching\n"
            "Required Qualifications:\n"
            "- Experience with SQL"
        )
        cleaned = clean_posting(posting)
        self.assertEqual([line["text"] for line in cleaned], [
            "Python experience",
            "Preferred Qualifications:",
            "- Experience with Terraform",
            "- Experience with AWS",
            "Required Qualifications:",
            "- Experience with SQL",
        ])
        self.assertEqual(
            [priority(line["text"], line["heading"]) for line in cleaned],
            ["must", "nice", "nice", "nice", "must", "must"],
        )
        for line in cleaned:
            self.assertEqual(posting[line["start"]:line["end"]], line["text"])
        self.assertEqual(clean_posting("Python")[0]["heading"], "")

    def test_preferred_qualifications_posting(self):
        posting = "Preferred Qualifications: \n- Experience with Terraform"
        cleaned = clean_posting(posting)

        self.assertEqual([line["text"] for line in cleaned], [
            "Preferred Qualifications:",
            "- Experience with Terraform",
        ])
        for line in cleaned:
            self.assertEqual(posting[line["start"]:line["end"]], line["text"])

    def test_benefits_with_inline_description(self):
        posting = "Benefits: We offer: \n- Health insurance \n- 401(k) matching"
        self.assertEqual(clean_posting(posting), [])

    def test_benefits_with_multiline_description(self):
        for posting in [
            "Benefits:\nWe offer:\n- Health insurance\n- 401(k) matching",
            "Benefits: \nWe offer: \n- Health insurance \n- 401(k) matching",
        ]:
            with self.subTest(posting=posting):
                self.assertEqual(clean_posting(posting), [])

    def test_clean_posting(self):
        posting = "\n".join([
            "About us",
            "We build software for cafés.",
            "",
            "We work around the world.",
            "Requirements:",
            "  Must have: Python  ",
            "Experience with Go is a plus",
            "",
            "Benefits:",
            "Health insurance and paid leave.",
            "",
            "Free lunches.",
            "Preferred qualifications:",
            "\tPreferred: AWS",
        ])

        cleaned_posting = clean_posting(posting)

        """ 
        Check that the cleaned posting contains the expected lines
        and that their start and end positions match the original text.
        """
        self.assertEqual([line["text"] for line in cleaned_posting], [
            "Requirements:",
            "Must have: Python",
            "Experience with Go is a plus",
            "Preferred qualifications:",
            "Preferred: AWS",
        ])
        for line in cleaned_posting:
            self.assertEqual(posting[line["start"]:line["end"]], line["text"])

class TestPriority(unittest.TestCase):
    """
    Test the priority function with a sample job posting 
    containing various headings and lines, including those that should
    be skipped and those that should be kept. The test checks that the
    cleaned posting contains the expected lines and that their start and
    end positions match the original text.
    """
    def test_priority(self):
        self.assertEqual(priority("Experience with Go is a plus"), "nice")
        self.assertEqual(priority("Preferred: AWS"), "nice")
        self.assertEqual(priority("Must have: Python"), "must")

    def test_preferred_qualifications_multiline(self):
        posting = "Preferred Qualifications:\n- Experience with Terraform"
        self.assertEqual(priority(posting), "nice")