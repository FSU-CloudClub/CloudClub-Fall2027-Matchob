import json
import unittest
from pathlib import Path

from jsonschema import validate

AI = Path(__file__).parent.parent
CONTRACTS = AI / "contracts"
MOCK_DIR = AI / "fixtures" / "mock_responses"
MOCKS = sorted(MOCK_DIR.glob("*.json"))
ALEX = (AI / "fixtures" / "resumes" / "alex.txt").read_text()


def load(path):
    return json.loads(path.read_text())


def case(name):
    return load(MOCK_DIR / f"{name}.json")["recommendations"][0]


class TestMocks(unittest.TestCase):
    def test_all_mocks_present(self):
        self.assertEqual([p.stem for p in MOCKS], ["empty", "full_analysis", "missing",
                                                   "needs_confirmation", "supported", "unsupported"])

    # Once Lane 1's contract is merged, delete the skipUnless line below. While it's there, a missing or
    # renamed contract file makes this test say "skipped" forever instead of failing.
    @unittest.skipUnless((CONTRACTS / "analysis.schema.json").exists(), "Lane 1's contract isn't merged yet")
    def test_every_mock_matches_the_contract(self):
        schema = {n: load(CONTRACTS / f"{n}.schema.json") for n in ("analysis", "requirement", "recommendation")}
        for path in MOCKS:
            with self.subTest(mock=path.name):
                mock = load(path)
                validate(mock, schema["analysis"])
                for item in mock["requirements"]:
                    validate(item, schema["requirement"])
                for item in mock["recommendations"]:
                    validate(item, schema["recommendation"])

    # Mostly repeats test_positions_point_at_the_quoted_text. To cut it, move the non-empty evidence
    # check into test_labels_still_fit_the_resume and delete this test (-5 lines).
    def test_supported_quotes_the_resume_word_for_word(self):
        rec = case("supported")
        self.assertTrue(rec["evidence"])
        for ev in rec["evidence"]:
            self.assertIn(ev["text"], ALEX)

    def test_positions_point_at_the_quoted_text(self):
        for path in MOCKS:
            with self.subTest(mock=path.name):
                mock = load(path)
                self.assertEqual(mock["resume_text"], ALEX)
                for item in mock["requirements"]:
                    s = item["source_span"]
                    self.assertEqual(mock["job_text"][s["start"]:s["end"]], s["text"])
                for rec in mock["recommendations"]:
                    self.assertIn(rec["original_bullet"], ALEX)
                    for ev in rec["evidence"]:
                        self.assertEqual(mock["resume_text"][ev["start"]:ev["end"]], ev["text"])

    def test_every_suggestion_points_at_a_requirement(self):
        for path in MOCKS:
            with self.subTest(mock=path.name):
                mock = load(path)
                ids = [item["id"] for item in mock["requirements"]]
                self.assertEqual(len(ids), len(set(ids)))
                for rec in mock["recommendations"]:
                    self.assertIn(rec["requirement_id"], ids)

    def test_labels_still_fit_the_resume(self):
        # If alex.txt changes, these cases must still mean what their names say.
        for name in ("supported", "needs_confirmation", "unsupported"):
            self.assertEqual(case(name)["status"], name)
        self.assertIn("Led", case("needs_confirmation")["suggestion"])
        self.assertIn("Helped", case("needs_confirmation")["original_bullet"])
        self.assertNotRegex(ALEX.lower(), r"\bled\b")
        self.assertIn("Kubernetes", case("unsupported")["suggestion"])
        self.assertNotIn("kubernetes", ALEX.lower())
        self.assertNotIn("terraform", ALEX.lower())

    def test_missing_has_no_suggestion_or_evidence(self):
        rec = case("missing")
        self.assertEqual((rec["match"], rec["suggestion"], rec["evidence"]), ("missing", "", []))

    def test_empty_has_no_requirements_or_suggestions(self):
        mock = load(MOCK_DIR / "empty.json")
        self.assertEqual((mock["requirements"], mock["recommendations"]), ([], []))

    # The four single-case mocks are copies of parts of full_analysis.json, kept because Frontend
    # agreed to them. If Frontend only uses full_analysis.json, delete those four files and this test,
    # and point case() at full_analysis.json (about -140 lines).
    def test_full_analysis_has_every_case(self):
        full = load(MOCK_DIR / "full_analysis.json")["recommendations"]
        for name in ("supported", "needs_confirmation", "unsupported", "missing"):
            self.assertIn(case(name), full)
