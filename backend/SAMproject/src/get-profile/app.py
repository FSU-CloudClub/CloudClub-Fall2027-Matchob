
import json
import os
import boto3
from botocore.exceptions import ClientError
from matchob_common.auth import get_user_id

# Initialize DynamoDB outside the handler
dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None
)

table = dynamodb.Table(os.environ["USERS_TABLE"])


def lambda_handler(event, context):
    print("USERS_TABLE:", os.environ.get("USERS_TABLE"))
    print("DYNAMODB_ENDPOINT:", os.environ.get("DYNAMODB_ENDPOINT"))
    # Extract authenticated user ID
    # Extract authenticated user ID (claims in AWS, X-Local-User header under sam local)
    user_id = get_user_id(event)


    if not user_id:
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "Unauthorized"})
        }

    try:
        # Retrieve profile from DynamoDB
        response = table.get_item(
            Key={"userId": user_id}
        )

        profile = response.get("Item")

        if profile is None:
            return {
                "statusCode": 404,
                "body": json.dumps({
                    "error": "Profile not found"
                })
            }

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps(profile, default=str)
        }

    except ClientError as e:
        print("DynamoDB ClientError:", repr(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"})
        }
