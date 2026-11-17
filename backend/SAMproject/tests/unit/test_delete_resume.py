"""Exercise DELETE through the Lambda router with mocked AWS services."""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError, ReadTimeoutError


@pytest.fixture
def endpoint(monkeypatch):
    monkeypatch.setenv("USERS_TABLE", "TestUsers")
    monkeypatch.setenv("UPLOAD_BUCKET", "TestUploads")
    monkeypatch.delenv("AWS_SAM_LOCAL", raising=False)
    monkeypatch.setattr("boto3.resource", MagicMock())
    monkeypatch.setattr("boto3.client", MagicMock())
    monkeypatch.delitem(sys.modules, "resume_helpers", raising=False)
    source = Path(__file__).resolve().parents[2] / "src/s3-pipeline/app.py"
    spec = importlib.util.spec_from_file_location("delete_resume_app", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.table = MagicMock()
    module.s3 = MagicMock()
    module.table.update_item.return_value = {"Attributes": {
        "resumes": {"resume-1": {"s3Key": "users/owner/resumes/resume-1.pdf"}}
    }}
    return module


def invoke(endpoint, authenticated=True, resume_id="resume-1"):
    return endpoint.lambda_handler({
        "httpMethod": "DELETE", "path": f"/resumes/{resume_id}",
        "resource": "/resumes/{resumeId}",
        "headers": {"X-Local-User": "spoofed-user"},
        "requestContext": {"stage": "test", "authorizer": {
            "claims": {"sub": "owner"} if authenticated else {}}},
        "body": json.dumps({"userId": "someone-else", "s3Key": "other-file"}),
    }, SimpleNamespace(function_name="test", memory_limit_in_mb=128,
                       invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test",
                       aws_request_id="test"))


def error(code):
    return ClientError({"Error": {"Code": code, "Message": "test"}}, "Test")


def test_success_uses_authenticated_owner_and_stored_key(endpoint):
    result = invoke(endpoint)
    assert result["statusCode"] == 200
    assert json.loads(result["body"]) == {"message": "Resume deleted"}
    endpoint.table.update_item.assert_called_once_with(
        Key={"userId": "owner"}, UpdateExpression="REMOVE #resumes.#resumeId",
        ExpressionAttributeNames={"#resumes": "resumes", "#resumeId": "resume-1"},
        ConditionExpression="attribute_exists(#resumes.#resumeId)", ReturnValues="ALL_OLD")
    endpoint.s3.delete_object.assert_called_once_with(
        Bucket="TestUploads", Key="users/owner/resumes/resume-1.pdf")


def test_unauthorized_never_touches_storage(endpoint):
    result = invoke(endpoint, authenticated=False)
    assert result["statusCode"] == 401
    assert json.loads(result["body"]) == {"error": "Unauthorized"}
    endpoint.table.update_item.assert_not_called()
    endpoint.s3.delete_object.assert_not_called()


@pytest.mark.parametrize("code,status,message", [
    ("ConditionalCheckFailedException", 404, "Resume not found"),
    ("InternalServerError", 500, "Internal server error"),
    ("AccessDeniedException", 500, "Internal server error"),
])
def test_database_failure_does_not_delete_file(endpoint, code, status, message):
    endpoint.table.update_item.side_effect = error(code)
    result = invoke(endpoint)
    assert result["statusCode"] == status
    assert json.loads(result["body"]) == {"error": message}
    endpoint.s3.delete_object.assert_not_called()


def test_s3_failure_keeps_success_after_metadata_deleted(endpoint):
    endpoint.s3.delete_object.side_effect = error("AccessDenied")
    assert invoke(endpoint)["statusCode"] == 200


@pytest.mark.parametrize("legacy_default", ["resume-1", "another-resume", None])
def test_delete_uses_one_write_even_with_legacy_default(endpoint, legacy_default):
    endpoint.table.update_item.return_value["Attributes"]["defaultResume"] = legacy_default
    assert invoke(endpoint)["statusCode"] == 200
    endpoint.table.update_item.assert_called_once()
    endpoint.s3.delete_object.assert_called_once_with(
        Bucket="TestUploads", Key="users/owner/resumes/resume-1.pdf")


@pytest.mark.parametrize("resume_id", ["bad id", "bad.id", "x" * 129, "bad%20id"])
def test_invalid_id_rejected_before_storage(endpoint, resume_id):
    result = invoke(endpoint, resume_id=resume_id)
    assert result["statusCode"] == 400
    assert json.loads(result["body"]) == {"error": "Invalid resume ID"}
    endpoint.table.update_item.assert_not_called()
    endpoint.s3.delete_object.assert_not_called()


@pytest.mark.parametrize("failure", [EndpointConnectionError(endpoint_url="local"),
                                     ReadTimeoutError(endpoint_url="local"),
                                     RuntimeError("private details")])
def test_unexpected_database_failures_return_safe_json(endpoint, failure):
    endpoint.table.update_item.side_effect = failure
    result = invoke(endpoint)
    assert result["statusCode"] == 500
    assert json.loads(result["body"]) == {"error": "Internal server error"}
    endpoint.s3.delete_object.assert_not_called()


@pytest.mark.parametrize("failure", [EndpointConnectionError(endpoint_url="local"),
                                     ReadTimeoutError(endpoint_url="local")])
def test_s3_transport_failure_is_best_effort(endpoint, failure):
    endpoint.s3.delete_object.side_effect = failure
    assert invoke(endpoint)["statusCode"] == 200
