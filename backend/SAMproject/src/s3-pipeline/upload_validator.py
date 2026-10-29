"""Validate quarantined uploads; only the validated byte snapshot is promoted."""

import io
import logging
import os
import re
import uuid
from urllib.parse import unquote_plus

import boto3
from botocore.exceptions import ClientError
from pypdf import PdfReader

from resume_helpers import BUCKET, get_resumes, resume_path_names, table

s3 = boto3.client("s3", endpoint_url=os.environ.get("S3_ENDPOINT") or None)
MAX_BYTES = 5 * 1024 * 1024
MAX_PAGES = 100
KEY_PATTERN = re.compile(r"quarantine/users/([^/]+)/resumes/([A-Za-z0-9_-]{1,128})\.pdf")

# Parser diagnostics can contain document data. Never forward them to CloudWatch.
parser_logger = logging.getLogger("pypdf")
parser_logger.handlers = [logging.NullHandler()]
parser_logger.propagate = False


def valid_pdf(data):
    """Require a bounded, parseable, unencrypted PDF, not merely a magic prefix."""
    if not data or len(data) > MAX_BYTES or not data.startswith(b"%PDF-"):
        return False
    if not data.rstrip().endswith(b"%%EOF"):
        return False
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
            return False
        for page in reader.pages:
            # Resolve the page tree and parse content streams, including scanned PDFs.
            _ = page.mediabox
            contents = page.get_contents()
            if contents is not None:
                _ = contents.operations
        return True
    except Exception:
        # Malformed documents can raise multiple parser exceptions. Infrastructure
        # errors are deliberately outside this catch so Lambda retries them.
        return False


def finish(user_id, resume_id, source_key, status, destination=None):
    names = {**resume_path_names(resume_id), "#status": "status", "#key": "s3Key"}
    values = {":pending": "pending", ":status": status, ":source": source_key}
    update = "SET #resumes.#resumeId.#status = :status"
    if destination:
        update += ", #resumes.#resumeId.#key = :destination"
        values[":destination"] = destination
    try:
        table.update_item(
            Key={"userId": user_id},
            UpdateExpression=update,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ConditionExpression="#resumes.#resumeId.#status = :pending AND #resumes.#resumeId.#key = :source",
        )
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False  # Deleted, rejected, or already promoted by another invocation.
        raise


def validate_upload(key):
    match = KEY_PATTERN.fullmatch(key)
    if not match:
        return
    user_id, resume_id = match.groups()
    stored = (get_resumes(user_id) or {}).get(resume_id)
    if not stored or stored.get("status") != "pending" or stored.get("s3Key") != key:
        # Also completes cleanup after a successful metadata write followed by a
        # transient S3 failure. Replayed PUT URLs can never modify the promoted key.
        if stored and stored.get("status") == "validated":
            s3.delete_object_tagging(Bucket=BUCKET, Key=stored["s3Key"])
        s3.delete_object(Bucket=BUCKET, Key=key)
        return

    try:
        response = s3.get_object(Bucket=BUCKET, Key=key, Range=f"bytes=0-{MAX_BYTES}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return  # Duplicate notification after cleanup.
        if exc.response["Error"]["Code"] == "InvalidRange":
            # S3 returns 416 for a zero-byte object and a byte range request.
            response = None
        else:
            raise
    data = b""
    if response:
        stream = response["Body"]
        try:
            data = stream.read(MAX_BYTES + 1)
        finally:
            stream.close()

    if not valid_pdf(data):
        finish(user_id, resume_id, key, "rejected")
        s3.delete_object(Bucket=BUCKET, Key=key)
        return

    # Write precisely the bytes inspected, never CopyObject from a mutable upload
    # key. Each invocation gets its own destination so a losing race can clean up
    # without deleting another invocation's accepted object.
    destination = f"users/{user_id}/resumes/{resume_id}/validated/{uuid.uuid4()}.pdf"
    s3.put_object(
        Bucket=BUCKET, Key=destination, Body=data, ContentType="application/pdf",
        Tagging="validation=pending",
    )
    if finish(user_id, resume_id, key, "validated", destination):
        s3.delete_object_tagging(Bucket=BUCKET, Key=destination)
    else:
        s3.delete_object(Bucket=BUCKET, Key=destination)
    s3.delete_object(Bucket=BUCKET, Key=key)


def lambda_handler(event, context):
    for record in event.get("Records", []):
        if record.get("eventSource") != "aws:s3" or not record.get("eventName", "").startswith("ObjectCreated:"):
            continue
        if record["s3"]["bucket"]["name"] != BUCKET:
            continue
        validate_upload(unquote_plus(record["s3"]["object"]["key"]))
