import os
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from matchob_common.auth import get_user_id
from matchob_common.http import read_json_body, to_json
from matchob_common.validators import validate_fields
from resume_helpers import (
    BUCKET,
    UPLOAD_FIELDS,
    get_resumes,
    now_iso,
    presign_upload,
    resume_path_names,
    s3_key,
    table,
    to_resume_object,  # Builds the public resume fields and a temporary download link.
)

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ.get("S3_ENDPOINT") or None,
    config=Config(s3={"addressing_style": "path"}),
)

logger = Logger()
app = APIGatewayRestResolver(serializer=to_json)


# Add one function per endpoint in the Resumes section of
# docs/general/api-contracts.md, e.g. @app.get("/resumes"). The routes are already in
# templates/s3-template.yaml, so until a function exists here they return 404.
@app.post("/resumes/upload-url")
def create_upload_url():
    """Store resume metadata on the caller's profile, then return a signed upload URL."""
    user_id = get_user_id(app.current_event.raw_event)
    if not user_id:
        return {"error": "Unauthorized"}, 401

    body, error = read_json_body(app.current_event)
    if error:
        return {"error": error}, 400

    fields, error = validate_fields(body, UPLOAD_FIELDS, partial=False)
    if error:
        return {"error": error}, 400

    resume_id = str(uuid.uuid4())
    key = s3_key(user_id, resume_id, fields["contentType"])
    stored = {
        "s3Key": key,
        "name": fields["fileName"],
        "tags": [],
        "contentType": fields["contentType"],
        "uploadedAt": now_iso(),
    }
    try:
        table.update_item(
            Key={"userId": user_id},
            UpdateExpression="SET #resumes.#resumeId = :resume",
            ExpressionAttributeNames=resume_path_names(resume_id),
            ExpressionAttributeValues={":resume": stored},
            ConditionExpression="attribute_exists(userId)",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {"error": "Profile not found"}, 404
        logger.exception("dynamodb update_item failed")
        return {"error": "Internal server error"}, 500

    upload_url = presign_upload(key, fields["contentType"])
    logger.info("resume upload url created", extra={"user_id": user_id, "resume_id": resume_id})
    return {"resumeId": resume_id, "uploadUrl": upload_url}, 201


# GET /resumes runs when the frontend asks to display the user's resumes.
@app.get("/resumes")
def list_resumes():
    """Return the caller's resumes, newest first, with fresh download links."""
    # Started by Tommy before Task #2 was assigned to Nate; completed for Task #2.
    # See docs/s3-pipeline/endpoints/list-resumes.md for the endpoint requirements.

    # Identify the caller using their login information (or the local test header).
    # Keep Tommy's check: requests without a user receive 401 (unauthorized).
    user_id = get_user_id(app.current_event.raw_event)
    if not user_id:
        return {"error": "Unauthorized"}, 401

    # Read only this user's resume details from DynamoDB, not the resume files.
    # If AWS reports a database error, log the details and send a general error.
    try:
        resumes = get_resumes(user_id)
    except ClientError:
        logger.exception("dynamodb get_item failed")
        return {"error": "Internal server error"}, 500

    # None means the profile does not exist: return 404 (not found).
    # An empty map means the profile exists but has no resumes: return [] below.
    if resumes is None:
        return {"error": "Profile not found"}, 404

    # Each entry contains a resume ID and its stored details.
    # Upload times use a consistent UTC format, so sorting their text works.
    # reverse=True puts the newest upload first.
    sorted_resumes = sorted(
        resumes.items(), key=lambda item: item[1]["uploadedAt"], reverse=True
    )

    # Build the list the frontend expects. The helper adds a fresh download link
    # and its expiry time, and leaves the internal s3Key out of the public fields.
    # If there are no resumes, this loop is skipped and result stays empty.
    result = []
    for resume_id, stored in sorted_resumes:
        result.append(to_resume_object(resume_id, stored))

    # Record the user and number of resumes returned, then send 200 (success).
    logger.info("resumes listed", extra={"user_id": user_id, "count": len(result)})
    return result, 200


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
