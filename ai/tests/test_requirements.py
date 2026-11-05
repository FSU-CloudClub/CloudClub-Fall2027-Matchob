"""Tests for ai.extraction.requirements, using a fake model (no real model calls)."""

import json
import unittest
from pathlib import Path

from ai.extraction.requirements import extract_requirements

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "jobs" / "job-01-frontend-intern.txt"


def _req(n, text, category, priority, start, end):
    return {
        "id": f"req-{n}",
        "text": text,
        "category": category,
        "priority": priority,
        "source_span": {"start": start, "end": end, "text": text},
    }


# A ready-made reply for job-01-frontend-intern.txt. Offsets are into that file.
JOB_01_REQUIREMENTS = [
    _req(1, "building user interfaces with React", "skill", "must", 260, 295),
    _req(2, "write clean, readable JavaScript", "skill", "must", 306, 338),
    _req(3, "Git for version control", "tool", "must", 358, 381),
    _req(4, "communication skills when working on a team", "skill", "must", 391, 434),
    _req(5, "TypeScript", "tool", "nice", 467, 477),
    _req(6, "Jest", "tool", "nice", 516, 520),
    _req(7, "accessibility best practices", "skill", "nice", 540, 568),
]


def make_fake_model(reply):
    """A stand-in for the real model: records what it was sent, returns `reply`."""
    calls = []

    def fake_model(system, user):
        calls.append((system, user))
        return reply

    fake_model.calls = calls
    return fake_model


class ExtractRequirementsTests(unittest.TestCase):
    def test_returns_requirements_from_the_models_reply(self):
        job_text = FIXTURE.read_text(encoding="utf-8")
        model = make_fake_model(json.dumps({"requirements": JOB_01_REQUIREMENTS}))

        result = extract_requirements(job_text, model)

        self.assertEqual(result, JOB_01_REQUIREMENTS)
        # The offsets in the ready-made reply still point at the right text in the fixture.
        for req in result:
            with self.subTest(id=req["id"]):
                span = req["source_span"]
                self.assertEqual(job_text[span["start"] : span["end"]], span["text"])
                self.assertEqual(span["text"], req["text"])

        # The model got the prompt's system message, and the posting pasted into the user message.
        self.assertEqual(len(model.calls), 1)
        system, user = model.calls[0]
        self.assertTrue(system.startswith("You extract hiring requirements"))
        self.assertIn(job_text, user)
        self.assertNotIn("{{JOB_TEXT}}", user)

    def test_raises_value_error_when_the_reply_is_not_json(self):
        model = make_fake_model("Sorry, I can't pull requirements out of that.")

        with self.assertRaises(ValueError):
            extract_requirements("Some job posting", model)


if __name__ == "__main__":
    unittest.main()