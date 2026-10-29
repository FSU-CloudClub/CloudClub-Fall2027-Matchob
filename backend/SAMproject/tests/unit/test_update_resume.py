"""PATCH resume contract tests through the Lambda entry point; no AWS calls.

Runnable with pytest or Python's standard-library unittest runner.
"""

import importlib.util
import json
import os
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from botocore.exceptions import ClientError


ROOT = Path(__file__).resolve().parents[2]


class UpdateResumeTests(unittest.TestCase):
    def setUp(self):
        # Supply the same import paths as pytest.ini for standalone unittest runs.
        paths = [str(ROOT / "src/shared"), str(ROOT / "src/s3-pipeline")]
        self.enterContext(patch.object(sys, "path", paths + sys.path))
        self.enterContext(patch.dict(os.environ, {
            "USERS_TABLE": "users", "UPLOAD_BUCKET": "uploads",
            "AWS_SAM_LOCAL": "false",
        }))
        # Restore the module cache after each test so other endpoint tests stay isolated.
        self.enterContext(patch.dict(sys.modules))
        sys.modules.pop("resume_helpers", None)
        resource = self.enterContext(patch("boto3.resource"))
        self.clients = self.enterContext(patch("boto3.client"))
        self.table = resource.return_value.Table.return_value
        spec = importlib.util.spec_from_file_location(
            "update_resume_app", ROOT / "src/s3-pipeline/app.py"
        )
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.info = self.enterContext(patch.object(self.module.logger, "info"))
        self.error = self.enterContext(patch.object(self.module.logger, "error"))
        self.signer = self.clients.return_value.generate_presigned_url
        self.signer.return_value = "https://example.test/signed-download"
        self.stored = {
            "s3Key": "users/user-123/resumes/resume-456.pdf",
            "name": "Original.pdf", "tags": ["original"],
            "contentType": "application/pdf", "uploadedAt": "2026-10-22T14:03:00Z",
        }
        self.context = SimpleNamespace(
            function_name="ResumesFunction", memory_limit_in_mb=128,
            invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test",
            aws_request_id="test-request",
        )

    def invoke(self, payload, *, user="user-123", local=False, raw=False):
        self.table.update_item.return_value = {
            "Attributes": {"resumes": {"resume-456": deepcopy(self.stored)}}
        }
        event = {
            "httpMethod": "PATCH", "path": "/resumes/resume-456",
            "resource": "/resumes/{resumeId}",
            "pathParameters": {"resumeId": "resume-456"},
            "headers": {"Content-Type": "application/json", "X-Local-User": "local-user"},
            "body": payload if raw else json.dumps(payload),
            "isBase64Encoded": False,
            "requestContext": {
                "requestId": "test-request", "stage": "dev",
                "authorizer": {"claims": {"sub": user}} if user else {},
            },
        }
        with patch.dict(os.environ, {"AWS_SAM_LOCAL": "true" if local else "false"}):
            response = self.module.lambda_handler(event, self.context)
        headers = response.get("headers") or response.get("multiValueHeaders", {})
        content_type = next(value for key, value in headers.items() if key.lower() == "content-type")
        if isinstance(content_type, list):
            content_type = ", ".join(content_type)
        self.assertIn("application/json", content_type)
        return response["statusCode"], json.loads(response["body"])

    def assert_no_write_or_sign(self):
        self.table.update_item.assert_not_called()
        self.signer.assert_not_called()
        self.info.assert_not_called()

    def test_successful_updates_and_full_response(self):
        cases = [
            ({"name": "  SWE Resume  "}, {"name": "SWE Resume"}),
            ({"tags": [" swe ", "swe", "intern"]}, {"tags": ["swe", "intern"]}),
            ({"tags": []}, {"tags": []}),
            ({"name": "New", "tags": ["new"]}, {"name": "New", "tags": ["new"]}),
            ({"name": "n" * 100, "tags": ["t" * 30] * 10},
             {"name": "n" * 100, "tags": ["t" * 30]}),
        ]
        for payload, cleaned in cases:
            with self.subTest(payload=payload):
                self.table.reset_mock()
                self.signer.reset_mock()
                self.info.reset_mock()
                self.stored.update(cleaned)
                status, body = self.invoke(payload)
                self.assertEqual(status, 200)
                self.assertEqual(body, {
                    "id": "resume-456",
                    **{k: v for k, v in self.stored.items() if k != "s3Key"},
                    "downloadUrl": "https://example.test/signed-download", "expiresIn": 300,
                })
                # Only supplied fields may change; no profile read/overwrite or S3 write.
                self.table.update_item.assert_called_once_with(
                    Key={"userId": "user-123"},
                    UpdateExpression="SET " + ", ".join(
                        f"#resumes.#resumeId.#{key} = :{key}" for key in cleaned
                    ),
                    ExpressionAttributeNames={
                        "#resumes": "resumes", "#resumeId": "resume-456",
                        **{f"#{key}": key for key in cleaned},
                    },
                    ExpressionAttributeValues={f":{key}": value for key, value in cleaned.items()},
                    ConditionExpression="attribute_exists(#resumes.#resumeId)",
                    ReturnValues="ALL_NEW",
                )
                self.assertEqual([call[0] for call in self.table.mock_calls], ["update_item"])
                self.signer.assert_called_once_with(
                    "get_object", Params={
                        "Bucket": "uploads", "Key": self.stored["s3Key"],
                        "ResponseContentDisposition": f'inline; filename="{self.stored["name"]}"',
                    }, ExpiresIn=300,
                )
                self.clients.return_value.put_object.assert_not_called()
                self.clients.return_value.delete_object.assert_not_called()
                self.info.assert_called_once_with("resume updated", extra={
                    "user_id": "user-123", "resume_id": "resume-456", "fields": list(cleaned),
                })
                self.error.assert_not_called()

    def test_invalid_input(self):
        cases = [
            ({}, "Provide at least one field to update"),
            (None, "Request body must be a JSON object"),
            ([], "Request body must be a JSON object"),
            ("name", "Request body must be a JSON object"),
            ({"s3Key": "x"}, "Unknown fields: s3Key"),
            ({"userId": "other"}, "Unknown fields: userId"),
            ({"name": "valid", "id": "other"}, "Unknown fields: id"),
        ]
        for value in ["", "   ", "n" * 101, None, 1, True, []]:
            cases.append(({"name": value}, "name must be 1-100 characters"))
        tag_error = "tags must be a list of at most 10 strings, each 1-30 characters"
        for value in ["swe", None, {}, ["x"] * 11, [""], ["  "], ["t" * 31], [1], [None]]:
            cases.append(({"tags": value}, tag_error))
        for payload, message in cases:
            with self.subTest(payload=payload):
                self.assertEqual(self.invoke(payload), (400, {"error": message}))
                self.assert_no_write_or_sign()

    def test_malformed_json(self):
        self.assertEqual(self.invoke('{"name":', raw=True),
                         (400, {"error": "Invalid JSON body"}))
        self.assert_no_write_or_sign()

    def test_missing_authentication_rejects_spoofed_local_header(self):
        # Authentication must run before parsing even a malformed body.
        self.assertEqual(self.invoke("{", user=None, raw=True),
                         (401, {"error": "Unauthorized"}))
        self.assert_no_write_or_sign()

    def test_local_authentication(self):
        self.assertEqual(self.invoke({"name": "New"}, user=None, local=True)[0], 200)
        self.assertEqual(self.table.update_item.call_args.kwargs["Key"], {"userId": "local-user"})

    def test_cognito_claim_takes_precedence_over_local_header(self):
        self.assertEqual(self.invoke({"name": "New"}, local=True)[0], 200)
        self.assertEqual(self.table.update_item.call_args.kwargs["Key"], {"userId": "user-123"})

    def test_missing_resume(self):
        # Missing profile/resume and another owner's resume share this conditional failure.
        self.table.update_item.side_effect = ClientError({"Error": {
            "Code": "ConditionalCheckFailedException", "Message": "private details",
        }}, "UpdateItem")
        self.assertEqual(self.invoke({"name": "New"}), (404, {"error": "Resume not found"}))
        self.assertEqual(self.table.update_item.call_args.kwargs["Key"], {"userId": "user-123"})
        self.signer.assert_not_called()
        self.info.assert_not_called()
        self.error.assert_not_called()

    def test_unexpected_dynamodb_errors(self):
        for code in ["ValidationException", "AccessDeniedException", "InternalServerError"]:
            with self.subTest(code=code):
                self.error.reset_mock()
                self.table.update_item.side_effect = ClientError({"Error": {
                    "Code": code, "Message": "private details",
                }}, "UpdateItem")
                self.assertEqual(self.invoke({"tags": []}),
                                 (500, {"error": "Internal server error"}))
                self.error.assert_called_once_with("dynamodb update_item failed")
                self.signer.assert_not_called()
                self.info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
