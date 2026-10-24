"""POST /profile tests through the Lambda entry point; no AWS calls are made."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError


@pytest.fixture
def valid_profile():
    return {
        "firstname": "Sarah",
        "lastname": "Lee",
        "email": "sarah@fsu.edu",
        "phoneNumber": "+18505551234",
        "age": 20,
        "year": "junior",
        "major": "CS",
    }


@pytest.fixture
def endpoint(monkeypatch):
    monkeypatch.setenv("USERS_TABLE", "MatchobUsers")
    monkeypatch.delenv("AWS_SAM_LOCAL", raising=False)
    resource = MagicMock()
    monkeypatch.setattr("boto3.resource", lambda *args, **kwargs: resource)
    source = Path(__file__).resolve().parents[2] / "src/dynamodb-pipeline/app.py"
    spec = importlib.util.spec_from_file_location("create_user_app", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    context = SimpleNamespace(
        function_name="GetProfileFunction",
        memory_limit_in_mb=128,
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test",
        aws_request_id="test-request",
    )

    def invoke(body, authenticated=True):
        event = {
            "httpMethod": "POST",
            "path": "/profile",
            "resource": "/profile",
            "headers": {"Content-Type": "application/json", "X-Local-User": "spoofed"},
            "body": body,
            "isBase64Encoded": False,
            "requestContext": {
                "requestId": "test-request",
                "stage": "dev",
                "authorizer": {"claims": {"sub": "user-123"}} if authenticated else {},
            },
        }
        response = module.lambda_handler(event, context)
        return response["statusCode"], json.loads(response["body"])

    return invoke, resource.Table.return_value


def test_creates_profile_using_authenticated_id(endpoint, valid_profile):
    invoke, table = endpoint
    payload = {
        key: f"  {value}  " if isinstance(value, str) and key != "year" else value
        for key, value in valid_profile.items()
    }
    status, body = invoke(json.dumps(payload))
    expected = {
        "userId": "user-123",
        **valid_profile,
        "websites": [],
        "defaultResume": None,
        "resumes": {},
        "structuredJsonResume": None,
    }
    assert status == 201
    assert body == expected
    table.put_item.assert_called_once_with(
        Item=expected, ConditionExpression="attribute_not_exists(userId)"
    )


def test_rejects_client_supplied_user_id(endpoint, valid_profile):
    invoke, table = endpoint
    payload = {**valid_profile, "userId": "another-user"}
    assert invoke(json.dumps(payload)) == (400, {"error": "Unknown fields: userId"})
    table.put_item.assert_not_called()


def test_unauthenticated_request_cannot_use_local_header_in_production(endpoint, valid_profile):
    invoke, table = endpoint
    assert invoke(json.dumps(valid_profile), authenticated=False) == (
        401, {"error": "Unauthorized"}
    )
    table.put_item.assert_not_called()


@pytest.mark.parametrize("body,message", [
    (None, "Request body must be a JSON object"),
    ("", "Request body must be a JSON object"),
    ("{invalid", "Invalid JSON body"),
])
def test_missing_or_invalid_json(endpoint, body, message):
    invoke, table = endpoint
    assert invoke(body) == (400, {"error": message})
    table.put_item.assert_not_called()


@pytest.mark.parametrize("body", [None, [], "text", 42, True])
def test_body_must_be_an_object(endpoint, body):
    invoke, table = endpoint
    assert invoke(json.dumps(body)) == (400, {"error": "Request body must be a JSON object"})
    table.put_item.assert_not_called()


@pytest.mark.parametrize("field", ["firstname", "lastname", "email", "phoneNumber", "major"])
@pytest.mark.parametrize("value", [None, "", "  \t\n", 42, [], {}])
def test_fields_must_be_nonempty_strings(endpoint, valid_profile, field, value):
    invoke, table = endpoint
    payload = {**valid_profile, field: value}
    assert invoke(json.dumps(payload)) == (400, {"error": f"{field} must be a non-empty string"})
    table.put_item.assert_not_called()


@pytest.mark.parametrize("field", ["firstname", "lastname", "email", "phoneNumber", "age", "year", "major"])
def test_required_fields(endpoint, valid_profile, field):
    invoke, table = endpoint
    payload = valid_profile.copy()
    del payload[field]
    assert invoke(json.dumps(payload)) == (400, {"error": f"{field} is required"})
    table.put_item.assert_not_called()


@pytest.mark.parametrize("code,status,message", [
    ("ConditionalCheckFailedException", 409, "Profile already exists"),
    ("ProvisionedThroughputExceededException", 500, "Internal server error"),
    ("AccessDeniedException", 500, "Internal server error"),
])
def test_dynamodb_errors(endpoint, valid_profile, code, status, message):
    invoke, table = endpoint
    table.put_item.side_effect = ClientError(
        {"Error": {"Code": code, "Message": "Private AWS error details"}}, "PutItem"
    )
    assert invoke(json.dumps(valid_profile)) == (
        status, {"error": message}
    )
    table.put_item.assert_called_once()


@pytest.mark.parametrize("field,value,message", [
    ("email", "invalid", "email must be a valid email address"),
    ("age", 12, "age must be a whole number from 13 to 120"),
    ("age", 121, "age must be a whole number from 13 to 120"),
    ("age", True, "age must be a whole number from 13 to 120"),
    ("age", 20.5, "age must be a whole number from 13 to 120"),
    ("age", "20", "age must be a whole number from 13 to 120"),
    ("year", "invalid", "year must be one of: freshman, sophomore, junior, senior, graduate"),
    ("websites", "https://example.com", "websites must be a list of URLs"),
    ("websites", ["invalid"], "websites must be a list of URLs starting with http:// or https://"),
    ("defaultResume", "resume-123", "defaultResume must be one of your resumes"),
])
def test_invalid_profile_values(endpoint, valid_profile, field, value, message):
    invoke, table = endpoint
    assert invoke(json.dumps({**valid_profile, field: value})) == (400, {"error": message})
    table.put_item.assert_not_called()


@pytest.mark.parametrize("age", [13, 120])
def test_accepts_age_boundaries_and_optional_fields(endpoint, valid_profile, age):
    invoke, table = endpoint
    payload = {
        **valid_profile,
        "age": age,
        "websites": ["  https://example.com  "],
        "defaultResume": None,
    }
    status, body = invoke(json.dumps(payload))
    assert status == 201
    assert body["age"] == age
    assert body["websites"] == ["https://example.com"]
    assert body["defaultResume"] is None
    assert table.put_item.call_args.kwargs["Item"] == body
