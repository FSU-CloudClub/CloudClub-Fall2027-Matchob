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


# GET endpoint for retrieving a user's core metadata
@app.get("/profile/core")                                          # Handles GET /profile/core requests
def get_core_metadata():                                           # Defines the core metadata function
    user_id = get_user_id(app.current_event.raw_event)             # Extracts authenticated user ID from the request

    if not user_id:                                                # Checks whether the user is authenticated
        return {"error": "Unauthorized"}, 401                       # Returns HTTP 401 if authentication fails

    try:                                                           # Attempts to retrieve user data from DynamoDB
        response = table.get_item(Key={"userId": user_id})         # Searches DynamoDB using the user's unique ID
    except ClientError:                                            # Catches AWS DynamoDB client errors
        logger.exception("Failed to retrieve core metadata")      # Logs the error and stack trace
        return {"error": "Internal server error"}, 500             # Returns HTTP 500 without exposing internal details

    profile = response.get("Item")                                 # Extracts the user record from DynamoDB's response

    if profile is None:                                            # Checks whether the user record exists
        return {"error": "User not found"}, 404                     # Returns HTTP 404 if no matching user exists

    core_metadata = {                                              # Creates a dictionary containing only required fields
        "userId": profile.get("userId"),                            # Retrieves the user's unique identifier
        "email": profile.get("email"),                              # Retrieves the user's email address
        "firstName": profile.get("firstName"),                      # Retrieves the user's first name
        "lastName": profile.get("lastName")                         # Retrieves the user's last name
    }                                                              # Ends the core metadata dictionary

    logger.info("Core metadata retrieved", extra={"user_id": user_id})  # Logs successful metadata retrieval

    return core_metadata                                           # Returns the four metadata fields as a JSON response




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
