# DELETE /profile

**Contract:** [api-contracts.md → DELETE /profile](../../general/api-contracts.md#delete-profile)
**Status:** Done (see the gap below)
**Code:** `src/dynamodb-pipeline/app.py` → `delete_user()`

## What it does
Deletes the signed-in user's profile.

## How it works
1. `get_user_id(app.current_event.raw_event)`. `None` → 401.
2. `table.delete_item(Key={"userId": user_id}, ReturnValues="ALL_OLD")`.
3. Read `.get("Attributes")` from the response. Missing → nothing was deleted → 404.
4. Log `profile deleted` and return `{"message": "Profile deleted"}` with status 200.

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
| `ClientError` from `delete_item` | 500 | `Internal server error` | `logger.exception("dynamodb delete_item failed")` |

## Infrastructure
None. The `DeleteProfile` event is in `templates/dynamodb-template.yaml`.

## Done when
```bash
curl -i -X DELETE localhost:3001/profile -H "X-Local-User: u1"   # 200, then 404 if run again
```

## Gap: resume files are left in S3
The deleted item's `resumes` map lists every `s3Key`, and those files aren't deleted. The profile Lambda has no S3 access, so the fix needs a decision:
- Give `ProfileFunction` `S3CrudPolicy` on the bucket and delete each `s3Key` from the `Attributes` returned above, or
- Add an S3 lifecycle rule or a DynamoDB Stream on the users table that cleans up after a delete.

---

New to a term? See the [glossary](../../general/glossary.md).
