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
    URL_EXPIRES_IN,
    get_resumes,
    now_iso,
    presign_download, 
    presign_upload,
    resume_path_names,
    s3_key,
    table,
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


@app.get("/resumes")
def list_resumes():
    # Implementation for fetching resumes
    # NOT DONE YET! ONLY STARTED BY TOMMY BEFORE TASK WAS ASSIGNED TO NATE (TASK #2 from meeting_notes.md)
    # aka CloudClub-Fall2027-Matchob/backend/SAMproject/docs/meeting_notes.md
    user_id = get_user_id(app.current_event.raw_event)
    if not user_id:
        return {"error": "Unauthorized"}, 401
    
    resumes = get_resumes(user_id)
    if not resumes:
        return {"error": "No resumes found"}, 404


@app.get("/resumes/<resume_id>/download-url")
def create_download_url(resume_id):
    """Return a fresh download link for one of the caller's resumes."""
    user_id = get_user_id(app.current_event.raw_event)
    if not user_id:
        return {"error": "Unauthorized"}, 401

    try:
        resumes = get_resumes(user_id)

        if resumes is None:
            return {"error": "Profile not found"}, 404

        stored = resumes.get(resume_id)
        if stored is None:
            return {"error": "Resume not found"}, 404

        url = presign_download(stored["s3Key"], stored["name"])
    except Exception:
        # Includes SDK service/transport/signing failures and invalid stored data.
        # Exception messages can contain private data; never log their contents.
        logger.error("resume download failed")
        return {"error": "Internal server error"}, 500

    logger.info("resume download url created", extra={"user_id": user_id, "resume_id": resume_id})
    return {"downloadUrl": url, "expiresIn": URL_EXPIRES_IN}, 200


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST, log_event=False)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
