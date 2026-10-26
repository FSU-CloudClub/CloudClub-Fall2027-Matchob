import os

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from matchob_common.auth import get_user_id
from matchob_common.http import to_json
from resume_helpers import BUCKET, resume_path_names, table

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ.get("S3_ENDPOINT") or None,
    config=Config(s3={"addressing_style": "path"}),
)

logger = Logger()
app = APIGatewayRestResolver(serializer=to_json)

@app.delete("/resumes/<resume_id>")
def delete_resume(resume_id):
    user_id = get_user_id(app.current_event.raw_event)
    if user_id is None:
        return {"error": "Unauthorized"}, 401

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
        logger.exception("dynamodb update_item failed")
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
                logger.exception("clear defaultResume failed")

    try:
        s3.delete_object(Bucket=BUCKET, Key=stored["s3Key"])
    except ClientError:
        logger.exception("s3 delete_object failed", extra={"s3_key": stored["s3Key"]})

    logger.info("resume deleted", extra={"user_id": user_id, "resume_id": resume_id})
    return {"message": "Resume deleted"}


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
