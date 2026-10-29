"""Content validation, promotion races and fail-closed download boundaries."""
import importlib.util
import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

from .test_create_upload_url import endpoint

KEY = "quarantine/users/user-123/resumes/resume-123.pdf"


def pdf_bytes(encrypted=False, pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    if encrypted:
        writer.encrypt("secret")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def worker(endpoint, monkeypatch):
    source = Path(__file__).resolve().parents[2] / "src/s3-pipeline/upload_validator.py"
    spec = importlib.util.spec_from_file_location("test_validator", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "s3", MagicMock())
    module.table.reset_mock()
    module.table.get_item.return_value = {"Item": {"resumes": {
        "resume-123": {"s3Key": KEY, "status": "pending"}
    }}}
    module.s3.get_object.return_value = {"Body": io.BytesIO(pdf_bytes())}
    return module


@pytest.mark.parametrize("data", [b"", b"not a PDF", b"%PDF-1.7\nnot really a PDF\n%%EOF", pdf_bytes()[:-10], pdf_bytes(encrypted=True), pdf_bytes(pages=0), pdf_bytes(pages=101)])
def test_rejects_invalid_contents(worker, data):
    assert worker.valid_pdf(data) is False


def test_accepts_real_pdf_and_rejects_appended_payload(worker):
    assert worker.valid_pdf(pdf_bytes())
    assert not worker.valid_pdf(pdf_bytes() + b"<html>not PDF</html>")


def test_parses_page_contents_not_just_header(worker):
    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    stream = DecodedStreamObject()
    stream.set_data(b"(unterminated string")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    assert not worker.valid_pdf(output.getvalue())


def test_promotes_exact_validated_bytes(worker):
    data = pdf_bytes()
    body = io.BytesIO(data)
    worker.s3.get_object.return_value = {"Body": body}
    worker.validate_upload(KEY)
    assert body.closed
    put = worker.s3.put_object.call_args.kwargs
    assert put["Body"] == data
    assert put["Key"].startswith("users/user-123/resumes/resume-123/validated/")
    assert put["Tagging"] == "validation=pending"
    update = worker.table.update_item.call_args.kwargs
    assert update["ExpressionAttributeValues"][":destination"] == put["Key"]
    assert update["ExpressionAttributeValues"][":status"] == "validated"
    assert ":pending" in update["ConditionExpression"]
    assert ":source" in update["ConditionExpression"]
    worker.s3.delete_object_tagging.assert_called_once_with(Bucket="uploads", Key=put["Key"])
    worker.s3.delete_object.assert_called_once_with(Bucket="uploads", Key=KEY)
    worker.s3.copy_object.assert_not_called()


@pytest.mark.parametrize("data", [b"renamed executable", b"x" * (5 * 1024 * 1024 + 1)])
def test_rejected_upload_is_deleted_and_never_promoted(worker, data):
    worker.s3.get_object.return_value = {"Body": io.BytesIO(data)}
    worker.validate_upload(KEY)
    worker.s3.put_object.assert_not_called()
    assert worker.table.update_item.call_args.kwargs["ExpressionAttributeValues"][":status"] == "rejected"
    worker.s3.delete_object.assert_called_once_with(Bucket="uploads", Key=KEY)


def test_size_boundary(worker):
    data = pdf_bytes()
    padded = data[:-6] + b" " * (worker.MAX_BYTES - len(data)) + data[-6:]
    assert len(padded) == worker.MAX_BYTES
    assert worker.valid_pdf(padded)
    assert not worker.valid_pdf(padded + b" ")


def test_empty_s3_object_rejected(worker):
    worker.s3.get_object.side_effect = ClientError({"Error": {"Code": "InvalidRange"}}, "GetObject")
    worker.validate_upload(KEY)
    assert worker.table.update_item.call_args.kwargs["ExpressionAttributeValues"][":status"] == "rejected"
    worker.s3.put_object.assert_not_called()


@pytest.mark.parametrize("stored", [None, {"status": "rejected", "s3Key": KEY}, {"status": "validated", "s3Key": "users/user-123/resumes/resume-123/validated/accepted.pdf"}])
def test_duplicate_or_replayed_upload_never_changes_accepted_file(worker, stored):
    worker.table.get_item.return_value = {"Item": {"resumes": {"resume-123": stored} if stored else {}}}
    worker.validate_upload(KEY)
    worker.s3.get_object.assert_not_called()
    worker.s3.put_object.assert_not_called()
    worker.table.update_item.assert_not_called()
    worker.s3.delete_object.assert_called_once_with(Bucket="uploads", Key=KEY)


def test_concurrent_completion_or_deletion_cleans_only_own_candidate(worker):
    worker.table.update_item.side_effect = ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
    worker.validate_upload(KEY)
    candidate = worker.s3.put_object.call_args.kwargs["Key"]
    assert [c.kwargs["Key"] for c in worker.s3.delete_object.call_args_list] == [candidate, KEY]
    worker.s3.delete_object_tagging.assert_not_called()


def test_transient_database_failure_keeps_quarantine_for_retry(worker):
    worker.table.update_item.side_effect = ClientError({"Error": {"Code": "InternalServerError"}}, "UpdateItem")
    with pytest.raises(ClientError):
        worker.validate_upload(KEY)
    worker.s3.delete_object.assert_not_called()
    worker.s3.delete_object_tagging.assert_not_called()


def test_missing_object_notification_is_idempotent(worker):
    worker.s3.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
    worker.validate_upload(KEY)
    worker.table.update_item.assert_not_called()


def test_event_filters_and_url_decoding(worker, monkeypatch):
    validate = MagicMock()
    monkeypatch.setattr(worker, "validate_upload", validate)
    def record(bucket="uploads", name="ObjectCreated:Put", key=KEY.replace("/", "%2F")):
        return {"eventSource": "aws:s3", "eventName": name, "s3": {"bucket": {"name": bucket}, "object": {"key": key}}}
    worker.lambda_handler({"Records": [record(), record(bucket="other"), record(name="ObjectRemoved:Delete")]}, None)
    validate.assert_called_once_with(KEY)


@pytest.mark.parametrize("status", [None, "pending", "rejected", "unverified"])
def test_unvalidated_resumes_never_receive_download_urls(endpoint, status):
    stored = {"s3Key": KEY, "name": "resume.pdf", "tags": [], "contentType": "application/pdf", "uploadedAt": "now"}
    if status:
        stored["status"] = status
    endpoint.table.get_item.return_value = {"Item": {"resumes": {"resume-123": stored}}}
    endpoint.s3.generate_presigned_url.reset_mock()
    result = endpoint.list_resumes()
    assert result[0]["downloadUrl"] is None
    assert result[0]["expiresIn"] == 0
    assert endpoint.create_download_url("resume-123")[1] == 409
    endpoint.s3.generate_presigned_url.assert_not_called()


def test_other_users_resume_not_downloadable(endpoint):
    endpoint.table.get_item.return_value = {"Item": {"resumes": {}}}
    assert endpoint.create_download_url("someone-elses-resume")[1] == 404
    assert endpoint.table.get_item.call_args.kwargs["Key"] == {"userId": "user-123"}


def test_quarantine_key_never_downloadable_even_with_validated_status(endpoint):
    assert not endpoint.is_validated({"status": "validated", "s3Key": KEY})


@pytest.mark.parametrize("fixture,expected", [("scanned-resume.pdf", True), ("multipage-resume.pdf", True), ("protected-resume.pdf", False)])
def test_repository_pdf_fixtures(worker, fixture, expected):
    path = Path(__file__).resolve().parents[4] / "data/fixtures" / fixture
    assert worker.valid_pdf(path.read_bytes()) is expected


def test_validated_resume_download(endpoint):
    stored = {"s3Key": "users/user-123/resumes/resume-123/validated/file.pdf", "status": "validated", "name": "resume.pdf", "tags": [], "contentType": "application/pdf", "uploadedAt": "now"}
    endpoint.table.get_item.return_value = {"Item": {"resumes": {"resume-123": stored}}}
    endpoint.s3.generate_presigned_url.return_value = "signed-download"
    assert endpoint.create_download_url("resume-123") == {"downloadUrl": "signed-download", "expiresIn": 300}
    assert endpoint.s3.generate_presigned_url.call_args.kwargs["Params"]["Key"] == stored["s3Key"]


def test_pending_patch_does_not_bypass_download_gate(endpoint):
    stored = {"s3Key": KEY, "status": "pending", "name": "New name", "tags": [], "contentType": "application/pdf", "uploadedAt": "now"}
    endpoint.app.current_event.json_body = {"name": "New name"}
    endpoint.table.update_item.return_value = {"Attributes": {"resumes": {"resume-123": stored}}}
    result, status = endpoint.update_resume("resume-123")
    assert status == 200
    assert result["downloadUrl"] is None
    endpoint.s3.generate_presigned_url.assert_not_called()


def test_read_routes_require_authentication(endpoint, monkeypatch):
    monkeypatch.setattr(endpoint, "get_user_id", lambda event: None)
    assert endpoint.list_resumes()[1] == 401
    assert endpoint.create_download_url("resume-123")[1] == 401
    endpoint.table.get_item.assert_not_called()


def test_docx_claim_rejected(endpoint):
    endpoint.app.current_event.json_body = {"fileName": "resume.docx", "contentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    assert endpoint.create_upload_url()[1] == 400
    endpoint.presign_upload.assert_not_called()
    endpoint.table.update_item.assert_not_called()
