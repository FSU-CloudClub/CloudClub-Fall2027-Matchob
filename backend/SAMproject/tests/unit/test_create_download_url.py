"""Task 3: route contract, ownership, signing, and safe failures. No AWS calls."""
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
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError, ReadTimeoutError


# Treat duplicate route registration as a failure, not a warning hidden by a passing build.
pytestmark = pytest.mark.filterwarnings("error:A route like this was already registered")

PRIVATE = "PRIVATE_RESUME_name_email_phone"


@pytest.fixture
def endpoint(monkeypatch):
    monkeypatch.setenv("USERS_TABLE", "users")
    monkeypatch.setenv("UPLOAD_BUCKET", "uploads")
    monkeypatch.setenv("POWERTOOLS_LOGGER_LOG_EVENT", "true")
    monkeypatch.delenv("AWS_SAM_LOCAL", raising=False)
    resource, client = MagicMock(), MagicMock()
    monkeypatch.setattr("boto3.resource", resource)
    monkeypatch.setattr("boto3.client", client)
    monkeypatch.delitem(sys.modules, "resume_helpers", raising=False)
    stream = io.StringIO()
    logger = Logger(service=f"download-test-{uuid.uuid4()}", stream=stream)
    monkeypatch.setattr("aws_lambda_powertools.Logger", lambda **kwargs: logger)
    source = Path(__file__).resolve().parents[2] / "src/s3-pipeline/app.py"
    spec = importlib.util.spec_from_file_location("download_app", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    table = resource.return_value.Table.return_value
    profiles = {
        "a": {"resumes": {"r1": {"s3Key": "users/a/resumes/r1.pdf", "name": PRIVATE}}},
        "b": {"resumes": {}},
    }
    table.get_item.side_effect = lambda *, Key, **kwargs: (
        {"Item": profiles[Key["userId"]]} if Key["userId"] in profiles else {})
    signer = client.return_value.generate_presigned_url
    signer.return_value = "https://example.test/signed"
    return SimpleNamespace(module=module, table=table, signer=signer, stream=stream, profiles=profiles)


def invoke(endpoint, user="a", resume_id="r1"):
    return endpoint.module.lambda_handler({
        "httpMethod": "GET", "path": f"/resumes/{resume_id}/download-url",
        "headers": {"X-Local-User": "a"},
        "queryStringParameters": {"userId": "a", "s3Key": "users/a/resumes/r1.pdf"},
        "body": json.dumps({"userId": "a", "private": PRIVATE}),
        "requestContext": {"authorizer": {"claims": {"sub": user} if user else {}}},
    }, SimpleNamespace(function_name="test", memory_limit_in_mb=128,
                       invoked_function_arn="test", aws_request_id="test"))


def test_owner_gets_fresh_url_for_stored_key(endpoint):
    result = invoke(endpoint)
    assert result["statusCode"] == 200
    assert json.loads(result["body"]) == {"downloadUrl": "https://example.test/signed", "expiresIn": 300}
    assert endpoint.table.get_item.call_args.kwargs["Key"] == {"userId": "a"}
    endpoint.signer.assert_called_once_with("get_object", Params={
        "Bucket": "uploads", "Key": "users/a/resumes/r1.pdf",
        "ResponseContentDisposition": f'inline; filename="{PRIVATE}"'}, ExpiresIn=300)
    assert "resume download url created" in endpoint.stream.getvalue()
    assert PRIVATE not in endpoint.stream.getvalue()
    assert "https://example.test/signed" not in endpoint.stream.getvalue()


@pytest.mark.parametrize("user,resume_id,message", [
    ("b", "r1", "Resume not found"),
    ("a", "nonexistent", "Resume not found"),
    ("missing", "r1", "Resume not found"),
])
def test_missing_or_foreign_resume_never_signs(endpoint, user, resume_id, message):
    result = invoke(endpoint, user, resume_id)
    assert result["statusCode"] == 404
    assert json.loads(result["body"]) == {"error": message}
    assert endpoint.table.get_item.call_args.kwargs["Key"] == {"userId": user}
    endpoint.signer.assert_not_called()


def test_missing_login_ignores_local_header_in_production(endpoint):
    assert invoke(endpoint, user=None)["statusCode"] == 401
    endpoint.table.get_item.assert_not_called()
    endpoint.signer.assert_not_called()


@pytest.mark.parametrize("failure", [
    ClientError({"Error": {"Code": "AccessDenied", "Message": PRIVATE}}, "GetItem"),
    EndpointConnectionError(endpoint_url=PRIVATE),
    ReadTimeoutError(endpoint_url=PRIVATE),
    RuntimeError(PRIVATE),
])
def test_database_failures_return_safe_json(endpoint, failure):
    endpoint.table.get_item.side_effect = failure
    result = invoke(endpoint)
    assert result["statusCode"] == 500
    assert json.loads(result["body"]) == {"error": "Internal server error"}
    endpoint.signer.assert_not_called()
    assert_safe_error_log(endpoint)


def assert_safe_error_log(endpoint):
    output = endpoint.stream.getvalue()
    assert PRIVATE not in output
    records = [json.loads(line) for line in output.splitlines()]
    assert any(r["message"] == "resume download failed" for r in records)
    assert all("exception" not in r and "stack_trace" not in r for r in records)


@pytest.mark.parametrize("failure", [NoCredentialsError(), RuntimeError(PRIVATE)])
def test_signing_failures_return_safe_json(endpoint, failure):
    endpoint.signer.side_effect = failure
    result = invoke(endpoint)
    assert result["statusCode"] == 500
    assert json.loads(result["body"]) == {"error": "Internal server error"}
    assert_safe_error_log(endpoint)


def test_malformed_stored_metadata_returns_safe_json(endpoint):
    endpoint.profiles["a"]["resumes"]["r1"] = {"name": PRIVATE}
    result = invoke(endpoint)
    assert result["statusCode"] == 500
    assert json.loads(result["body"]) == {"error": "Internal server error"}
    endpoint.signer.assert_not_called()
    assert_safe_error_log(endpoint)
