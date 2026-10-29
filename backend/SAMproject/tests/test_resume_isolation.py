"""P3-4: caller-keyed storage and actual signing arguments through the router.

AWS is mocked; these do not test S3 enforcement of the generated URLs.
"""
import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError


def stored(owner, resume_id, date="2026-10-29T10:00:00Z"):
    return {"name": f"PRIVATE_{owner}.pdf", "tags": [owner],
            "s3Key": f"users/{owner}/resumes/{resume_id}.pdf",
            "contentType": "application/pdf", "uploadedAt": date}


@pytest.fixture
def endpoint(monkeypatch):
    monkeypatch.setenv("USERS_TABLE", "users")
    monkeypatch.setenv("UPLOAD_BUCKET", "uploads")
    monkeypatch.delenv("AWS_SAM_LOCAL", raising=False)
    resource, client = MagicMock(), MagicMock()
    monkeypatch.setattr("boto3.resource", resource)
    monkeypatch.setattr("boto3.client", client)
    monkeypatch.delitem(sys.modules, "resume_helpers", raising=False)
    source = Path(__file__).resolve().parents[1] / "src/s3-pipeline/app.py"
    spec = importlib.util.spec_from_file_location("resume_isolation_app", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    profiles = {
        "a": {"resumes": {"a-only": stored("a", "a-only"), "shared-id": stored("a", "shared-id")}},
        "b": {"resumes": {"shared-id": stored("b", "shared-id")}},
        "empty": {"resumes": {}},
    }
    table = resource.return_value.Table.return_value

    def read(*, Key, **kwargs):
        item = profiles.get(Key["userId"])
        return {"Item": deepcopy(item)} if item is not None else {}

    def update(*, Key, ExpressionAttributeNames, ExpressionAttributeValues, **kwargs):
        resumes = profiles.get(Key["userId"], {}).get("resumes", {})
        resume_id = ExpressionAttributeNames["#resumeId"]
        if resume_id not in resumes:
            raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
        resumes[resume_id]["name"] = ExpressionAttributeValues[":name"]
        return {"Attributes": {"resumes": deepcopy(resumes)}}

    table.get_item.side_effect = read
    table.update_item.side_effect = update
    signer = client.return_value.generate_presigned_url
    signer.return_value = "https://example.test/signed"
    return SimpleNamespace(module=module, table=table, signer=signer, profiles=profiles)


def invoke(endpoint, path="/resumes", user="b", method="GET", body=None):
    return endpoint.module.lambda_handler({
        "httpMethod": method, "path": path,
        # All client-supplied ownership hints must be ignored.
        "headers": {"X-Local-User": "a"},
        "queryStringParameters": {"userId": "a", "s3Key": "users/a/resumes/a-only.pdf"},
        "body": json.dumps(body if body is not None else {"userId": "a", "s3Key": "users/a/resumes/a-only.pdf"}),
        "requestContext": {"authorizer": {"claims": {"sub": user} if user else {}}},
    }, SimpleNamespace(function_name="test", memory_limit_in_mb=128,
                       invoked_function_arn="test", aws_request_id="test"))


def signed_keys(endpoint):
    return [item.kwargs["Params"]["Key"] for item in endpoint.signer.call_args_list]


def test_alternating_users_list_only_their_resumes(endpoint):
    for user in ("a", "b", "a"):
        endpoint.signer.reset_mock()
        response = invoke(endpoint, user=user)
        assert response["statusCode"] == 200
        resumes = json.loads(response["body"])
        assert {r["id"] for r in resumes} == set(endpoint.profiles[user]["resumes"])
        assert all(r["name"] == f"PRIVATE_{user}.pdf" and "s3Key" not in r for r in resumes)
        assert set(signed_keys(endpoint)) == {r["s3Key"] for r in endpoint.profiles[user]["resumes"].values()}
    assert [c.kwargs["Key"] for c in endpoint.table.get_item.call_args_list] == [
        {"userId": "a"}, {"userId": "b"}, {"userId": "a"}]


def test_list_newest_first(endpoint):
    endpoint.profiles["b"]["resumes"]["new"] = stored("b", "new", "2026-10-30T10:00:00Z")
    response = invoke(endpoint)
    assert response["statusCode"] == 200
    assert [r["id"] for r in json.loads(response["body"])] == ["new", "shared-id"]


@pytest.mark.parametrize("user,status,body", [
    ("empty", 200, []), ("missing", 404, {"error": "Profile not found"}),
])
def test_empty_or_missing_profile_never_signs(endpoint, user, status, body):
    response = invoke(endpoint, user=user)
    assert response["statusCode"] == status
    assert json.loads(response["body"]) == body
    endpoint.signer.assert_not_called()


@pytest.mark.parametrize("path", ["/resumes", "/resumes/shared-id/download-url"])
def test_no_login_never_reads_or_signs(endpoint, path):
    assert invoke(endpoint, path, user=None)["statusCode"] == 401
    endpoint.table.get_item.assert_not_called()
    endpoint.signer.assert_not_called()


def test_download_uses_own_stored_key_even_with_same_resume_id(endpoint):
    response = invoke(endpoint, "/resumes/shared-id/download-url")
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"downloadUrl": "https://example.test/signed", "expiresIn": 300}
    endpoint.signer.assert_called_once_with("get_object", Params={
        "Bucket": "uploads", "Key": "users/b/resumes/shared-id.pdf",
        "ResponseContentDisposition": 'inline; filename="PRIVATE_b.pdf"',
    }, ExpiresIn=300)
    assert endpoint.table.get_item.call_args.kwargs["Key"] == {"userId": "b"}


@pytest.mark.parametrize("user,resume_id", [("b", "a-only"), ("b", "nonexistent"), ("missing", "a-only")])
def test_foreign_or_missing_resume_is_indistinguishable_and_never_signed(endpoint, user, resume_id):
    response = invoke(endpoint, f"/resumes/{resume_id}/download-url", user=user)
    assert response["statusCode"] == 404
    assert json.loads(response["body"]) == {"error": "Resume not found"}
    endpoint.signer.assert_not_called()


@pytest.mark.parametrize("resume_id", ["bad id", "bad%2Fid", "..", "x" * 129])
def test_invalid_download_id_never_reads_or_signs(endpoint, resume_id):
    assert invoke(endpoint, f"/resumes/{resume_id}/download-url")["statusCode"] == 400
    endpoint.table.get_item.assert_not_called()
    endpoint.signer.assert_not_called()


@pytest.mark.parametrize("path", ["/resumes", "/resumes/shared-id/download-url"])
@pytest.mark.parametrize("error", [
    ClientError({"Error": {"Code": "AccessDenied", "Message": "PRIVATE_DATA"}}, "GetItem"),
    EndpointConnectionError(endpoint_url="PRIVATE_DATA"),
])
def test_read_failure_returns_safe_error_and_never_signs(endpoint, path, error):
    endpoint.table.get_item.side_effect = error
    response = invoke(endpoint, path)
    assert response["statusCode"] == 500
    assert json.loads(response["body"]) == {"error": "Internal server error"}
    endpoint.signer.assert_not_called()


def test_patch_cannot_obtain_foreign_download_url(endpoint):
    before = deepcopy(endpoint.profiles["a"])
    response = invoke(endpoint, "/resumes/a-only", method="PATCH", body={"name": "Attempt"})
    assert response["statusCode"] == 404
    assert json.loads(response["body"]) == {"error": "Resume not found"}
    assert endpoint.table.update_item.call_args.kwargs["Key"] == {"userId": "b"}
    assert endpoint.profiles["a"] == before
    endpoint.signer.assert_not_called()


def test_patch_same_id_only_updates_and_signs_own_resume(endpoint):
    before = deepcopy(endpoint.profiles["a"])
    response = invoke(endpoint, "/resumes/shared-id", method="PATCH", body={"name": "Updated"})
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["name"] == "Updated"
    assert signed_keys(endpoint) == ["users/b/resumes/shared-id.pdf"]
    assert endpoint.profiles["a"] == before
