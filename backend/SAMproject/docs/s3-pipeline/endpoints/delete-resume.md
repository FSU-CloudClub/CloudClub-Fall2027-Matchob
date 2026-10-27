# DELETE /resumes/{resumeId}

**Contract:** [api-contracts.md → DELETE /resumes/{id}](../../general/api-contracts.md#delete-resumesid)
**Code:** `src/s3-pipeline/app.py` → `delete_resume(resume_id)`

## What it does
Removes a resume from the profile, clears `defaultResume` if it pointed at it, and deletes the file from S3. Backs `resumeApi.deleteResume(id)`.

## How it works
1. `get_user_id(app.current_event.raw_event)`. `None` → 401.
2. Remove the entry with `table.update_item` (call 1 below), returning the old item. `ConditionalCheckFailedException` → 404.
3. `old = result["Attributes"]`, `stored = old["resumes"][resume_id]`.
4. If `old.get("defaultResume") == resume_id`, clear it (call 2 below).
5. `s3.delete_object(Bucket=BUCKET, Key=stored["s3Key"])`.
6. Log `resume deleted` with `user_id` and `resume_id`, and return `{"message": "Resume deleted"}`. It's sent with status 200.

**Why DynamoDB first, S3 last:** if the S3 delete fails after the record is gone, the user sees the resume as deleted and the only cost is an orphaned file. The other order could leave a listed resume whose file is gone.

## Objects and calls

**Call 1: remove the resume**

| Parameter | Value | Why |
|---|---|---|
| `Key` | `{"userId": user_id}` | The caller's own profile |
| `UpdateExpression` | `"REMOVE #resumes.#resumeId"` | Deletes one map entry |
| `ExpressionAttributeNames` | `resume_path_names(resume_id)` | |
| `ConditionExpression` | `"attribute_exists(#resumes.#resumeId)"` | `REMOVE` on a missing path succeeds silently, so without this a bad ID would return 200 |
| `ReturnValues` | `"ALL_OLD"` | The item **before** the removal, which still has the `s3Key` and `defaultResume` |

**Call 2: clear the default (only if it was this resume)**

| Parameter | Value | Why |
|---|---|---|
| `UpdateExpression` | `"SET #defaultResume = :null"` | `:null` is `None` |
| `ConditionExpression` | `"#defaultResume = :resumeId"` | Only clears it if it still points at this resume, so a default the user changed a moment ago isn't wiped |
| On `ConditionalCheckFailedException` | Ignore it | The default already changed; nothing to do |

DynamoDB can't do "remove this, and clear that only if it matches" in one expression, so it's two calls. The condition on call 2 makes it safe.

**`s3.delete_object(Bucket=BUCKET, Key=...)`** uses the regular `s3` client, not `presign_client`, because the Lambda makes this call itself. It succeeds even if the object was never uploaded, so no special case is needed.

## Helpers
| Helper | Where | New or existing | Signature → returns |
|---|---|---|---|
| `resume_path_names` | `resume_helpers` | **New** | `(resume_id) → dict` |
| `get_user_id` | `matchob_common.auth` | Existing | |

## Errors
| Condition | Status | `error` message | Log |
|---|---|---|---|
| No user | 401 | `Unauthorized` | none |
| Call 1 `ConditionalCheckFailedException` | 404 | `Resume not found` | none |
| Call 1 other `ClientError` | 500 | `Internal server error` | `logger.exception("dynamodb update_item failed")` |
| Call 2 `ConditionalCheckFailedException` | (continue) | | none |
| Call 2 other `ClientError` | (continue, return 200) | | `logger.exception("clear defaultResume failed")`. The resume is gone, so the user's request succeeded |
| `delete_object` `ClientError` | (continue, return 200) | | `logger.exception("s3 delete_object failed", extra={"s3_key": ...})`. Leaves an orphaned file |

## Infrastructure
None. The `DeleteResume` event and `S3CrudPolicy` (which includes `s3:DeleteObject`) are in `templates/s3-template.yaml`.

## Done when
```bash
curl -i -X PUT localhost:3001/profile -H "X-Local-User: u1" -H "Content-Type: application/json" -d '{"defaultResume":"<resumeId>"}'
curl -i -X DELETE localhost:3001/resumes/<resumeId> -H "X-Local-User: u1"     # 200
curl -s localhost:3001/profile -H "X-Local-User: u1"                          # resume gone, defaultResume null
aws s3 ls s3://matchob-uploads/users/u1/resumes/ --endpoint-url http://localhost:9090   # file gone
curl -i -X DELETE localhost:3001/resumes/<resumeId> -H "X-Local-User: u1"     # 404 the second time
```

## Gotchas
- Without the `ConditionExpression` on call 1, deleting a nonexistent resume returns 200.
- Without `ReturnValues="ALL_OLD"` you lose the `s3Key` and can't delete the file.

---

New to a term? See the [glossary](../../general/glossary.md).
