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
from botocore.exceptions import ClientError, EndpointConnectionError


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


@pytest.mark.parametrize("error", [
    ClientError({"Error": {"Code": "AccessDeniedException", "Message": MARKER}}, "GetItem"),
    EndpointConnectionError(endpoint_url=MARKER),
])
def test_profile_exists_failure_returns_500_without_private_details(monkeypatch, error):
    module, stream = load(monkeypatch, "dynamodb-pipeline")
    module.table.update_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": MARKER}}, "UpdateItem")
    module.table.get_item.side_effect = error
    response = invoke(module, "PUT", "/profile", {"defaultResume": "r1"})
    assert response["statusCode"] == 500
    assert json.loads(response["body"]) == {"error": "Internal server error"}
    assert "profile AWS operation failed" in stream.getvalue()
    assert MARKER not in stream.getvalue()


@pytest.mark.parametrize("method,operation,body", [
    ("GET", "get_item", {}),
    ("POST", "put_item", {"firstname": "Local", "lastname": "Test", "email": "local@example.com",
                          "phoneNumber": "5550100", "age": 20, "year": "junior", "major": "CS"}),
    ("PUT", "update_item", {"age": 21}),
    ("DELETE", "delete_item", {}),
])
def test_profile_transport_failures_return_safe_500(monkeypatch, method, operation, body):
    module, stream = load(monkeypatch, "dynamodb-pipeline")
    getattr(module.table, operation).side_effect = EndpointConnectionError(endpoint_url=MARKER)
    response = invoke(module, method, "/profile", body)
    assert response["statusCode"] == 500
    assert json.loads(response["body"]) == {"error": "Internal server error"}
    assert "profile AWS operation failed" in stream.getvalue()
    assert MARKER not in stream.getvalue()


def test_profile_s3_transport_failure_continues_cleanup(monkeypatch):
    module, stream = load(monkeypatch, "dynamodb-pipeline")
    module.table.delete_item.return_value = {"Attributes": {"resumes": {
        "r1": {"s3Key": "users/owner-id/resumes/r1.pdf"},
        "r2": {"s3Key": "users/owner-id/resumes/r2.pdf"},
    }}}
    module.s3.delete_object.side_effect = [EndpointConnectionError(endpoint_url=MARKER), {}]
    response = invoke(module, "DELETE", "/profile", {})
    assert response["statusCode"] == 500
    assert json.loads(response["body"]) == {"error": "Internal server error"}
    assert module.s3.delete_object.call_count == 2
    assert "s3 resume deletion failed" in stream.getvalue()
    assert MARKER not in stream.getvalue()
