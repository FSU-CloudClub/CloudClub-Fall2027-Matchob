import os

import boto3
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from matchob_common.auth import get_user_id
from matchob_common.http import read_json_body, to_json
from matchob_common.validators import validate_fields
from profile_helpers import PROFILE_FIELDS, profile_exists

dynamodb = boto3.resource("dynamodb", endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None)
table = dynamodb.Table(os.environ["USERS_TABLE"])

logger = Logger()
app = APIGatewayRestResolver(serializer=to_json)


@app.get("/profile")
def get_profile():
    """GET /profile: return the signed-in user's profile.

    Responses:
        200: The profile object.
        401: No authenticated user.
        404: The user has no profile yet.
        500: DynamoDB error.
    """
    user_id = get_user_id(app.current_event.raw_event)
    if not user_id:
        return {"error": "Unauthorized"}, 401

    try:
        response = table.get_item(Key={"userId": user_id})
    except ClientError:
        logger.exception("dynamodb get_item failed")
        return {"error": "Internal server error"}, 500

    item = response.get("Item")
    if item is None:
        return {"error": "Profile not found"}, 404

    logger.info("profile fetched", extra={"user_id": user_id})
    return item


@app.post("/profile")
def create_user():
    """POST /profile: create the signed-in user's profile.

    Body: every REQUIRED field in PROFILE_FIELDS; websites and defaultResume
    are optional. The backend adds userId, resumes ({}) and
    structuredJsonResume (null).

    Responses:
        201: The created profile object.
        400: Invalid JSON, a missing, invalid or unknown field, or a
            defaultResume (a new profile has no resumes yet).
        401: No authenticated user.
        409: The user already has a profile.
        500: DynamoDB error.
    """
    user_id = get_user_id(app.current_event.raw_event)
    if not user_id:
        return {"error": "Unauthorized"}, 401

    body, error = read_json_body(app.current_event)
    if error:
        return {"error": error}, 400

    fields, error = validate_fields(body, PROFILE_FIELDS, partial=False)
    if error:
        return {"error": error}, 400
    if fields["defaultResume"] is not None:
        return {"error": "defaultResume must be one of your resumes"}, 400

    item = {"userId": user_id, **fields, "resumes": {}, "structuredJsonResume": None}
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


@app.put("/profile")
def put_profile():
    """PUT /profile: update some or all fields of the signed-in user's profile.

    Body: any non-empty subset of PROFILE_FIELDS. Fields that are not sent
    keep their current values. A non-null defaultResume must be a key of
    the profile's resumes.

    Responses:
        200: The full updated profile object.
        400: Invalid JSON, an invalid or unknown field, no fields sent, or a
            defaultResume that isn't one of the user's resumes.
        401: No authenticated user.
        404: The user has no profile yet.
        500: DynamoDB error.
    """
    user_id = get_user_id(app.current_event.raw_event)
    if not user_id:
        return {"error": "Unauthorized"}, 401

    body, error = read_json_body(app.current_event)
    if error:
        return {"error": error}, 400

    updates, error = validate_fields(body, PROFILE_FIELDS, partial=True)
    if error:
        return {"error": error}, 400

    names = {f"#{k}": k for k in updates}
    condition = "attribute_exists(userId)"
    default_resume = updates.get("defaultResume")
    if default_resume is not None:
        names.update({"#resumes": "resumes", "#defaultResumeId": default_resume})
        condition += " AND attribute_exists(#resumes.#defaultResumeId)"

    try:
        result = table.update_item(
            Key={"userId": user_id},
            UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in updates),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues={f":{k}": v for k, v in updates.items()},
            ConditionExpression=condition,
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
            logger.exception("dynamodb update_item failed")
            return {"error": "Internal server error"}, 500
        if default_resume is not None and profile_exists(table, user_id):
            return {"error": "defaultResume must be one of your resumes"}, 400
        return {"error": "Profile not found"}, 404

    logger.info("profile updated", extra={"user_id": user_id})
    return result["Attributes"], 200


@app.delete("/profile")
def delete_user():
    """DELETE /profile: delete the signed-in user's profile.

    Responses:
        200: {"message": "Profile deleted"}.
        401: No authenticated user.
        404: The user has no profile.
        500: DynamoDB error.
    """
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


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
