# Lambda Powertools: Handler Format

**Purpose:** The standard structure every Lambda handler follows.
**Tech:** Powertools for AWS Lambda (Python) v3: `Logger` + `APIGatewayRestResolver`.
**Role in the project:** Gives every endpoint the same routing, JSON responses, and structured logs, so handlers stay short and logs can be searched in CloudWatch.

## Example: GET /profile written in this format

```python
import os                                                           # env vars
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


# 4. Entry point: always exactly this
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)  # adds request ID, cold_start to logs
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)                              # run the matching route
```

## Minimum requirements

1. **Dependency:** `aws-lambda-powertools>=3.35,<4` in `src/shared/requirements.txt`. The shared layer installs it, so every function gets it.
2. **Env vars:**
   - `POWERTOOLS_LOG_LEVEL: INFO` in `Globals → Function → Environment`
   - `POWERTOOLS_SERVICE_NAME: <function-name>` in each function's own `Environment` (see [adding-lambda-functions.md](adding-lambda-functions.md))
3. **Python 3.10+.** We use 3.13.
4. Run `sam build` after adding the dependency.

## File format (the order every `app.py` follows)

1. **Imports:** stdlib, then boto3, then Powertools, then `matchob_common`.
2. **Clients:** boto3 clients and tables at module level, never inside routes.
3. **Powertools objects:** `logger` and `app`.
4. **Routes:** one decorated function per method and path. Read the user with `get_user_id(app.current_event.raw_event)` first.
5. **`lambda_handler`:** always the same two lines. Don't put logic here.

## Response rules

| Return | Result |
|---|---|
| `dict` / `list` | 200, JSON body, `Content-Type: application/json` |
| `(dict, 404)` | That status code with a JSON body |
| Errors | Always `{"error": "<message>"}`, matching `auth-contract.md` |

DynamoDB `Decimal` values are serialized as **strings** (`"age": "21"`). Convert them to `int` before returning if the frontend needs numbers.

## What's happening

- **Routing.** API Gateway sends every request as one big `event` dict. `app.resolve()` reads `httpMethod` and `path`, calls the matching decorated function, and turns its return value into the `{statusCode, headers, body}` shape API Gateway expects. You never build that dict by hand. An unknown route returns 404 automatically.
- **Request data.** `app.current_event` gives typed access to the request: `.json_body` (parsed body), `.query_string_parameters`, `.headers`, `.path_parameters`. Use `.raw_event` only to pass the event to `get_user_id`.
- **Path params.** `@app.get("/jobs/<job_id>")` passes `job_id` as a function argument. The path must also exist as an `Events` route in the template.
- **Logging.** `logger.info(...)` prints one JSON line with `service`, `level`, `cold_start`, `function_request_id` and `correlation_id` (the API Gateway request ID). Put searchable details in `extra={...}`. Never log tokens or full request bodies. Use `logger.exception` inside `except` to include the stack trace.
- **One function per resource.** A Lambda can hold several routes (e.g. GET and PUT `/profile` in one `app.py`), but each route still needs its own `Events` entry in the template.
