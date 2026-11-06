# PUT /profile

**Contract:** [api-contracts.md → PUT /profile](../../general/api-contracts.md#put-profile)
**Code:** `src/dynamodb-pipeline/app.py` → `put_profile()`

## What it does
Changes only the fields the client sends and returns the full updated profile.

## How it works
1. `get_user_id(app.current_event.raw_event)`. `None` → 401.
2. `read_json_body(app.current_event)`. Error → 400.
3. `validate_fields(body, PROFILE_FIELDS, partial=True)`. Any non-empty subset. Error → 400.
4. Build the update from the validated fields only: `SET #firstname = :firstname, #age = :age, ...`.
5. Use the condition `attribute_exists(userId)`.
6. `table.update_item(...)` with `ReturnValues="ALL_NEW"`.
7. On `ConditionalCheckFailedException`, return 404. No follow-up read is needed.
8. Log `profile updated` and return `result["Attributes"], 200`.

## Objects and calls

**`table.update_item(...)`**

| Parameter | Value | Why |
|---|---|---|
| `Key` | `{"userId": user_id}` | Which item |
| `UpdateExpression` | `"SET #a = :a, #b = :b"` | Changes only the listed attributes; everything else is untouched. `put_item` would replace the whole item |
| `ExpressionAttributeNames` | `{"#a": "a", ...}` | Placeholders for attribute names. Required for reserved words like `name` and `year`, and used for every field so you never have to check |
| `ExpressionAttributeValues` | `{":a": value, ...}` | Placeholders for the values |
| `ConditionExpression` | `attribute_exists(userId)` | Prevents creating a partial profile for a user who has none |
| `ReturnValues` | `"ALL_NEW"` | Returns the whole item after the update in `result["Attributes"]`, so no second read is needed |

## Helpers
| Helper | Where | New or existing | Signature → returns |
|---|---|---|---|
| `read_json_body` | `matchob_common.http` | Existing | `(current_event) → (body, error)` |
| `validate_fields` | `matchob_common.validators` | Existing | `(body, spec, partial) → (fields, error)` |
| `PROFILE_FIELDS` | `profile_helpers` | Existing | The field spec |

## Errors
| Condition | Status | `error` message | Log |
|---|---|---|---|
| No user | 401 | `Unauthorized` | none |
| Body isn't JSON | 400 | `Invalid JSON body` | none |
| Any `validate_fields` failure | 400 | Its message, e.g. `Provide at least one field to update` | none |
| `ConditionalCheckFailedException` | 404 | `Profile not found` | none |
| Other `ClientError` from `update_item` | 500 | `Internal server error` | `logger.error("dynamodb update_item failed")`, no exception details |

## Infrastructure
None. The `UpdateProfile` event is in `templates/dynamodb-template.yaml`.

## Done when
```bash
H=(-H "X-Local-User: u1" -H "Content-Type: application/json")
curl -i -X PUT localhost:3001/profile "${H[@]}" -d '{"age":21}'                  # 200, other fields unchanged
curl -i -X PUT localhost:3001/profile "${H[@]}" -d '{}'                          # 400
curl -i -X PUT localhost:3001/profile -H "X-Local-User: nobody" -H "Content-Type: application/json" -d '{"age":30}'   # 404
```

## Gotchas
- Writing `SET name = :name` without a placeholder fails, because `name` is reserved.

## Unit tests
`tests/unit/test_profile_endpoints.py` covers partial updates, the returned profile, caller ownership, authentication, invalid bodies and unknown fields, conditional failures (404), and update errors (500). Invalid requests never write; failed conditions never trigger an existence read. AWS clients are mocked.

---

New to a term? See the [glossary](../../general/glossary.md).
