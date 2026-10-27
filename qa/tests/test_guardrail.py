"""Run with: pytest qa/tests

These tests check the harness itself, not the guardrail's score. A guardrail miss on our cases
is a finding to report, not a failing build, so misses show up in the harness report instead.
"""
from pathlib import Path

from qa.harness.run_cases import LABELS, load_cases, report, run

ROOT = Path(__file__).resolve().parents[2]
AI_CASES = ROOT / "ai" / "fixtures" / "adversarial" / "cases.json"
PRACTICE = ROOT / "qa" / "tricky_cases" / "tricky_cases_practice.json"


def test_harness_agrees_with_ai_team_cases():
    """The AI team's own 36 cases all pass their tests, so the harness must score them 100%."""
    rows = run(load_cases(AI_CASES))
    assert len(rows) == 36
    assert all(r["verdict"] == "correct" for r in rows), [r["name"] for r in rows if r["verdict"] != "correct"]


def test_every_row_has_a_valid_label_and_report_has_counts():
    rows = run(load_cases(AI_CASES))
    assert all(r["got"] in LABELS and r["expected"] in LABELS for r in rows)
    assert "of 36 correct" in report(rows, AI_CASES)


def test_practice_cases_run_if_present():
    """Practice cases live in qa/tricky_cases/ once Olivia's branch is merged."""
    if not PRACTICE.exists():
        import pytest
        pytest.skip("practice cases not on this branch yet")
    rows = run(load_cases(PRACTICE))
    print(report(rows, PRACTICE))
    assert rows
