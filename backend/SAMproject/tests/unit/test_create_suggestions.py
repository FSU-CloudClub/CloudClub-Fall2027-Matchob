"""Exercise the suggestions route without AWS calls."""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import (ClientError, ReadTimeoutError, ConnectTimeoutError,
                                 EndpointConnectionError, ConnectionClosedError)


def fake_response(text, reason="end_turn"):
    return {"stopReason": reason, "output": {"message": {"content": [{"text": text}]}}}


@pytest.fixture
def endpoint(monkeypatch):
    for name in ("PROMPT_ARN", "GUARDRAIL_ID", "GUARDRAIL_VERSION"):
        monkeypatch.setenv(name, "test")
    monkeypatch.setattr("boto3.client", MagicMock())
    monkeypatch.delitem(sys.modules, "bedrock_helpers", raising=False)
    source = Path(__file__).resolve().parents[2] / "src/bedrock-pipeline/app.py"
    spec = importlib.util.spec_from_file_location("suggestions_app", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "get_user_id", lambda event: "user-123")
    module.app.current_event = SimpleNamespace(raw_event={}, json_body={
        "resumeText": "Resume", "jobDescription": {"title": "Intern", "text": "Python"}
    })
    monkeypatch.setattr(module, "call_bedrock", MagicMock(return_value=fake_response('{"suggestions": []}')))
    monkeypatch.setattr(module, "logger", MagicMock())
    return module


def test_success(endpoint):
    assert endpoint.create_suggestions() == {"suggestions": []}
    endpoint.call_bedrock.assert_called_once_with({
        "resume": {"text": "Resume"}, "job_title": {"text": "Intern"},
        "company": {"text": ""}, "job_description": {"text": "Python"},
        "supporting_context": {"text": ""},
    })
    endpoint.logger.info.assert_called_once_with(
        "suggestions created", extra={"user_id": "user-123", "stop_reason": "end_turn"}
    )


def test_route(endpoint):
    body = json.dumps(endpoint.app.current_event.json_body)
    del endpoint.app.current_event
    result = endpoint.app.resolve({
        "httpMethod": "POST", "path": "/suggestions", "headers": {},
        "requestContext": {"stage": "test"},
        "body": body,
    }, None)
    assert result["statusCode"] == 200
    assert json.loads(result["body"]) == {"suggestions": []}


def test_unauthorized(endpoint, monkeypatch):
    monkeypatch.setattr(endpoint, "get_user_id", lambda event: None)
    assert endpoint.create_suggestions() == ({"error": "Unauthorized"}, 401)
    endpoint.call_bedrock.assert_not_called()


@pytest.mark.parametrize("payload", [None, {}, [], {"resumeText": "Resume"},
    {"resumeText": "x" * 20001, "jobDescription": {"title": "Intern", "text": "Python"}},
    {"resumeText": "Resume", "jobDescription": "Python"},
    {"resumeText": "Resume", "jobDescription": {"title": "Intern", "text": "Python"}, "unknown": True},
])
def test_invalid_input(endpoint, payload):
    endpoint.app.current_event.json_body = payload
    assert endpoint.create_suggestions()[1] == 400
    endpoint.call_bedrock.assert_not_called()


def test_malformed_json(endpoint):
    class InvalidEvent:
        raw_event = {}

        @property
        def json_body(self):
            raise ValueError("bad JSON")

    endpoint.app.current_event = InvalidEvent()
    assert endpoint.create_suggestions() == ({"error": "Invalid JSON body"}, 400)
    endpoint.call_bedrock.assert_not_called()


@pytest.mark.parametrize("reason", ["guardrail_intervened", "content_filtered"])
def test_blocked_before_parsing(endpoint, reason):
    endpoint.call_bedrock.return_value = fake_response("Blocked content", reason)
    assert endpoint.create_suggestions() == ({"error": "Request blocked by content filters"}, 422)


@pytest.mark.parametrize("text", ["not JSON", "[]", '{"suggestions":'])
def test_invalid_reply(endpoint, text):
    endpoint.call_bedrock.return_value = fake_response(text)
    assert endpoint.create_suggestions() == ({"error": "AI returned an invalid response"}, 502)


@pytest.mark.parametrize("code,status,message", [
    ("ThrottlingException", 503, "AI service is busy, try again"),
    ("ServiceUnavailableException", 503, "AI service is busy, try again"),
    ("ModelTimeoutException", 504, "AI service timed out"),
    ("AccessDeniedException", 500, "Internal server error"),
])
def test_service_errors(endpoint, code, status, message):
    endpoint.call_bedrock.side_effect = ClientError({"Error": {"Code": code}}, "Converse")
    assert endpoint.create_suggestions() == ({"error": message}, status)


def test_read_timeout(endpoint):
    endpoint.call_bedrock.side_effect = ReadTimeoutError(endpoint_url="x")
    assert endpoint.create_suggestions() == ({"error": "AI service timed out"}, 504)


@pytest.mark.parametrize("error,status,message", [
    (ConnectTimeoutError(endpoint_url="https://bedrock.test"), 504, "AI service timed out"),
    (EndpointConnectionError(endpoint_url="https://bedrock.test"), 503, "AI service is unavailable, try again"),
    (ConnectionClosedError(endpoint_url="https://bedrock.test"), 503, "AI service is unavailable, try again"),
    (RuntimeError("private resume text"), 500, "Internal server error"),
])
def test_failures_return_json_through_router(endpoint, error, status, message):
    body = json.dumps(endpoint.app.current_event.json_body)
    del endpoint.app.current_event
    endpoint.call_bedrock.side_effect = error
    result = endpoint.app.resolve({
        "httpMethod": "POST", "path": "/suggestions", "headers": {},
        "requestContext": {"stage": "test"}, "body": body,
    }, None)
    assert result["statusCode"] == status
    assert json.loads(result["body"]) == {"error": message}
    assert "private resume text" not in str(endpoint.logger.mock_calls)
