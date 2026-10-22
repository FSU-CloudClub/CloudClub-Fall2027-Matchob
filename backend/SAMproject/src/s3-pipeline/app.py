import os

import boto3
from botocore.config import Config
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from matchob_common.http import to_json
from resume_helpers import BUCKET, table

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ.get("S3_ENDPOINT") or None,
    config=Config(s3={"addressing_style": "path"}),
)

logger = Logger()
app = APIGatewayRestResolver(serializer=to_json)

# No routes yet. Add one function per endpoint in the Resumes section of
# docs/general/api-contracts.md, e.g. @app.get("/resumes"). The routes are already in
# templates/s3-template.yaml, so until a function exists here they return 404.


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
