import json
import unittest
from pathlib import Path

from jsonschema import ValidationError, validate

CONTRACTS = Path(__file__).parent.parent / "contracts"


def load(name):
    return json.loads((CONTRACTS / name).read_text())


GOOD = {"id": "req-1", "text": "Python", "category": "skill", "priority": "must",
        "source_span": {"start": 0, "end": 6, "text": "Python"}}

GOOD_REC = {
    "requirement_id": "req-1",
    "match": "matched",
    "original_bullet": "Built data pipelines in Python",
    "suggestion": "Built Python data pipelines processing 2M rows/day",
    "reason": "Resume already shows Python pipeline work",
    "status": "supported",
    "prompt_version": "v1",
    "evidence": [
        {"source": "resume", "start": 0, "end": 30,
         "text": "Built data pipelines in Python", "tier": "high"}
    ],
}


class TestContracts(unittest.TestCase):
    def test_good_requirement_passes(self):
        validate(GOOD, load("requirement.schema.json"))

    def test_bad_priority_fails(self):
        with self.assertRaises(ValidationError):
            validate({**GOOD, "priority": "maybe"}, load("requirement.schema.json"))

    def test_good_recommendation_passes(self):
        validate(GOOD_REC, load("recommendation.schema.json"))

    def test_bad_status_fails(self):
        with self.assertRaises(ValidationError):
            validate({**GOOD_REC, "status": "probably"},
                     load("recommendation.schema.json"))


if __name__ == "__main__":
    unittest.main() 