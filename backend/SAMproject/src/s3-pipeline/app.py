# Tools for reading settings and creating a unique ID for each new resume.
import os
import uuid     #to generate random
import boto3    #lets us talk to aws
from botocore.config import Config   #how we talk to aws, specifically formatting s3 address
from botocore.exceptions import ClientError  #for exception handling
from aws_lambda_powertools import Logger #for logs
from aws_lambda_powertools.event_handler import APIGatewayRestResolver  #match requests like GET /resumes to functions that handle them
from aws_lambda_powertools.logging import correlation_paths      #pairs log messages with request IDs
#describes the run information AWS passes to our handler; helps editor suggestions.
from aws_lambda_powertools.utilities.typing import LambdaContext
#our shared code for identifying users, reading/writing JSON and checking inputs
from matchob_common.auth import get_user_id
from matchob_common.http import read_json_body, to_json
from matchob_common.validators import validate_fields
#resume specific tools
from resume_helpers import (
    BUCKET,
    UPLOAD_FIELDS,
    get_resumes,
    now_iso,
    presign_upload,
    resume_path_names,
    s3_key,
    table,
    to_resume_object,
)

#set up S3; use the local service when S3_ENDPOINT is provided
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ.get("S3_ENDPOINT") or None,
    config=Config(s3={"addressing_style": "path"}),
)

#create logger and router to match requests to their correct functions
logger = Logger()
app = APIGatewayRestResolver(serializer=to_json)


#add one function per endpoint in the resumes section of
#docs/general/api-contracts.md, e.g @app.get("/resumes")
#the routes are already in
#templates/s3-template.yaml, so until a function exists here they return 404
@app.post("/resumes/upload-url")
def create_upload_url():
    """Store resume metadata on the caller's profile, then return a signed upload URL."""
    #identify caller. stop if we cant identify a user
    user_id = get_user_id(app.current_event.raw_event)
    if not user_id:
        return {"error": "Unauthorized"}, 401

    #read submitted json checking both file name + type
    body, error = read_json_body(app.current_event)
    if error:
        return {"error": error}, 400

    fields, error = validate_fields(body, UPLOAD_FIELDS, partial=False)
    if error:
        return {"error": error}, 400

    #give the resume a new ID and prepare its file location and saved details
    #(just describing the file for now)
    resume_id = str(uuid.uuid4())
    key = s3_key(user_id, resume_id, fields["contentType"])
    stored = {
        "s3Key": key,
        "name": fields["fileName"],
        "tags": [],
        "contentType": fields["contentType"],
        "uploadedAt": now_iso(),
    }
    #add resume details to existing profile without overwriting other resumes
    try:
        table.update_item(
            Key={"userId": user_id},
            UpdateExpression="SET #resumes.#resumeId = :resume",
            ExpressionAttributeNames=resume_path_names(resume_id),
            ExpressionAttributeValues={":resume": stored},
            ConditionExpression="attribute_exists(userId)",
        )
    except ClientError as error:
        #missing profile is a 404 error; other database failures return 500
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {"error": "Profile not found"}, 404
        logger.exception("dynamodb update_item failed")
        return {"error": "Internal server error"}, 500

    #return a temp link so the frontend can upload the file directly to S3
    upload_url = presign_upload(key, fields["contentType"])
    logger.info("resume upload url created", extra={"user_id": user_id, "resume_id": resume_id})
    return {"resumeId": resume_id, "uploadUrl": upload_url}, 201


#run this function when the frontend sends GET /resumes.
@app.get("/resumes")
def list_resumes():
    """Return the caller's resumes, newest first, with fresh download links."""
    #only read resumes for the user identified by this request
    user_id = get_user_id(app.current_event.raw_event)
    if not user_id:
        return {"error": "Unauthorized"}, 401

    #read resume details and if aws rejects it return an error
    try:
        resumes = get_resumes(user_id)
    except ClientError:
        logger.exception("dynamodb get_item failed")
        return {"error": "Internal server error"}, 500

    #None means the profile is missing; an empty map means the user has no resumes
    if resumes is None:
        return {"error": "Profile not found"}, 404

    #sort by upload time with newest first
    #for each resume add a fresh download link
    #leave the internal s3Key out of the returned fields. An empty map gives [].
    result = [
        to_resume_object(resume_id, stored)
        for resume_id, stored in sorted(
            resumes.items(), key=lambda item: item[1]["uploadedAt"], reverse=True
        )
    ]
    #record how many resumes we returned, then send the list with 200 (success).
    logger.info("resumes listed", extra={"user_id": user_id, "count": len(result)})
    return result, 200


# attach run details and the request ID to logs for this request
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    #AWS starts here. The router picks the endpoint function and formats its response.
    return app.resolve(event, context)
