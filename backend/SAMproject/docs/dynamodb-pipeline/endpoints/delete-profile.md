# DELETE /profile

**Contract:** [api-contracts.md → DELETE /profile](../../general/api-contracts.md#delete-profile)
**Code:** `src/dynamodb-pipeline/app.py` → `delete_user()`

## What it does
Deletes the signed-in user's profile and each resume file listed in its `resumes` map.

## How it works
1. `get_user_id(app.current_event.raw_event)`. `None` → 401.
2. `table.delete_item(Key={"userId": user_id}, ReturnValues="ALL_OLD")`.
3. Read `.get("Attributes")` from the response. Missing → nothing was deleted → 404.
4. Delete each stored `s3Key` with `s3.delete_object(Bucket=BUCKET, Key=...)`. Log failures and continue attempting the remaining files; any failure returns 500.
5. Log `profile deleted` and return `{"message": "Profile deleted"}` with status 200.

## Objects and calls

**`table.delete_item(Key=..., ReturnValues="ALL_OLD")`**
- `delete_item` succeeds even when the item doesn't exist, so on its own it can't tell you whether anything was deleted.
- `ReturnValues="ALL_OLD"` returns the deleted item in `"Attributes"`. If there's no `"Attributes"` key, there was no profile, which gives the 404 in one call.

## Helpers
| Helper | Where | New or existing | Signature → returns |
|---|---|---|---|
| `get_user_id` | `matchob_common.auth` | Existing | `(event) → str \| None` |

## Errors
| Condition | Status | `error` message | Log |
|---|---|---|---|
| No user | 401 | `Unauthorized` | none |
| No `Attributes` in the response | 404 | `Profile not found` | none |
| Service or transport error from `s3.delete_object` | 500 | `Internal server error` | fixed message and user ID; no key or exception details |
| `ClientError` from `delete_item` | 500 | `Internal server error` | `logger.error("dynamodb delete_item failed")`, no exception details |

AWS transport failures from DynamoDB return generic JSON 500. S3 transport failures, like service errors, do not prevent attempts to delete remaining files.

## Infrastructure
`ProfileFunction` has only `s3:DeleteObject` for `users/*/resumes/*` in the uploads bucket and receives `UPLOAD_BUCKET` and `S3_ENDPOINT`. The root stack passes the same bucket name to both services without a circular dependency.

When updating an existing deployment, set the root `UploadBucketName` parameter to its current uploads bucket name to preserve the bucket and its files. New stacks can leave it empty to generate a unique name.

## Done when
```bash
curl -i -X DELETE localhost:3001/profile -H "X-Local-User: u1"   # 200, then 404 if run again
```

## MVP failure behavior
DynamoDB deletion happens before S3 cleanup. If S3 fails, the endpoint returns 500 and logs a fixed failure message and user ID, but the profile is already gone. A retry returns 404 and cannot retry cleanup; leftover files need separate investigation and cleanup. This flow only deletes files listed in the deleted profile and does not coordinate concurrent uploads. Retryable cleanup remains deferred pending chair review.

## Unit tests
`tests/test_delete_user.py` covers success with absent/empty/populated resume maps, authentication, missing profile, DynamoDB failures, and attempting remaining S3 deletes after one fails. `tests/unit/test_profile_endpoints.py` adds repeated deletion (200 then 404 without repeating S3 cleanup) and authentication with a spoofed local header in production. See the [pipeline test command and results](../README.md#unit-tests-task-7); AWS clients are mocked.

---

New to a term? See the [glossary](../../general/glossary.md).
