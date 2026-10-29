import os
import re
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, Response
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from matchob_common.auth import get_user_id
from matchob_common.http import read_json_body, to_json
from matchob_common.validators import validate_fields
from resume_helpers import (
    BUCKET,
    UPLOAD_FIELDS,
    RESUME_FIELDS,
    get_resumes,
    now_iso,
    presign_upload,
    resume_path_names,
    s3_key,
    table,
    to_resume_object,
)

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ.get("S3_ENDPOINT") or None,
    config=Config(s3={"addressing_style": "path"}),
)

logger = Logger()
app = APIGatewayRestResolver(serializer=to_json)

@app.exception_handler(Exception)
def handle_unexpected_error(error):
    logger.error("unexpected resumes failure", extra={"error_type": type(error).__name__})
    return Response(status_code=500, content_type="application/json",
                    body=to_json({"error": "Internal server error"}))


@app.delete("/resumes/<resume_id>")
def delete_resume(resume_id):
    user_id = get_user_id(app.current_event.raw_event)
    if user_id is None:
        return {"error": "Unauthorized"}, 401

    # Accept UUIDs and existing opaque IDs, without whitespace or path separators.
    if not isinstance(resume_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", resume_id):
        return {"error": "Invalid resume ID"}, 400

    try:
        result = table.update_item(
            Key={"userId": user_id},
            UpdateExpression="REMOVE #resumes.#resumeId",
            ExpressionAttributeNames=resume_path_names(resume_id),
            ConditionExpression="attribute_exists(#resumes.#resumeId)",
            ReturnValues="ALL_OLD",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {"error": "Resume not found"}, 404
        logger.error("dynamodb update_item failed")
        return {"error": "Internal server error"}, 500

    except BotoCoreError:
        logger.error("dynamodb request failed")
        return {"error": "Internal server error"}, 500

    old = result["Attributes"]
    stored = old["resumes"][resume_id]
    if old.get("defaultResume") == resume_id:
        try:
            table.update_item(
                Key={"userId": user_id},
                UpdateExpression="SET #defaultResume = :null",
                ExpressionAttributeNames={"#defaultResume": "defaultResume"},
                ExpressionAttributeValues={":null": None, ":resumeId": resume_id},
                ConditionExpression="#defaultResume = :resumeId",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                logger.error("clear defaultResume failed")
        except BotoCoreError:
            logger.error("clear defaultResume request failed")

    try:
        s3.delete_object(Bucket=BUCKET, Key=stored["s3Key"])
    except (ClientError, BotoCoreError):
        logger.error("s3 delete_object failed")

    logger.info("resume deleted", extra={"user_id": user_id, "resume_id": resume_id})
    return {"message": "Resume deleted"}

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
        logger.error("dynamodb update_item failed")
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


@app.patch("/resumes/<resume_id>")                              # registers the PATCH endpoint for a specific resume
def update_resume(resume_id):                                   # defines the function and receives the resume ID from the URL
    """Update an existing resume's name, tags, or both."""      # describes the purpose of this function

    user_id = get_user_id(app.current_event.raw_event)          # retrieves the authenticated user's ID from the request

    if not user_id:                                              # checks whether authentication failed
        return {"error": "Unauthorized"}, 401                    # returns HTTP 401 if no authenticated user exists

    body, error = read_json_body(app.current_event)             # parses the incoming JSON and checks for parsing errors

    if error:                                                    # checks whether the JSON body is invalid
        return {"error": error}, 400                             # returns HTTP 400 with the validation error

    fields, error = validate_fields(                             # validates the fields supplied by the user
        body,                                                   # passes the parsed JSON request body
        RESUME_FIELDS,                                          # allows only the name and tags fields
        partial=True                                            # permits updating either field individually or both
    )

    if error:                                                    # checks whether field validation failed
        return {"error": error}, 400                             # returns HTTP 400 if the supplied fields are invalid

    updates = []                                                  # stores the DynamoDB SET expressions for fields being updated
    names = resume_path_names(resume_id)                           # maps the resumes attribute and resume ID to safe DynamoDB placeholders
    values = {}                                                    # stores the validated values that DynamoDB will write

    if "name" in fields:                                           # checks whether the user provided a new resume name
        updates.append("#resumes.#resumeId.#name = :name")         # adds the name field to the DynamoDB update expression
        names["#name"] = "name"                                     # maps the #name placeholder to the actual name attribute
        values[":name"] = fields["name"]                            # stores the validated resume name for the update

    if "tags" in fields:                                           # checks whether the user provided replacement tags
        updates.append("#resumes.#resumeId.#tags = :tags")         # adds the tags field to the DynamoDB update expression
        names["#tags"] = "tags"                                     # maps the #tags placeholder to the actual tags attribute
        values[":tags"] = fields["tags"]                            # stores the validated replacement tags

    if not updates:                                                   # prevents running an empty DynamoDB update
        return {"error": "No fields provided"}, 400                  # returns HTTP 400 if neither name nor tags was supplied

    update_expression = "SET " + ", ".join(updates)                # combines the requested field updates into one DynamoDB SET statement

    try:                                                              # begins the database operation and catches potential errors
        response = table.update_item(                                 # updates the selected resume in DynamoDB
            Key={"userId": user_id},                                   # identifies the authenticated user's DynamoDB record
            UpdateExpression=update_expression,                        # specifies which resume fields should be changed
            ExpressionAttributeNames=names,                            # supplies the safe attribute-name placeholders
            ExpressionAttributeValues=values,                          # supplies the validated new field values
            ConditionExpression="attribute_exists(#resumes.#resumeId)", # only updates a resume that already exists
            ReturnValues="ALL_NEW",                                    # returns the user's updated DynamoDB attributes
        )

    except ClientError as error:                                       # catches errors returned by DynamoDB
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":  # checks whether the resume was missing
            return {"error": "Resume not found"}, 404                  # returns HTTP 404 without creating a new resume

        logger.error("dynamodb update_item failed")               # logs unexpected DynamoDB errors for investigation
        return {"error": "Internal server error"}, 500                # returns HTTP 500 for an unexpected database failure

    updated_item = response["Attributes"]                              # retrieves the updated DynamoDB user record
    stored_resume = updated_item["resumes"][resume_id]                 # extracts the updated resume's metadata

    resume = to_resume_object(resume_id, stored_resume)                # formats the metadata into the expected API resume object

    logger.info(                                  # logs the successful resume update
        "resume updated",                          # identifies the completed operation
        extra={                                    # attaches additional information to the log
            "user_id": user_id,                    # records which user owns the resume
            "resume_id": resume_id,                # records which resume was updated
            "fields": list(fields),                # records which fields changed without exposing their values
        },
    )
    return resume, 200                                                 # returns the updated resume with HTTP 200

# Never log request bodies, even if POWERTOOLS_LOGGER_LOG_EVENT is enabled.
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST, log_event=False)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
