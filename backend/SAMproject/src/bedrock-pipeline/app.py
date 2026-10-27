from botocore.exceptions import ClientError, ReadTimeoutError
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from matchob_common.auth import get_user_id
from matchob_common.http import read_json_body, to_json
from matchob_common.validators import validate_fields
from bedrock_helpers import (
    ERROR_STATUS,
    SUGGESTION_FIELDS,
    call_bedrock,
    parse_reply,
    prompt_variables,
    was_blocked,
)

logger = Logger()
app = APIGatewayRestResolver(serializer=to_json)


# Add create_suggestions() here as @app.post("/suggestions"). Design:
# docs/bedrock-pipeline/endpoints/create-suggestions.md. The route is already in
# templates/bedrock-template.yaml, so until the function exists it returns 404.


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
