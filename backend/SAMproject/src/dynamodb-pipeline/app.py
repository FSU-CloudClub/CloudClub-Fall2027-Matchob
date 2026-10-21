import os                                                           # env vars
import boto3                                                        # AWS SDK
from botocore.exceptions import ClientError                         # AWS error type
from aws_lambda_powertools import Logger                            # structured JSON logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver  # router for API Gateway REST events
from aws_lambda_powertools.logging import correlation_paths         # where to find the request ID
from aws_lambda_powertools.utilities.typing import LambdaContext    # type hint for context
from matchob_common.auth import get_user_id                         # shared auth helper (layer)

# 1. Clients: once per container, reused while warm
#dynamodb = boto3.resource("dynamodb", endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None)  # local or AWS
#table = dynamodb.Table(os.environ["USERS_TABLE"])                   # our table

# DEBUG: Test whether boto3 can initialize a session
import time

start = time.perf_counter()                            # Start measuring elapsed time

print("DEBUG A: Before session", flush=True)           # Check whether execution reaches boto3

session = boto3.Session(                               # Create a boto3 session without making an API request
    aws_access_key_id="local",                         # Use local test credentials
    aws_secret_access_key="local",                     # Use local test credentials
    region_name="us-east-1"                            # Set the region explicitly
)

print("DEBUG B: Session created", flush=True)           # Check whether session initialization succeeds

dynamodb = session.resource(                           # Create DynamoDB resource from that session
    "dynamodb",                                         # Select DynamoDB
    endpoint_url="http://dynamodb:8000"                 # Point to local DynamoDB
)

print("DEBUG C: Resource created", flush=True)          # Confirm resource initialization completed

table = dynamodb.Table(os.environ["USERS_TABLE"])       # Reference the existing users table

print("DEBUG D: Table ready", flush=True)               # Confirm table initialization completed
print("Elapsed:", time.perf_counter() - start, flush=True)  # Display initialization duration

# 2. Powertools objects
logger = Logger()                                                   # service name from POWERTOOLS_SERVICE_NAME
app = APIGatewayRestResolver()                                      # matches method + path to a function


# 3. Routes: one function per method + path
@app.get("/profile")                                                # handles GET /profile
def get_profile():
    user_id = get_user_id(app.current_event.raw_event)              # Cognito sub (or X-Local-User locally)
    if not user_id:                                                 # not authenticated
        return {"error": "Unauthorized"}, 401                       # (body, status) tuple

    try:
        response = table.get_item(Key={"userId": user_id} )  # read profile
    except ClientError:
        logger.exception("dynamodb get_item failed")                # logs the stack trace as JSON
        return {"error": "Internal server error"}, 500              # generic message to the client

    if response is None:                                                # no profile yet
        return {"error": "Profile not found"}, 404

    logger.info("profile fetched", extra={"user_id": user_id})      # extra = searchable fields
    return response                                                     # plain dict → 200 + JSON body



# GET endpoint for retrieving validated core metadata
@app.get("/profile/core")                                         # Handles GET /profile/core requests
def get_core_metadata():                                          # Defines the core metadata function
    user_id = get_user_id(app.current_event.raw_event)            # Extracts the authenticated user's ID

    if not isinstance(user_id, str) or not user_id.strip():        # Validates that the ID is a non-empty string
        return {"error": "Unauthorized"}, 401                      # Rejects requests without a valid user ID

    try:                                                          # Attempts to retrieve the user's record
        response = table.get_item(Key={"userId": user_id})         # Searches DynamoDB using the authenticated ID
    except ClientError:                                           # Handles DynamoDB client errors
        logger.exception("Failed to retrieve core metadata")     # Logs the exception for debugging
        return {"error": "Internal server error"}, 500             # Returns a generic server error

    profile = response.get("Item")                                 # Extracts the stored user record

    if profile is None:                                           # Checks whether the user exists
        return {"error": "User not found"}, 404                    # Returns 404 when the record is missing

    required_fields = ("userId", "email", "firstName", "lastName")   # Defines the four required metadata attributes

    for field in required_fields:                                 # Checks each required field
        value = profile.get(field)                                # Retrieves the field's stored value
        if not isinstance(value, str) or not value.strip():        # Rejects missing, empty, or non-string values
            logger.error("Invalid core metadata", extra={"field": field})  # Records which field is invalid
            return {"error": "Incomplete core metadata"}, 500     # Reports invalid stored data

    if profile["userId"] != user_id:                               # Verifies the record belongs to the requested user
        logger.error("Core metadata user ID mismatch")            # Logs a record integrity problem
        return {"error": "Internal server error"}, 500             # Prevents returning mismatched data

    email = profile["email"]                                       # Reads the validated email string
    local, separator, domain = email.partition("@")                # Splits email into local and domain parts

    if not local or separator != "@" or not domain or "@" in domain:  # Checks basic email structure
        logger.error("Invalid email in core metadata")            # Logs an invalid stored email
        return {"error": "Invalid core metadata"}, 500             # Rejects malformed stored metadata

    core_metadata = {                                             # Constructs the successful response
        "userId": profile["userId"],                               # Includes the user's unique ID
        "email": profile["email"],                                 # Includes the user's email
        "firstName": profile["firstName"],                         # Includes the user's first name
        "lastName": profile["lastName"]                             # Includes the user's last name
    }                                                             # Ends the response dictionary

    logger.info("Core metadata retrieved", extra={"user_id": user_id})  # Logs successful retrieval
    return core_metadata                                          # Returns the metadata as JSON with HTTP 200



@app.post("/profile")                                              # handles POST /profile
def create_user():
    user_id = get_user_id(app.current_event.raw_event)              # authenticated user's ID
    if not user_id:
        return {"error": "Unauthorized"}, 401

    try:
        body = app.current_event.json_body                         # parse request JSON
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
            ConditionExpression="attribute_not_exists(userId)",   # prevent overwriting an existing user
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {"error": "Profile already exists"}, 409
        logger.exception("dynamodb put_item failed")
        return {"error": "Internal server error"}, 500

    logger.info("profile created", extra={"user_id": user_id})
    return item, 201                                               # created successfully

# 4. Entry point: always exactly this
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)  # adds request ID, cold_start to logs
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)                              # run the matching route

# import json
# import os
# import boto3
# from botocore.exceptions import ClientError
# from matchob_common.auth import get_user_id

# # Initialize DynamoDB outside the handler
# dynamodb = boto3.resource(
#     "dynamodb",
#     endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None
# )

# table = dynamodb.Table(os.environ["USERS_TABLE"])


# def lambda_handler(event, context):
#     print("USERS_TABLE:", os.environ.get("USERS_TABLE"))
#     print("DYNAMODB_ENDPOINT:", os.environ.get("DYNAMODB_ENDPOINT"))
#     # Extract authenticated user ID
#     # Extract authenticated user ID (claims in AWS, X-Local-User header under sam local)
#     user_id = get_user_id(event)


#     if not user_id:
#         return {
#             "statusCode": 401,
#             "body": json.dumps({"error": "Unauthorized"})
#         }

#     try:
#         # Retrieve profile from DynamoDB
#         response = table.get_item(
#             Key={"userId": user_id}
#         )

#         profile = response.get("Item")

#         if profile is None:
#             return {
#                 "statusCode": 404,
#                 "body": json.dumps({
#                     "error": "Profile not found"
#                 })
#             }

#         return {
#             "statusCode": 200,
#             "headers": {
#                 "Content-Type": "application/json"
#             },
#             "body": json.dumps(profile, default=str)
#         }

#     except ClientError as e:
#         print("DynamoDB ClientError:", repr(e))
#         return {
#             "statusCode": 500,
#             "body": json.dumps({"error": "Internal server error"})
#         }
