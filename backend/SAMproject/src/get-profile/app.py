import os     
import boto3                                                        # AWS SDK
from botocore.exceptions import ClientError                         # AWS error type
from aws_lambda_powertools import Logger                            # structured JSON logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver  # router for API Gateway REST events
from aws_lambda_powertools.logging import correlation_paths         # where to find the request ID
from aws_lambda_powertools.utilities.typing import LambdaContext    # type hint for context
from matchob_common.auth import get_user_id                         # shared auth helper (layer)

# 1. Clients: once per container, reused while warm
dynamodb = boto3.resource("dynamodb", endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None)  # local or AWS
table = dynamodb.Table(os.environ["USERS_TABLE"])                   # our table

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
        item = table.get_item(Key={"userId": user_id}).get("Item")  # read profile
    except ClientError:
        logger.exception("dynamodb get_item failed")                # logs the stack trace as JSON
        return {"error": "Internal server error"}, 500              # generic message to the client

    if item is None:                                                # no profile yet
        return {"error": "Profile not found"}, 404

    logger.info("profile fetched", extra={"user_id": user_id})      # extra = searchable fields
    return item                                                     # plain dict → 200 + JSON body

@app.put("/profile")                                                # handles PUT /profile
def put_profile():
    user_id = get_user_id(app.current_event.raw_event)
    if not user_id:
        return {"error": "Unauthorized"}, 401
    
    try:
        body = app.current_event.json_body
        if not body:
            return {"error": "Failed to get request body"}, 400
    
        body["userId"] = user_id # make sure user id is set to authenticated user
    
        table.put_item(Item=body) # write profile
    #client error check
    except ClientError:
        logger.exception("dynamodb put_item failed")
        return {"error": "Internal server error"}, 500
    
    logger.info("profile updated", extra={"user_id": user_id})
    return {"message": "Profile updated", "Profile": body}, 200


    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
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
