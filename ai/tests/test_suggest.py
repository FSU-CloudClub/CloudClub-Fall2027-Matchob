
"""Unit tests using a fake model; no Bedrock access needed."""

import json
import unittest

from ai.suggest import suggest


REQUIREMENTS = [
    {"id": "req-1", "text": "React UI"},
    {"id": "req-2", "text": "Terraform"},
]

LINES = {
    "req-1": ["Built a React dashboard."],
    "req-2": [],
}


class TestSuggest(unittest.TestCase):

    # Verify one model call returns a result for every job requirement.
    def test_one_call_and_one_result_per_requirement(self):
        calls = []

        def fake_model(prompt):
            calls.append(prompt)
            return json.dumps([
                {
                    "requirement_id": "req-1",
                    "match": "matched",
                    "original_bullet": "Built a React dashboard.",
                    "suggestion": "Built a dashboard using React.",
                    "reason": "Highlights React experience."
                },
                {
                    "requirement_id": "req-2",
                    "match": "missing",
                    "original_bullet": "",
                    "suggestion": "",
                    "reason": "No matching bullet."
                },
            ])

        output = suggest(REQUIREMENTS, LINES, fake_model)

        self.assertEqual(len(calls), 1)
        self.assertEqual(
            [r["requirement_id"] for r in output],
            ["req-1", "req-2"]
        )
        self.assertTrue(
            all(r["prompt_version"] == "v1" for r in output)
        )
        self.assertNotIn("status", output[0])
        self.assertEqual(output[1]["suggestion"], "")

    # Ensure invalid model responses raise ValueError.
    def test_invalid_json_raises_value_error(self):
        with self.assertRaises(ValueError):
            suggest(REQUIREMENTS, LINES, lambda prompt: "not JSON")

    # Verify JSON wrapped in Markdown code fences is accepted.
    def test_json_code_fences_accepted(self):
        response = json.dumps([
            {
                "requirement_id": "req-1",
                "match": "missing",
                "original_bullet": "",
                "suggestion": "",
                "reason": "No match"
            },
            {
                "requirement_id": "req-2",
                "match": "missing",
                "original_bullet": "",
                "suggestion": "",
                "reason": "No match"
            },
        ])

        output = suggest(
            REQUIREMENTS,
            LINES,
            lambda _: f"```json\n{response}\n```"
        )
        self.assertEqual(len(output), 2)

    # Reject incorrectly typed match values instead of crashing.
    def test_bad_match_type_raises_value_error(self):
        bad = [
            {
                "requirement_id": "req-1",
                "match": ["matched"],
                "original_bullet": "Built a React dashboard.",
                "suggestion": "Built a React dashboard.",
                "reason": "Match"
            },
            {
                "requirement_id": "req-2",
                "match": "missing",
                "original_bullet": "",
                "suggestion": "",
                "reason": "No match"
            },
        ]

        with self.assertRaises(ValueError):
            suggest(REQUIREMENTS, LINES, lambda _: json.dumps(bad))

    # Ensure unresolved resume unit IDs cannot replace actual bullet text.
    def test_rejects_unit_ids_instead_of_bullet_text(self):
        with self.assertRaisesRegex(ValueError, "unit IDs"):
            suggest(
                REQUIREMENTS,
                {"req-1": ["u3"]},
                lambda _: "[]"
            )


if __name__ == "__main__":
    unittest.main()
