# Glossary

**Purpose:** Plain definitions of the terms used across the backend docs.
**Role in the project:** Every doc links here at the bottom, so the docs themselves can stay short.

Terms are grouped by topic. Code names (`table`, `s3`) refer to the objects at the top of each `app.py`.

## AWS and infrastructure

| Term | Meaning |
|---|---|
| **AWS SAM** | Serverless Application Model. A tool and template format for Lambda apps. `sam build`, `sam local` and `sam deploy` all read `template.yaml` |
| **CloudFormation** | The AWS service that creates and updates resources from a template. SAM templates are turned into CloudFormation templates |
| **IaC** | Infrastructure as code. The cloud resources are described in files (our YAML templates), not clicked together in the AWS console |
| **Template** | A YAML file listing resources. Ours: `template.yaml` (root) and `templates/*.yaml` (one per service) |
| **Stack** | The set of resources CloudFormation created from one template, managed as a unit |
| **Nested stack** | A stack created by another stack. Our root stack creates `SharedStack`, `ProfileStack`, `ResumesStack` and `BedrockStack`. See [nested-stacks.md](nested-stacks.md) |
| **Resource** (template) | One thing a template creates, like a table, bucket, API or function. Each has a **logical ID** such as `ProfileFunction` |
| **Parameter** / **Output** | A value a template takes in / hands out. The root passes one stack's output into another's parameter with `!GetAtt` |
| **`!Ref`, `!GetAtt`, `!Sub`** | Template functions: the resource's main value (usually its name or ID), one of its attributes, and string substitution |
| **Globals** | Template section with defaults (runtime, timeout, layer, environment variables) for every function in that template |
| **Lambda** | AWS's run-code-on-request service. Our Python code runs as Lambda functions with no server to manage |
| **Handler** | The function Lambda calls: `lambda_handler(event, context)` in `app.py`. Ours always just calls `app.resolve` |
| **Event** (Lambda) | The dict Lambda passes to the handler. For API calls it holds the method, path, headers, body and auth claims |
| **Event** (template) | Under a function's `Events:`, a trigger for that function, such as one API route |
| **Cold start** | The first request to a new Lambda container, which also runs the module-level code (creating clients). Later "warm" requests reuse it |
| **Layer** | Code packaged once and attached to Lambdas. Ours, `SharedLayer`, holds `matchob_common` and the shared dependencies |
| **IAM role / policy** | The permissions a Lambda has. Set under `Policies:` in the template, e.g. `DynamoDBCrudPolicy` |
| **API Gateway** | The AWS service that receives HTTP requests and calls the right Lambda |
| **Route** | One method + path, like `GET /profile` |
| **Stage** | A named deployment of an API. Ours is `dev`, which is why URLs end in `/dev` |
| **Cognito** | AWS's sign-up and login service |
| **User pool** | Our Cognito user directory. **App client** is the frontend's registration with it |
| **Authorizer** | API Gateway's token check that runs before the Lambda. Ours checks the Cognito token |
| **ID token** | What the frontend gets after login and sends in the `Authorization` header. A JWT holding claims about the user |
| **Claims** / **`sub`** | Fields inside the token. `sub` is the user's permanent unique ID, which we use as `userId` |
| **Environment variable** | A setting passed to the Lambda, read with `os.environ`. Set in the template, and overridden locally by `env.json` |

## DynamoDB

| Term | Meaning |
|---|---|
| **DynamoDB** | AWS's NoSQL database. We use one table, `MatchobUsers` |
| **Table** / **Item** / **Attribute** | A table holds items (like rows). An item is a set of attributes (like columns), and different items can have different attributes |
| **Partition key** | The attribute every item is looked up by. Ours is `userId` |
| **Map** / **List** | A nested object / array stored inside an attribute. `resumes` is a map |
| **Document path** | A path into nested data, like `resumes.3f6c....name` |
| **`get_item`, `put_item`, `update_item`, `delete_item`** | Read one item; create or fully replace one; change some attributes; delete one |
| **`UpdateExpression`** | What `update_item` changes: `SET a = :v`, `REMOVE a` |
| **`ConditionExpression`** | A check DynamoDB makes as part of the write. If it's false, nothing is written and `ConditionalCheckFailedException` is raised |
| **`ExpressionAttributeNames`** / **`Values`** | Placeholders in expressions: `#name` for attribute names (required for reserved words and map keys), `:value` for values |
| **`ProjectionExpression`** | Which attributes a read returns. Smaller reads for big items |
| **`ReturnValues`** | What a write returns: `ALL_NEW` (item after), `ALL_OLD` (item before), `UPDATED_NEW` (changed attributes only) |
| **Reserved word** | A word DynamoDB won't accept as a bare attribute name in expressions, e.g. `name`, `year`. Use a `#placeholder` |
| **`Decimal`** | The Python type DynamoDB returns for every number |
| **Item size limit** | 400 KB per item. Big data doesn't belong on the profile |
| **DynamoDB Local** | A DynamoDB emulator that runs in Docker at `localhost:8000` |

## S3

| Term | Meaning |
|---|---|
| **S3** | AWS's file storage |
| **Bucket** | A named container for files. Ours is `UploadBucket` (`matchob-uploads` locally) |
| **Object** / **Key** | A stored file / its full path in the bucket, like `users/abc/resumes/3f6c....pdf`. There are no real folders; `/` is just part of the key |
| **Presigned URL** | A temporary URL that lets whoever has it do one operation (upload or download one object) with the Lambda's permissions, without AWS credentials |
| **Presign** | Create a presigned URL. Done locally by boto3 with no network call |
| **`Content-Type`** | The file's media type, e.g. `application/pdf`. Signed into upload URLs, so the upload must send the same one |
| **`Content-Disposition`** | Tells the browser to show a file (`inline`) or save it, and under what filename |
| **Path vs virtual addressing** | Bucket in the URL path (`host/bucket/key`) vs in the hostname (`bucket.host/key`). s3mock needs path; real S3 prefers virtual |
| **CORS** | Browser rule: a page can only call another origin if that server allows it. The bucket allows `GET`/`PUT` so the browser can use presigned URLs |
| **Orphaned file** | A file in S3 that no profile points at anymore |
| **s3mock** | An S3 emulator that runs in Docker at `localhost:9090` |

## Python and boto3

| Term | Meaning |
|---|---|
| **boto3** | The AWS SDK for Python |
| **Client** | A low-level boto3 object with one method per AWS API call, taking and returning plain dicts: `boto3.client("s3")`. Our `s3`, `presign_client` and `bedrock` are clients |
| **Resource** (boto3) | A higher-level boto3 object that converts DynamoDB types for you: `boto3.resource("dynamodb").Table(...)`. Our `table` comes from a resource |
| **`endpoint_url`** | Where a client sends requests. `None` means real AWS; locally it's the Docker container |
| **`ClientError`** | The exception boto3 raises when AWS rejects a call. `error.response["Error"]["Code"]` says why, e.g. `ConditionalCheckFailedException` |
| **`ParamValidationError`** | Raised by boto3 before calling AWS, for a misspelled or wrong-type parameter. Not a `ClientError` |
| **Module level** | Code outside any function in `app.py`. Runs once per cold start, which is why clients go there |
| **Helper** | A small function routes share. Shared ones are in `matchob_common` ([shared-helpers.md](shared-helpers.md)); pipeline ones in `<name>_helpers.py` |
| **Validator** | A helper that checks one field and returns the cleaned value, or raises `ValueError` |
| **Spec** | The `{field: (default, validator)}` dict `validate_fields` checks a body against, e.g. `PROFILE_FIELDS` |
| **`REQUIRED`** | The marker in a spec for fields that must be sent on create |
| **UUID** | A random unique ID, from `uuid.uuid4()`. Used for resume IDs |
| **ISO 8601** | The timestamp format we use: `2026-10-22T14:03:00Z` (UTC) |

## Powertools

| Term | Meaning |
|---|---|
| **Powertools** | AWS Lambda Powertools for Python, a library for routing and logging. See [powertools.md](powertools.md) |
| **Resolver** (`app`) | `APIGatewayRestResolver`. Matches each request to a route function and turns its return value into an HTTP response |
| **Route function** | A function decorated with `@app.get(...)` etc. Returns a dict (200) or `(dict, status)` |
| **`app.current_event`** | The current request, with `.json_body`, `.path_parameters`, `.headers` and `.raw_event` |
| **Path parameter** | A variable part of the path: `{resumeId}` in the template, `<resume_id>` in Powertools, passed as a function argument |
| **Serializer** | The function that turns a route's return value into JSON. Ours is `to_json`, which handles `Decimal` |
| **Logger** | Powertools' logger. Prints one JSON line per call. `logger.info` for normal events, `logger.exception` inside `except` to include the stack trace |
| **Correlation ID** | The API Gateway request ID, attached to every log line of one request so they can be found together |
| **Service name** | `POWERTOOLS_SERVICE_NAME`, shown in every log line (`profile`, `resumes`, `bedrock`) |

## API and HTTP

| Term | Meaning |
|---|---|
| **Endpoint** | One route the frontend can call, like `PUT /profile`. (Different from `endpoint_url`) |
| **Contract** | The agreed request and response for each endpoint. Ours is [api-contracts.md](api-contracts.md) |
| **Body** / **Payload** | The JSON sent with a request or response |
| **`GET`, `POST`, `PUT`, `PATCH`, `DELETE`** | Read; create; update (ours is partial); partial update; delete |
| **Partial update** | Only the fields sent change. Both `PUT /profile` and `PATCH /resumes/{id}` work this way |
| **Status code** | `200` OK, `201` created, `400` bad request, `401` not signed in, `404` not found, `409` already exists, `500` server error, `501` not implemented |
| **Backend-only field** | A field the client can see but not send, like `userId` or `resumes`. Rejected as unknown |

## Local development

| Term | Meaning |
|---|---|
| **`dev.py`** | Starts Docker Compose (DynamoDB Local, s3mock, seed data) and `sam local start-api` on port 3001. See [setup.md](setup.md) |
| **`sam local start-api`** | Runs the APIs and Lambdas on your machine, each Lambda in a Docker container |
| **Docker** / **Compose** | Runs the emulators in containers. `compose.yaml` defines them |
| **`env.json`** | Local environment variable overrides for every function. Not committed; copy `env.example.json` |
| **Seed data** | Test data loaded into DynamoDB Local on start, from `docker/seed/users.json` |
| **`X-Local-User`** | Header that stands in for a Cognito login under `sam local`. See [auth.md](auth.md) |
| **`s3:9090` vs `localhost:9090`** | The same s3mock, by its name inside the Docker network and from your machine |
