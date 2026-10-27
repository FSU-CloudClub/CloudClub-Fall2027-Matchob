import os

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

dynamodb = boto3.resource("dynamodb", endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None)
table = dynamodb.Table(os.environ["USERS_TABLE"])

bedrock = boto3.client("bedrock-runtime")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "")

logger = Logger()
app = APIGatewayRestResolver()

# No routes yet. Add them with @app.get / @app.post once the AI endpoints are in
# docs/general/api-contracts.md, and add the matching API and Events to templates/bedrock-template.yaml.


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
