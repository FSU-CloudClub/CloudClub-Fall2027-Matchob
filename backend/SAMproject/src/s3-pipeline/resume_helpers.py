"""Helpers used only by the resumes Lambda. Design: docs/s3-pipeline/helpers.md."""

import os
from datetime import datetime, timezone

import boto3
from botocore.config import Config
from matchob_common.validators import REQUIRED, one_of, str_length

ALLOWED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}
URL_EXPIRES_IN = 300

dynamodb = boto3.resource("dynamodb", endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None)
table = dynamodb.Table(os.environ["USERS_TABLE"])
BUCKET = os.environ["UPLOAD_BUCKET"]

# Used only for generate_presigned_url. Locally it signs for localhost:9090 (the host your
# browser knows) while app.py's s3 client talks to s3:9090. In AWS both endpoints are None.
_public_endpoint = os.environ.get("S3_PUBLIC_ENDPOINT") or None
presign_client = boto3.client(
    "s3",
    endpoint_url=_public_endpoint,
    config=Config(signature_version="s3v4", s3={"addressing_style": "path" if _public_endpoint else "virtual"}),
)


def tag_list(value):
    """Return the trimmed, de-duplicated list of tags, or raise ValueError."""
    message = "must be a list of at most 10 strings, each 1-30 characters"
    if not isinstance(value, list) or len(value) > 10:
        raise ValueError(message)
    tags = []
    for tag in value:
        if not isinstance(tag, str) or not 1 <= len(tag.strip()) <= 30:
            raise ValueError(message)
        if tag.strip() not in tags:
            tags.append(tag.strip())
    return tags


# Field specs for validate_fields. Anything else (id, s3Key, uploadedAt) is rejected.
UPLOAD_FIELDS = {
    "fileName": (REQUIRED, str_length(1, 100)),
    "contentType": (REQUIRED, one_of(*ALLOWED_CONTENT_TYPES)),
}

RESUME_FIELDS = {  # only ever used with partial=True
    "name": (REQUIRED, str_length(1, 100)),
    "tags": (REQUIRED, tag_list),
}


def s3_key(user_id, resume_id, content_type):
    """Return the S3 key for a resume. content_type must already be validated."""
    return f"users/{user_id}/resumes/{resume_id}.{ALLOWED_CONTENT_TYPES[content_type]}"


def now_iso():
    """Return the current UTC time as 2026-10-22T14:03:00Z (sorts correctly as a string)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def presign_upload(key, content_type):
    """Return a URL that allows one PUT of key with exactly this Content-Type."""
    return presign_client.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=URL_EXPIRES_IN,
    )


def presign_download(key, file_name):
    """Return a URL that downloads key, saved as file_name."""
    file_name = file_name.replace('"', "")
    return presign_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key, "ResponseContentDisposition": f'inline; filename="{file_name}"'},
        ExpiresIn=URL_EXPIRES_IN,
    )


def to_resume_object(resume_id, stored):
    """Turn a stored resume into the contract's resume object. Never includes s3Key."""
    return {
        "id": resume_id,
        "name": stored["name"],
        "tags": stored["tags"],
        "contentType": stored["contentType"],
        "uploadedAt": stored["uploadedAt"],
        "downloadUrl": presign_download(stored["s3Key"], stored["name"]),
        "expiresIn": URL_EXPIRES_IN,
    }


def get_resumes(user_id):
    """Return the user's resumes map, or None if they have no profile. ClientError propagates."""
    item = table.get_item(
        Key={"userId": user_id},
        ProjectionExpression="#resumes",
        ExpressionAttributeNames={"#resumes": "resumes"},
    ).get("Item")
    if item is None:
        return None
    return item.get("resumes", {})


def resume_path_names(resume_id):
    """ExpressionAttributeNames for resumes.<id>. A map key is a name, so the ID never goes in values."""
    return {"#resumes": "resumes", "#resumeId": resume_id}
