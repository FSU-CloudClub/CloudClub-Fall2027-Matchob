import os
import boto3
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from matchob_common.auth import get_user_id

dynamodb = boto3.resource("dynamodb", endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None)
table = dynamodb.Table(os.environ["USERS_TABLE"])

logger = Logger()
app = APIGatewayRestResolver()


@app.get("/profile")
def get_profile():
    user_id = get_user_id(app.current_event.raw_event)
    if not user_id:
        return {"error": "Unauthorized"}, 401

    try:
        response = table.get_item(Key={"userId": user_id})
    except ClientError:
        logger.exception("dynamodb get_item failed")
        return {"error": "Internal server error"}, 500

    if response is None:
        return {"error": "Profile not found"}, 404

    logger.info("profile fetched", extra={"user_id": user_id})
    return response

@app.post("/profile")
def create_user():
    user_id = get_user_id(app.current_event.raw_event)
    if not user_id:
        return {"error": "Unauthorized"}, 401

    try:
        body = app.current_event.json_body
    except (ValueError, TypeError):
        return {"error": "Invalid JSON body"}, 400

    if not isinstance(body, dict):
        return {"error": "Request body must be a JSON object"}, 400

    name = body.get("name")
    education = body.get("education")
    if not isinstance(name, str) or not name.strip():
        return {"error": "name must be a non-empty string"}, 400
    if not isinstance(education, str) or not education.strip():
        return {"error": "education must be a non-empty string"}, 400

    item = {"userId": user_id, "name": name.strip(), "education": education.strip()}
    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(userId)",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {"error": "Profile already exists"}, 409
        logger.exception("dynamodb put_item failed")
        return {"error": "Internal server error"}, 500

    logger.info("profile created", extra={"user_id": user_id})
    return item, 201

@app.delete("/profile")
def delete_user():
    user_id = get_user_id(app.current_event.raw_event)
    if not user_id:
        return {"error": "Unauthorized"}, 401

    try:
        item = table.delete_item(
            Key={"userId": user_id},
            ReturnValues="ALL_OLD",
        ).get("Attributes")
    except ClientError:
        logger.exception("dynamodb delete_item failed")
        return {"error": "Internal server error"}, 500

    if item is None:
        return {"error": "Profile not found"}, 404

    logger.info("profile deleted", extra={"user_id": user_id})
    return {"message": "Profile deleted"}


@app.put("/profile")
def put_profile():
    user_id = get_user_id(app.current_event.raw_event)
    if not user_id:
        return {"error": "Unauthorized"}, 401

    try:
        body = app.current_event.json_body
        if not body:
            return {"error": "Failed to get request body"}, 400

        body["userId"] = user_id

        table.put_item(Item=body)
    except ClientError:
        logger.exception("dynamodb put_item failed")
        return {"error": "Internal server error"}, 500

    logger.info("profile updated", extra={"user_id": user_id})
    return {"message": "Profile updated", "Profile": body}, 200


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
