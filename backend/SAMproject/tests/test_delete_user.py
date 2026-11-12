import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest
from botocore.exceptions import ClientError


@pytest.fixture
def handler(monkeypatch):
    monkeypatch.setenv("USERS_TABLE", "TestUsers")
    monkeypatch.setenv("UPLOAD_BUCKET", "TestUploads")
    monkeypatch.delenv("AWS_SAM_LOCAL", raising=False)

    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "dynamodb-pipeline"
        / "app.py"
    )
    spec = importlib.util.spec_from_file_location("delete_endpoint_app", source)
    module = importlib.util.module_from_spec(spec)

    # Prevent boto3 from accessing AWS during import.
    with patch("boto3.resource"), patch("boto3.client"):
        spec.loader.exec_module(module)

    module.table = MagicMock()
    return module


@pytest.mark.parametrize(
    "scenario, expected_status, expected_body",
    [
        ("success", 200, {"message": "Profile deleted"}),
        ("resumes", 200, {"message": "Profile deleted"}),
        ("s3_error", 500, {"error": "Internal server error"}),
        ("empty_resumes", 200, {"message": "Profile deleted"}),
        ("missing", 404, {"error": "Profile not found"}),
        ("unauthorized", 401, {"error": "Unauthorized"}),
        ("database_error", 500, {"error": "Internal server error"}),
    ],
)
def test_delete_profile(handler, scenario, expected_status, expected_body):
    claims = {} if scenario == "unauthorized" else {"sub": "12345"}

    event = {
        "httpMethod": "DELETE",
        "path": "/profile",
        "resource": "/profile",
        "headers": {},
        "requestContext": {
            "requestId": "test-request",
            "stage": "test",
            "authorizer": {"claims": claims},
        },
        "isBase64Encoded": False,
        # A supplied ID must not override the authenticated user's ID.
        "body": json.dumps({"userId": "someone-else"}),
    }

    context = SimpleNamespace(
        function_name="test-delete-user",
        memory_limit_in_mb=128,
        invoked_function_arn=(
            "arn:aws:lambda:us-east-1:123456789012:function:test-delete-user"
        ),
        aws_request_id="test-request",
    )

    handler.table.delete_item.return_value = (
        {"Attributes": {"userId": "12345"}}
        if scenario == "success"
        else {}
    )

    if scenario in {"resumes", "s3_error", "empty_resumes"}:
        handler.table.delete_item.return_value = {"Attributes": {
            "userId": "12345",
            "resumes": {} if scenario == "empty_resumes" else {
                "r1": {"s3Key": "12345/first.pdf"},
                "r2": {"s3Key": "12345/second.pdf"},
            },
        }}
    if scenario == "s3_error":
        handler.s3.delete_object.side_effect = [
            ClientError({"Error": {"Code": "AccessDenied", "Message": "Denied"}}, "DeleteObject"),
            None,
        ]

    if scenario == "database_error":
        handler.table.delete_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "InternalServerError",
                    "Message": "Simulated database failure",
                }
            },
            "DeleteItem",
        )

    response = handler.lambda_handler(event, context)

    assert response["statusCode"] == expected_status
    assert json.loads(response["body"]) == expected_body

    if scenario == "unauthorized":
        handler.table.delete_item.assert_not_called()
    else:
        handler.table.delete_item.assert_called_once_with(
            Key={"userId": "12345"},
            ReturnValues="ALL_OLD",
        )

    if scenario in {"resumes", "s3_error"}:
        assert handler.s3.delete_object.call_args_list == [
            call(Bucket="TestUploads", Key="12345/first.pdf"),
            call(Bucket="TestUploads", Key="12345/second.pdf"),
        ]
    else:
        handler.s3.delete_object.assert_not_called()
