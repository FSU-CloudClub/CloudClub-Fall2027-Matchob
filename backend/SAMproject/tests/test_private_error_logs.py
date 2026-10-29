"""Check actual JSON logs, including exception text and event-log configuration."""
import importlib.util
import io
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError


MARKER = "PRIVATE_Jane_jane@example.test_5550100_resume_phrase"
ROOT = Path(__file__).resolve().parents[1]


def load(monkeypatch, folder):
    for key in ("USERS_TABLE", "UPLOAD_BUCKET", "PROMPT_ARN", "GUARDRAIL_ID", "GUARDRAIL_VERSION"):
        monkeypatch.setenv(key, "test")
    # Request-body logging must stay disabled even under this configuration.
    monkeypatch.setenv("POWERTOOLS_LOGGER_LOG_EVENT", "true")
    monkeypatch.setattr("boto3.resource", MagicMock())
    monkeypatch.setattr("boto3.client", MagicMock())
    for helper in ("resume_helpers", "bedrock_helpers", "profile_helpers"):
        monkeypatch.delitem(sys.modules, helper, raising=False)
    stream = io.StringIO()
    logger = Logger(service=f"privacy-{uuid.uuid4()}", stream=stream)
    monkeypatch.setattr("aws_lambda_powertools.Logger", lambda **kwargs: logger)
    spec = importlib.util.spec_from_file_location("privacy_app", ROOT / "src" / folder / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, stream


def invoke(module, method, path, body):
    return module.lambda_handler({
        "httpMethod": method, "path": path, "headers": {},
        "requestContext": {"authorizer": {"claims": {"sub": "owner-id"}}},
        "body": json.dumps(body), "isBase64Encoded": False,
    }, SimpleNamespace(function_name="privacy-test", memory_limit_in_mb=128,
                       invoked_function_arn="test", aws_request_id="test"))


@pytest.mark.parametrize("scenario", [
    "profile_read", "profile_update", "profile_delete", "profile_s3_cleanup",
    "resume_upload", "resume_update", "resume_delete", "suggestions",
])
def test_service_failure_logs_exclude_private_details(monkeypatch, scenario):
    folder = ("dynamodb-pipeline" if scenario.startswith("profile") else
              "s3-pipeline" if scenario.startswith("resume") else "bedrock-pipeline")
    module, stream = load(monkeypatch, folder)
    error = ClientError({"Error": {"Code": "AccessDeniedException", "Message": MARKER}}, "Operation")
    method, path, body = "GET", "/profile", {"private": MARKER}
    if scenario == "profile_read":
        module.table.get_item.side_effect = error
    elif scenario == "profile_update":
        method, body = "PUT", {"firstname": MARKER}
        module.table.update_item.side_effect = error
    elif scenario == "profile_delete":
        method = "DELETE"
        module.table.delete_item.side_effect = error
    elif scenario == "profile_s3_cleanup":
        method = "DELETE"
        module.table.delete_item.return_value = {"Attributes": {
            "resumes": {"r1": {"s3Key": MARKER}}}}
        module.s3.delete_object.side_effect = error
    elif scenario.startswith("resume"):
        method, path, body = {
            "resume_upload": ("POST", "/resumes/upload-url", {"fileName": MARKER, "contentType": "application/pdf"}),
            "resume_update": ("PATCH", "/resumes/r1", {"name": MARKER}),
            "resume_delete": ("DELETE", "/resumes/r1", {"private": MARKER}),
        }[scenario]
        module.table.update_item.side_effect = error
    else:
        method, path = "POST", "/suggestions"
        body = {"resumeText": MARKER, "jobDescription": {"title": "Intern", "text": MARKER}}
        monkeypatch.setattr(module, "call_bedrock", MagicMock(side_effect=error))

    response = invoke(module, method, path, body)
    assert response["statusCode"] == 500
    assert MARKER not in response["body"]
    output = stream.getvalue()
    assert MARKER not in output
    records = [json.loads(line) for line in output.splitlines()]
    assert any(record["level"] == "ERROR" for record in records)
    assert all("exception" not in record and "stack_trace" not in record for record in records)


def test_profile_exists_error_does_not_log_exception_text(monkeypatch):
    module, stream = load(monkeypatch, "dynamodb-pipeline")
    module.table.get_item.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": MARKER}}, "GetItem")
    assert module.profile_exists(module.table, "owner-id") is False
    assert "dynamodb get_item failed" in stream.getvalue()
    assert MARKER not in stream.getvalue()
