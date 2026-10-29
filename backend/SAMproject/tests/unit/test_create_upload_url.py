"""Upload route validation and write-before-presign guarantees; no AWS calls."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from botocore.exceptions import ClientError


@pytest.fixture
def endpoint(monkeypatch):
    monkeypatch.setenv("USERS_TABLE", "users")
    monkeypatch.setenv("UPLOAD_BUCKET", "uploads")
    monkeypatch.setattr("boto3.resource", MagicMock())
    monkeypatch.setattr("boto3.client", MagicMock())
    monkeypatch.delitem(sys.modules, "resume_helpers", raising=False)
    source = Path(__file__).resolve().parents[2] / "src/s3-pipeline/app.py"
    spec = importlib.util.spec_from_file_location("upload_app", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "get_user_id", lambda event: "user-123")
    module.app.current_event = SimpleNamespace(
        raw_event={}, json_body={"fileName": " cv.pdf ", "contentType": "application/pdf"}
    )
    monkeypatch.setattr(module, "presign_upload", MagicMock(return_value="signed-url"))
    return module


def test_stores_metadata_before_presigning(endpoint):
    def sign(key, content_type):
        endpoint.table.update_item.assert_called_once()
        assert key.startswith("quarantine/users/user-123/resumes/")
        assert key.endswith(".pdf")
        assert content_type == "application/pdf"
        return "signed-url"

    endpoint.presign_upload.side_effect = sign
    body, status = endpoint.create_upload_url()
    assert status == 201
    assert body["uploadUrl"] == "signed-url"
    assert UUID(body["resumeId"]).version == 4
    kwargs = endpoint.table.update_item.call_args.kwargs
    assert kwargs["Key"] == {"userId": "user-123"}
    assert kwargs["ConditionExpression"] == "attribute_exists(userId)"
    assert kwargs["UpdateExpression"] == "SET #resumes.#resumeId = :resume"
    assert kwargs["ExpressionAttributeNames"] == {"#resumes": "resumes", "#resumeId": body["resumeId"]}
    stored = kwargs["ExpressionAttributeValues"][":resume"]
    assert stored["name"] == "cv.pdf"
    assert stored["tags"] == []
    assert stored["status"] == "pending"
    assert stored["s3Key"] == f'quarantine/users/user-123/resumes/{body["resumeId"]}.pdf'
    assert stored["uploadedAt"].endswith("Z")


@pytest.mark.parametrize("payload", [None, {}, [], {"fileName": "x", "contentType": "image/png"}, {"fileName": "x", "contentType": "application/pdf", "id": "client-id"}])
def test_invalid_input_never_writes_or_signs(endpoint, payload):
    endpoint.app.current_event.json_body = payload
    assert endpoint.create_upload_url()[1] == 400
    endpoint.table.update_item.assert_not_called()
    endpoint.presign_upload.assert_not_called()


def test_unauthenticated_request(endpoint, monkeypatch):
    monkeypatch.setattr(endpoint, "get_user_id", lambda event: None)
    assert endpoint.create_upload_url() == ({"error": "Unauthorized"}, 401)
    endpoint.table.update_item.assert_not_called()
    endpoint.presign_upload.assert_not_called()


def test_malformed_json(endpoint):
    class InvalidEvent:
        raw_event = {}

        @property
        def json_body(self):
            raise ValueError("bad JSON")

    endpoint.app.current_event = InvalidEvent()
    assert endpoint.create_upload_url() == ({"error": "Invalid JSON body"}, 400)
    endpoint.table.update_item.assert_not_called()
    endpoint.presign_upload.assert_not_called()


@pytest.mark.parametrize("code,status,message", [
    ("ConditionalCheckFailedException", 404, "Profile not found"),
    ("ValidationException", 500, "Internal server error"),
    ("AccessDeniedException", 500, "Internal server error"),
])
def test_failed_write_never_signs(endpoint, code, status, message):
    endpoint.table.update_item.side_effect = ClientError(
        {"Error": {"Code": code, "Message": "private details"}}, "UpdateItem"
    )
    assert endpoint.create_upload_url() == ({"error": message}, status)
    endpoint.presign_upload.assert_not_called()
