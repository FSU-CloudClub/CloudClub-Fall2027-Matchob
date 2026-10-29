"""P9-2 backend marker checks. AWS services are mocked, log output is real.

This does not cover PDF transport, browser logs, or deployed AWS logging.
"""
import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from tests.test_private_error_logs import invoke, load


MARKERS = (
    "P9CanaryJane", "p9-canary@example.test", "555-0199-9272",
    "P9_RESUME_SECRET_PHRASE", "P9_JOB_SECRET_PHRASE",
)
RESUME_TEXT = "\n".join(MARKERS[:4])
PROFILE = {
    "firstname": MARKERS[0], "lastname": "Canary", "email": MARKERS[1],
    "phoneNumber": MARKERS[2], "age": 22, "year": "senior", "major": MARKERS[3],
}
SUGGESTIONS = {
    "resumeText": RESUME_TEXT,
    "jobDescription": {"title": "Intern", "text": MARKERS[4]},
}


def assert_clean(stream, capsys, caplog):
    # Search each marker separately, so leaking just a name or phone still fails.
    captured = capsys.readouterr()
    output = stream.getvalue() + captured.out + captured.err + caplog.text
    for marker in MARKERS:
        assert marker not in output, f"Private marker leaked: {marker}"
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_available_backend_success_flow(monkeypatch, capsys, caplog):
    profile, profile_logs = load(monkeypatch, "dynamodb-pipeline")
    resumes, resume_logs = load(monkeypatch, "s3-pipeline")
    suggestions, suggestion_logs = load(monkeypatch, "bedrock-pipeline")

    created = invoke(profile, "POST", "/profile", PROFILE)
    assert created["statusCode"] == 201
    item = profile.table.put_item.call_args.kwargs["Item"]
    assert item["email"] == MARKERS[1]
    profile.table.get_item.return_value = {"Item": item}
    fetched = invoke(profile, "GET", "/profile", None)
    assert fetched["statusCode"] == 200
    assert json.loads(fetched["body"])["phoneNumber"] == MARKERS[2]
    profile.table.update_item.return_value = {"Attributes": item}
    assert invoke(profile, "PUT", "/profile", {"major": MARKERS[3]})["statusCode"] == 200

    signed_url = f"https://example.test/file?signature={MARKERS[3]}"
    monkeypatch.setattr(resumes, "presign_upload", MagicMock(return_value=signed_url))
    uploaded = invoke(resumes, "POST", "/resumes/upload-url", {
        "fileName": MARKERS[0] + ".pdf", "contentType": "application/pdf"})
    assert uploaded["statusCode"] == 201
    resume_id = json.loads(uploaded["body"])["resumeId"]
    stored = resumes.table.update_item.call_args.kwargs["ExpressionAttributeValues"][":resume"]
    stored["name"] = MARKERS[0] + " renamed.pdf"
    resumes.table.update_item.return_value = {"Attributes": {"resumes": {resume_id: stored}}}
    # Exercise the actual download-signing helper, with only its AWS client mocked.
    resumes.to_resume_object.__globals__["presign_client"].generate_presigned_url.return_value = signed_url
    renamed = invoke(resumes, "PATCH", f"/resumes/{resume_id}", {"name": stored["name"]})
    assert renamed["statusCode"] == 200
    assert json.loads(renamed["body"])["downloadUrl"] == signed_url

    monkeypatch.setattr(suggestions, "call_bedrock", MagicMock(return_value={
        "stopReason": "end_turn", "output": {"message": {"content": [
            {"text": json.dumps({"suggestions": [MARKERS[3]]})}]}}}))
    assert invoke(suggestions, "POST", "/suggestions", SUGGESTIONS)["statusCode"] == 200
    assert suggestions.call_bedrock.call_args.args[0]["resume"]["text"] == RESUME_TEXT

    assert invoke(resumes, "DELETE", f"/resumes/{resume_id}", None)["statusCode"] == 200
    resumes.s3.delete_object.assert_called_once_with(Bucket="test", Key=stored["s3Key"])
    profile.table.delete_item.return_value = {"Attributes": item}
    assert invoke(profile, "DELETE", "/profile", None)["statusCode"] == 200

    records = []
    for stream in (profile_logs, resume_logs, suggestion_logs):
        records.extend(assert_clean(stream, capsys, caplog))
    # Prevent an empty-log false pass: all successful operations must be observed.
    assert {record["message"] for record in records} >= {
        "profile created", "profile fetched", "profile updated", "profile deleted",
        "resume upload url created", "resume updated", "resume deleted", "suggestions created",
    }


@pytest.mark.parametrize("folder,method,path", [
    ("dynamodb-pipeline", "POST", "/profile"),
    ("s3-pipeline", "POST", "/resumes/upload-url"),
    ("bedrock-pipeline", "POST", "/suggestions"),
])
@pytest.mark.parametrize("unauthorized", [False, True])
def test_rejected_requests_do_not_log_markers(monkeypatch, capsys, caplog, folder, method, path, unauthorized):
    module, stream = load(monkeypatch, folder)
    if unauthorized:
        monkeypatch.setattr(module, "get_user_id", lambda event: None)
    # Even unknown field names may contain private data.
    response = invoke(module, method, path, {marker: marker for marker in MARKERS})
    assert response["statusCode"] == (401 if unauthorized else 400)
    assert_clean(stream, capsys, caplog)


@pytest.mark.parametrize("scenario,status", [
    ("blocked", 422), ("invalid_reply", 502), ("unexpected", 500),
    ("throttled", 503), ("service_error", 500),
])
def test_suggestions_failure_flow(monkeypatch, capsys, caplog, scenario, status):
    module, stream = load(monkeypatch, "bedrock-pipeline")
    call = MagicMock()
    monkeypatch.setattr(module, "call_bedrock", call)
    if scenario == "unexpected":
        call.side_effect = RuntimeError(RESUME_TEXT)
    elif scenario in {"throttled", "service_error"}:
        code = "ThrottlingException" if scenario == "throttled" else "AccessDeniedException"
        call.side_effect = ClientError({"Error": {"Code": code, "Message": RESUME_TEXT}}, "Converse")
    else:
        call.return_value = {"stopReason": "guardrail_intervened" if scenario == "blocked" else "end_turn",
                             "output": {"message": {"content": [{"text": RESUME_TEXT}]}}}
    assert invoke(module, "POST", "/suggestions", SUGGESTIONS)["statusCode"] == status
    assert assert_clean(stream, capsys, caplog), "Expected a failure log"
