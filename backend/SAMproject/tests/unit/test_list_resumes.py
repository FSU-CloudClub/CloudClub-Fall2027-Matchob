"""Exercise GET /resumes through the Lambda handler without AWS calls."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError


@pytest.fixture
def endpoint(monkeypatch):
    monkeypatch.setenv("USERS_TABLE", "users")
    monkeypatch.setenv("UPLOAD_BUCKET", "uploads")
    monkeypatch.delenv("AWS_SAM_LOCAL", raising=False)
    monkeypatch.setattr("boto3.resource", MagicMock())
    monkeypatch.setattr("boto3.client", MagicMock())
    monkeypatch.delitem(sys.modules, "resume_helpers", raising=False)
    source = Path(__file__).resolve().parents[2] / "src/s3-pipeline/app.py"
    spec = importlib.util.spec_from_file_location("list_resumes_app", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invoke(endpoint, user_id="user-123"):
    event = {
        "httpMethod": "GET",
        "path": "/resumes",
        "headers": {},
        "requestContext": {
            "requestId": "test-request",
            "authorizer": {"claims": {"sub": user_id}} if user_id else {},
        },
    }
    context = SimpleNamespace(
        function_name="resumes", memory_limit_in_mb=128,
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:resumes",
        aws_request_id="test-request",
    )
    response = endpoint.lambda_handler(event, context)
    return response["statusCode"], json.loads(response["body"])


def test_unauthenticated_request_does_not_read(endpoint):
    assert invoke(endpoint, None) == (401, {"error": "Unauthorized"})
    endpoint.table.get_item.assert_not_called()


def test_missing_profile(endpoint):
    endpoint.table.get_item.return_value = {}
    assert invoke(endpoint) == (404, {"error": "Profile not found"})


@pytest.mark.parametrize("item", [{}, {"resumes": {}}])
def test_profile_without_resumes_returns_empty_list(endpoint, item):
    endpoint.table.get_item.return_value = {"Item": item}
    assert invoke(endpoint) == (200, [])


def test_newest_first_public_fields_and_fresh_download_links(endpoint):
    stored = {
        "older": {"s3Key": "users/user-123/resumes/older.pdf", "name": "old.pdf",
                  "tags": [], "contentType": "application/pdf", "uploadedAt": "2026-10-22T10:00:00Z"},
        "newer": {"s3Key": "users/user-123/resumes/newer.pdf", "name": "new.pdf",
                  "tags": ["work"], "contentType": "application/pdf", "uploadedAt": "2026-10-23T10:00:00Z"},
    }
    endpoint.table.get_item.return_value = {"Item": {"resumes": stored}}
    signer = sys.modules["resume_helpers"].presign_client.generate_presigned_url
    signer.side_effect = ["signed-new-1", "signed-old-1", "signed-new-2", "signed-old-2"]
    for generation in (1, 2):
        status, body = invoke(endpoint)
        assert status == 200
        assert body == [
            {"id": resume_id, **{k: v for k, v in stored[resume_id].items() if k != "s3Key"},
             "downloadUrl": f"signed-{label}-{generation}", "expiresIn": 300}
            for resume_id, label in (("newer", "new"), ("older", "old"))
        ]
    for call in endpoint.table.get_item.call_args_list:
        assert call.kwargs == {
            "Key": {"userId": "user-123"}, "ProjectionExpression": "#resumes",
            "ExpressionAttributeNames": {"#resumes": "resumes"},
        }
    assert signer.call_count == 4
    for call, resume_id in zip(signer.call_args_list, ["newer", "older"] * 2):
        assert call.args == ("get_object",)
        assert call.kwargs == {
            "Params": {"Bucket": "uploads", "Key": stored[resume_id]["s3Key"],
                       "ResponseContentDisposition": f'inline; filename="{stored[resume_id]["name"]}"'},
            "ExpiresIn": 300,
        }


def test_database_error_returns_generic_500(endpoint):
    endpoint.table.get_item.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "private details"}}, "GetItem"
    )
    assert invoke(endpoint) == (500, {"error": "Internal server error"})
