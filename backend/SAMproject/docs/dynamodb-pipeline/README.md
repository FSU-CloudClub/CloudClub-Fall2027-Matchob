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
| `ProfileFunction` | The Lambda. `DynamoDBCrudPolicy` on the table, one `Api` event per method on `/profile` |
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
3. One DynamoDB call, using a `ConditionExpression` instead of reading first, so two requests at once can't both succeed.
4. `ClientError` with code `ConditionalCheckFailedException` → the route's 404 or 409. Any other `ClientError` → `logger.exception(...)` and `500 Internal server error`.
5. `logger.info("<what happened>", extra={"user_id": user_id})` and return the result.

## Known gaps

- `DELETE /profile` doesn't delete the user's resume files from S3. Once the resumes pipeline exists, it should either call into it or the profile delete should delete each `s3Key` first.
- `tests/unit/test_create_user.py` still uses the old `name` and `education` fields and fails.

---

New to a term? See the [glossary](../general/glossary.md).
