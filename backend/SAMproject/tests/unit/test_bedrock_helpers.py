"""Suggestions helpers: validation, prompt variables and reply parsing; no AWS calls."""

import importlib
import sys
from unittest.mock import MagicMock

import pytest
from matchob_common.validators import validate_fields

VALID = {
    "resumeText": "Sarah Lee. CS student at FSU.",
    "jobDescription": {"title": "Backend Intern", "company": "Acme", "text": "Python, AWS."},
    "supportingContext": "Cloud club projects.",
}


@pytest.fixture
def helpers(monkeypatch):
    monkeypatch.setenv("PROMPT_ARN", "arn:aws:bedrock:us-east-1:123456789012:prompt/ABC:1")
    monkeypatch.setenv("GUARDRAIL_ID", "gr123")
    monkeypatch.setenv("GUARDRAIL_VERSION", "1")
    monkeypatch.setattr("boto3.client", MagicMock())
    monkeypatch.delitem(sys.modules, "bedrock_helpers", raising=False)
    return importlib.import_module("bedrock_helpers")


def fake_response(text, stop_reason="end_turn"):
    return {"stopReason": stop_reason, "output": {"message": {"content": [{"text": text}]}}}


def test_prompt_variables_with_every_field(helpers):
    fields, error = validate_fields(VALID, helpers.SUGGESTION_FIELDS, partial=False)
    assert error is None
    assert helpers.prompt_variables(fields) == {
        "resume": {"text": "Sarah Lee. CS student at FSU."},
        "job_title": {"text": "Backend Intern"},
        "company": {"text": "Acme"},
        "job_description": {"text": "Python, AWS."},
        "supporting_context": {"text": "Cloud club projects."},
    }


def test_prompt_variables_fills_missing_optional_fields(helpers):
    body = {"resumeText": "r", "jobDescription": {"title": "t", "text": "x"}}
    fields, error = validate_fields(body, helpers.SUGGESTION_FIELDS, partial=False)
    assert error is None
    variables = helpers.prompt_variables(fields)
    assert set(variables) == set(helpers.PROMPT_VARIABLES)
    assert variables["company"] == {"text": ""}
    assert variables["supporting_context"] == {"text": ""}


@pytest.mark.parametrize("value", ["text", [], None])
def test_job_description_must_be_an_object(helpers, value):
    with pytest.raises(ValueError, match="must be an object with title and text"):
        helpers.job_description(value)


@pytest.mark.parametrize("value, message", [
    ({"text": "x"}, "title is required"),
    ({"title": "t", "text": "x", "salary": 1}, "Unknown fields: salary"),
])
def test_job_description_passes_on_field_errors(helpers, value, message):
    with pytest.raises(ValueError, match=message):
        helpers.job_description(value)


@pytest.mark.parametrize("body", [
    {},
    {**VALID, "resumeText": "x" * 20001},
    {**VALID, "jobDescription": "Backend Intern"},
    {**VALID, "supportingContext": None},
    {**VALID, "userId": "someone-else"},
])
def test_invalid_bodies_are_rejected(helpers, body):
    fields, error = validate_fields(body, helpers.SUGGESTION_FIELDS, partial=False)
    assert fields is None and error


@pytest.mark.parametrize("stop_reason, blocked", [
    ("guardrail_intervened", True),
    ("content_filtered", True),
    ("end_turn", False),
])
def test_was_blocked(helpers, stop_reason, blocked):
    assert helpers.was_blocked(fake_response("{}", stop_reason)) is blocked


@pytest.mark.parametrize("text", [
    '{"suggestions": [{"id": "1", "suggestion": "s", "reason": "r"}]}',
    '```json\n{"suggestions": [{"id": "1", "suggestion": "s", "reason": "r"}]}\n```',
])
def test_parse_reply_returns_the_object(helpers, text):
    assert helpers.parse_reply(fake_response(text)) == {
        "suggestions": [{"id": "1", "suggestion": "s", "reason": "r"}]
    }


@pytest.mark.parametrize("text", ["Sorry, I can't help with that.", "[]", '"text"', '{"suggestions": [', ""])
def test_parse_reply_rejects_anything_else(helpers, text):
    assert helpers.parse_reply(fake_response(text)) is None


def test_call_bedrock_uses_the_prompt_and_guardrail(helpers):
    helpers.call_bedrock({"resume": {"text": "r"}})
    helpers.bedrock.converse.assert_called_once_with(
        modelId="arn:aws:bedrock:us-east-1:123456789012:prompt/ABC:1",
        promptVariables={"resume": {"text": "r"}},
        guardrailConfig={"guardrailIdentifier": "gr123", "guardrailVersion": "1"},
    )
