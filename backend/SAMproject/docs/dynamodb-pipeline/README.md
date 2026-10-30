# Profile Pipeline (DynamoDB)

**Purpose:** Create, read, update and delete the signed-in user's profile.
**Tech:** Python 3.13, Powertools, boto3 DynamoDB resource API.
**Role in the project:** Every other feature reads the profile. The resumes pipeline also writes its `resumes` map.

| | |
|---|---|
| Template | `templates/dynamodb-template.yaml` (`ProfileStack` in the root) |
| Code | `src/dynamodb-pipeline/app.py`, `src/dynamodb-pipeline/profile_helpers.py` |
| Contract | [api-contracts.md → Profile](../general/api-contracts.md#profile) |
| Helpers | [helpers.md](helpers.md) and [shared-helpers.md](../general/shared-helpers.md) |

## Endpoints

| Endpoint | Function | Doc |
|---|---|---|
| `GET /profile` | `get_profile()` | [get-profile.md](endpoints/get-profile.md) |
| `POST /profile` | `create_user()` | [post-profile.md](endpoints/post-profile.md) |
| `PUT /profile` | `put_profile()` | [put-profile.md](endpoints/put-profile.md) |
| `DELETE /profile` | `delete_user()` | [delete-profile.md](endpoints/delete-profile.md) |

## Infrastructure

Everything is in `templates/dynamodb-template.yaml`:

| Resource | What it is |
|---|---|
| `MatchobUsersTable` | DynamoDB table `MatchobUsers`. Partition key `userId` (string), on-demand billing |
| `ProfileApi` | API Gateway, stage `dev`, Cognito authorizer from the `UserPoolArn` parameter |
| `ProfileFunction` | The Lambda. Explicit `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem` permissions on this table only, one `Api` event per method on `/profile` |
| `SharedLayer` | This stack's copy of `src/shared` |

| Parameter | From |
|---|---|
| `UserPoolArn` | `SharedStack.Outputs.UserPoolArn` |

| Output | Used by |
|---|---|
| `ApiUrl` | Root output `ProfileApiUrl`, for the frontend |
| `UsersTableName` | `ResumesStack` and `BedrockStack`, which read and write profiles |

## Data model

One item per user. Only `userId` is part of the table definition; DynamoDB doesn't enforce the other attributes, so `PROFILE_FIELDS` in `profile_helpers.py` is what actually controls them.

| Attribute | Type | Set by |
|---|---|---|
| `userId` | String | Backend, from the token. Partition key |
| `firstname`, `lastname`, `email`, `phoneNumber`, `major` | String | Client |
| `age` | Number | Client |
| `year` | String | Client: `freshman`, `sophomore`, `junior`, `senior`, `graduate` |
| `websites` | List of strings | Client |
| `defaultResume` | String or null | Client, must be a key of `resumes` |
| `resumes` | Map of resume ID → `{s3Key, name, tags, contentType, uploadedAt}` | Resumes pipeline |
| `structuredJsonResume` | Map or null | Resume parsing |

The [contract](../general/api-contracts.md#profile-object) has the validation rules for each field.

## Objects at the top of `app.py`

| Object | What it is |
|---|---|
| `table` | `boto3.resource("dynamodb", endpoint_url=...).Table(USERS_TABLE)`. The resource API takes and returns plain Python values; numbers come back as `Decimal` |
| `logger` | Powertools `Logger`. Service name from `POWERTOOLS_SERVICE_NAME` (`profile`) |
| `app` | `APIGatewayRestResolver(serializer=to_json)`, so `Decimal` values are sent as JSON numbers |

`DYNAMODB_ENDPOINT` is `""` in AWS, so `endpoint_url` becomes `None` and boto3 uses real DynamoDB. Locally `env.json` sets it to `http://dynamodb:8000`.

## Every route follows the same shape

1. `get_user_id(app.current_event.raw_event)`. `None` → `401 Unauthorized`.
2. For routes with a body: `read_json_body` then `validate_fields`. Either fails → `400` with its message.
3. Read or write only the caller's DynamoDB item. POST and PUT use conditions; PUT may read afterward to explain a failed default-resume condition. DELETE returns the old item and then cleans up its S3 files.
4. POST/PUT conditional failures map to the documented 400/404/409 responses. Other caught `ClientError` failures return `500 Internal server error` and log a fixed message without exception details.
5. `logger.info("<what happened>", extra={"user_id": user_id})` and return the result.

## Unit tests (task 7)

GET, PUT and DELETE are tested through `lambda_handler` with API Gateway events and mocked DynamoDB/S3 clients. No AWS deployment or Docker is required.

| Test file | Coverage |
|---|---|
| `tests/unit/test_profile_endpoints.py` | GET response serialization and errors; PUT partial updates, validation, ownership, default-resume conditions and errors; authentication; repeated DELETE |
| `tests/test_profile_isolation.py` | GET caller isolation, local-header rules and rejection of foreign profile paths |
| `tests/test_delete_user.py` | DELETE success, missing profile, authentication, DynamoDB failures and S3 cleanup, including continuing after a file fails |

From `backend/SAMproject`, run:

```bash
.venv/bin/python -m pytest tests/unit/test_profile_endpoints.py tests/test_profile_isolation.py tests/test_delete_user.py -q
```

October 29, 2026: **44 tests and 3 subtests passed**. These mocked tests do not verify deployed API Gateway, IAM or live DynamoDB/S3 behavior. POST coverage is in `tests/unit/test_create_user.py`.

## Local SAM verification

October 29, 2026: rebuilt the current source and ran `sam local start-api` on port 3001 with `env.json`, the `matchob-local` Docker network, DynamoDB Local and S3mock. **All 23 HTTP checks passed**, using two unique synthetic users:

- GET/PUT/DELETE without login → 401; missing profile GET/PUT → 404.
- POST fixture creation → 201; GET → 200 with numeric age; partial PUT → 200 with unchanged fields retained.
- Malformed JSON, empty update, supplied `userId`, invalid age and nonexistent default resume → 400.
- Setting an owned default resume and clearing it → 200.
- Another user's ID in query parameters could not redirect PUT or DELETE; the original user's profile remained intact.
- DELETE → 200; direct emulator checks confirmed the DynamoDB item and its S3 file were gone. GET and repeated DELETE afterward → 404.

Synthetic fixtures were removed and the test services stopped afterward. Local authentication uses `X-Local-User`; SAM skips the Cognito authorizer. Real AWS authorization/IAM and service-failure behavior were not verified by this run; failure paths remain covered by mocked unit tests.

## Known gaps

- DELETE removes the profile before S3 cleanup. Failed file deletions cannot be retried through the endpoint after the profile is gone; retryable cleanup remains deferred pending chair review.


---

New to a term? See the [glossary](../general/glossary.md).

## IAM and AWS error handling review

The profile role allows only DynamoDB `GetItem`, `PutItem`, `UpdateItem` and `DeleteItem` on the profile table, plus S3 `DeleteObject` under `users/*/resumes/*` in the configured uploads bucket. It cannot upload, read or list S3 objects. Standard Lambda logging permissions remain managed by SAM.

AWS transport failures and failed PUT follow-up reads return generic JSON 500 responses without exception details in logs. S3 cleanup continues after service or transport failures. Regression suite: **295 tests and 34 subtests passed**. The earlier local SAM run predates these changes; local emulators do not verify IAM enforcement, which still needs deployment verification.
