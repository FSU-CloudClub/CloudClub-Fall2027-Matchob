"""GET/PUT/DELETE contract tests through the Lambda router, with AWS mocked.

Complements test_profile_isolation.py and test_delete_user.py rather than
duplicating their isolation and S3 cleanup scenarios.
"""

import importlib.util
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError


@pytest.fixture
def endpoint(monkeypatch):
    monkeypatch.setenv("USERS_TABLE", "TestUsers")
    monkeypatch.setenv("UPLOAD_BUCKET", "TestUploads")
    monkeypatch.delenv("AWS_SAM_LOCAL", raising=False)
    resource, s3 = MagicMock(), MagicMock()
    monkeypatch.setattr("boto3.resource", lambda *a, **kw: resource)
    monkeypatch.setattr("boto3.client", lambda *a, **kw: s3)
    source = Path(__file__).resolve().parents[2] / "src/dynamodb-pipeline/app.py"
    spec = importlib.util.spec_from_file_location("profile_contract_app", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    context = SimpleNamespace(
        function_name="ProfileFunction", memory_limit_in_mb=128,
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test",
        aws_request_id="test-request",
    )

    def invoke(method, body=None, authenticated=True):
        event = {
            "httpMethod": method, "path": "/profile", "resource": "/profile",
            "headers": {"Content-Type": "application/json", "X-Local-User": "other-user"},
            "queryStringParameters": {"userId": "other-user"},
            "body": body, "isBase64Encoded": False,
            "requestContext": {
                "requestId": "test-request", "stage": "dev",
                "authorizer": {"claims": {"sub": "user-123"}} if authenticated else {},
            },
        }
        response = module.lambda_handler(event, context)
        return response["statusCode"], json.loads(response["body"])

    return invoke, resource.Table.return_value, s3


def aws_error(code="InternalServerError"):
    return ClientError({"Error": {"Code": code, "Message": "PRIVATE_AWS_DETAILS"}}, "Test")


def test_get_returns_only_item_with_numeric_age(endpoint):
    invoke, table, _ = endpoint
    item = {"userId": "user-123", "age": Decimal("20"), "resumes": {}, "defaultResume": None}
    table.get_item.return_value = {"Item": item, "ResponseMetadata": {"RequestId": "internal"}}
    status, body = invoke("GET")
    assert status == 200
    assert body == {**item, "age": 20}
    assert type(body["age"]) is int
    table.get_item.assert_called_once_with(Key={"userId": "user-123"})


def test_get_missing_profile(endpoint):
    invoke, table, _ = endpoint
    table.get_item.return_value = {}
    assert invoke("GET") == (404, {"error": "Profile not found"})


@pytest.mark.parametrize("method,operation", [("GET", "get_item"), ("PUT", "update_item"), ("DELETE", "delete_item")])
def test_database_errors_return_generic_500(endpoint, method, operation):
    invoke, table, s3 = endpoint
    getattr(table, operation).side_effect = aws_error()
    assert invoke(method, '{"age":21}') == (500, {"error": "Internal server error"})
    s3.delete_object.assert_not_called()


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_authentication_precedes_database_access_and_body_validation(endpoint, method):
    invoke, table, s3 = endpoint
    assert invoke(method, "{invalid", authenticated=False) == (401, {"error": "Unauthorized"})
    assert table.mock_calls == []
    assert s3.mock_calls == []


def test_put_partial_update_returns_full_profile_and_targets_caller(endpoint):
    invoke, table, _ = endpoint
    updated = {"userId": "user-123", "firstname": "Sarah", "age": Decimal("21"), "resumes": {}}
    table.update_item.return_value = {"Attributes": updated}
    assert invoke("PUT", '{"age":21}') == (200, updated)
    table.update_item.assert_called_once_with(
        Key={"userId": "user-123"}, UpdateExpression="SET #age = :age",
        ExpressionAttributeNames={"#age": "age"}, ExpressionAttributeValues={":age": 21},
        ConditionExpression="attribute_exists(userId)", ReturnValues="ALL_NEW",
    )
    table.get_item.assert_not_called()


@pytest.mark.parametrize("body,message", [
    (None, "Request body must be a JSON object"),
    ("{invalid", "Invalid JSON body"),
    ("null", "Request body must be a JSON object"),
    ("[]", "Request body must be a JSON object"),
    ("{}", "Provide at least one field to update"),
    ('{"userId":"other-user"}', "Unknown fields: userId"),
    ('{"resumes":{}}', "Unknown fields: resumes"),
    ('{"structuredJsonResume":{}}', "Unknown fields: structuredJsonResume"),
    ('{"firstname":" "}', "firstname must be a non-empty string"),
    ('{"email":"invalid"}', "email must be a valid email address"),
    ('{"age":true}', "age must be a whole number from 13 to 120"),
    ('{"age":121}', "age must be a whole number from 13 to 120"),
    ('{"defaultResume":" "}', "defaultResume must be a non-empty string"),
])
def test_put_invalid_body_never_writes(endpoint, body, message):
    invoke, table, _ = endpoint
    assert invoke("PUT", body) == (400, {"error": message})
    assert table.mock_calls == []


@pytest.mark.parametrize("resume_id", [None, "resume-1"])
def test_put_sets_or_clears_default_resume(endpoint, resume_id):
    invoke, table, _ = endpoint
    table.update_item.return_value = {"Attributes": {"userId": "user-123", "defaultResume": resume_id}}
    assert invoke("PUT", json.dumps({"defaultResume": resume_id}))[0] == 200
    args = table.update_item.call_args.kwargs
    assert args["ExpressionAttributeValues"] == {":defaultResume": resume_id}
    if resume_id is None:
        assert args["ConditionExpression"] == "attribute_exists(userId)"
        assert "#defaultResumeId" not in args["ExpressionAttributeNames"]
    else:
        assert args["ConditionExpression"] == "attribute_exists(userId) AND attribute_exists(#resumes.#defaultResumeId)"
        assert args["ExpressionAttributeNames"]["#defaultResumeId"] == resume_id
    table.get_item.assert_not_called()


@pytest.mark.parametrize("profile_exists", [True, False])
def test_put_failed_resume_condition_distinguishes_missing_profile(endpoint, profile_exists):
    invoke, table, _ = endpoint
    table.update_item.side_effect = aws_error("ConditionalCheckFailedException")
    table.get_item.return_value = {"Item": {"userId": "user-123"}} if profile_exists else {}
    expected = (400, {"error": "defaultResume must be one of your resumes"}) if profile_exists else (404, {"error": "Profile not found"})
    assert invoke("PUT", '{"defaultResume":"foreign-resume"}') == expected
    table.get_item.assert_called_once_with(Key={"userId": "user-123"}, ProjectionExpression="userId")


def test_put_missing_profile_without_default_does_not_read_again(endpoint):
    invoke, table, _ = endpoint
    table.update_item.side_effect = aws_error("ConditionalCheckFailedException")
    assert invoke("PUT", '{"age":21}') == (404, {"error": "Profile not found"})
    table.get_item.assert_not_called()


def test_repeated_delete_returns_404_without_repeating_cleanup(endpoint):
    invoke, table, s3 = endpoint
    table.delete_item.side_effect = [
        {"Attributes": {"userId": "user-123", "resumes": {"r1": {"s3Key": "users/user-123/resumes/r1.pdf"}}}},
        {},
    ]
    assert invoke("DELETE") == (200, {"message": "Profile deleted"})
    assert invoke("DELETE") == (404, {"error": "Profile not found"})
    assert all(call.kwargs == {"Key": {"userId": "user-123"}, "ReturnValues": "ALL_OLD"} for call in table.delete_item.call_args_list)
    s3.delete_object.assert_called_once_with(Bucket="TestUploads", Key="users/user-123/resumes/r1.pdf")
