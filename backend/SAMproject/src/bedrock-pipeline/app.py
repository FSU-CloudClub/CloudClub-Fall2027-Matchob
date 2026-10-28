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


@app.post("/suggestions")
def create_suggestions():
    """Validate the caller's inputs and return the console prompt's JSON reply."""
    user_id = get_user_id(app.current_event.raw_event)
    if user_id is None:
        return {"error": "Unauthorized"}, 401

    body, error = read_json_body(app.current_event)
    if error:
        return {"error": error}, 400

    fields, error = validate_fields(body, SUGGESTION_FIELDS, partial=False)
    if error:
        return {"error": error}, 400

    variables = prompt_variables(fields)
    try:
        response = call_bedrock(variables)
    except ClientError as error:
        code = error.response["Error"]["Code"]
        status = ERROR_STATUS.get(code, 500)
        if status == 503:
            logger.warning("bedrock busy", extra={"code": code})
            return {"error": "AI service is busy, try again"}, status
        if status == 504:
            logger.warning("bedrock timed out")
            return {"error": "AI service timed out"}, status
        logger.exception("bedrock converse failed")
        return {"error": "Internal server error"}, status
    except ReadTimeoutError:
        logger.warning("bedrock timed out")
        return {"error": "AI service timed out"}, 504

    log_context = {"user_id": user_id, "stop_reason": response.get("stopReason")}
    # Blocked replies can be plain text, so check before parsing JSON.
    if was_blocked(response):
        logger.info("suggestions blocked", extra=log_context)
        return {"error": "Request blocked by content filters"}, 422

    reply = parse_reply(response)
    if reply is None:
        logger.error("invalid model reply", extra=log_context)
        return {"error": "AI returned an invalid response"}, 502

    logger.info("suggestions created", extra=log_context)
    return reply


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
