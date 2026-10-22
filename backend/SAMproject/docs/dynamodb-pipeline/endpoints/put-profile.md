# PUT /profile

**Contract:** [api-contracts.md → PUT /profile](../../general/api-contracts.md#put-profile)
**Status:** Done
**Code:** `src/dynamodb-pipeline/app.py` → `put_profile()`

## What it does
Changes only the fields the client sends and returns the full updated profile. Also how the user picks their `defaultResume`.

## How it works
1. `get_user_id(app.current_event.raw_event)`. `None` → 401.
2. `read_json_body(app.current_event)`. Error → 400.
3. `validate_fields(body, PROFILE_FIELDS, partial=True)`. Any non-empty subset. Error → 400.
4. Build the update from the validated fields only: `SET #firstname = :firstname, #age = :age, ...`.
5. Build the condition: always `attribute_exists(userId)`. If `defaultResume` is a non-null ID, also `attribute_exists(#resumes.#defaultResumeId)`.
6. `table.update_item(...)` with `ReturnValues="ALL_NEW"`.
7. On `ConditionalCheckFailedException`: if a `defaultResume` was sent and `profile_exists(table, user_id)` → 400. Otherwise → 404.
8. Log `profile updated` and return `result["Attributes"], 200`.

## Objects and calls

**`table.update_item(...)`**

| Parameter | Value | Why |
|---|---|---|
| `Key` | `{"userId": user_id}` | Which item |
| `UpdateExpression` | `"SET #a = :a, #b = :b"` | Changes only the listed attributes; everything else is untouched. `put_item` would replace the whole item |
| `ExpressionAttributeNames` | `{"#a": "a", ...}` | Placeholders for attribute names. Required for reserved words like `name` and `year`, and used for every field so you never have to check |
| `ExpressionAttributeValues` | `{":a": value, ...}` | Placeholders for the values |
| `ConditionExpression` | `attribute_exists(userId)` [`AND attribute_exists(#resumes.#defaultResumeId)`] | Without the first part, `update_item` would **create** a half-empty profile for a user who has none. The second part checks the resume exists in the same atomic write |
| `ReturnValues` | `"ALL_NEW"` | Returns the whole item after the update in `result["Attributes"]`, so no second read is needed |

The resume ID goes in `ExpressionAttributeNames` (`#defaultResumeId`) because it's a map key, which is an attribute name in DynamoDB's eyes, not a value.

## Helpers
| Helper | Where | New or existing | Signature → returns |
|---|---|---|---|
| `read_json_body` | `matchob_common.http` | Existing | `(current_event) → (body, error)` |
| `validate_fields` | `matchob_common.validators` | Existing | `(body, spec, partial) → (fields, error)` |
| `PROFILE_FIELDS` | `profile_helpers` | Existing | The field spec |
| `profile_exists` | `profile_helpers` | Existing | `(table, user_id) → bool`. Only called after a failed condition |

## Errors
| Condition | Status | `error` message | Log |
|---|---|---|---|
| No user | 401 | `Unauthorized` | none |
| Body isn't JSON | 400 | `Invalid JSON body` | none |
| Any `validate_fields` failure | 400 | Its message, e.g. `Provide at least one field to update` | none |
| Condition failed, `defaultResume` sent, profile exists | 400 | `defaultResume must be one of your resumes` | none |
| Condition failed otherwise | 404 | `Profile not found` | none |
| Any other `ClientError` | 500 | `Internal server error` | `logger.exception("dynamodb update_item failed")` |

`ConditionalCheckFailedException` doesn't say which part of the condition failed, which is why step 7 needs the extra read.

## Infrastructure
None. The `UpdateProfile` event is in `templates/dynamodb-template.yaml`.

## Done when
```bash
H=(-H "X-Local-User: u1" -H "Content-Type: application/json")
curl -i -X PUT localhost:3001/profile "${H[@]}" -d '{"age":21}'                  # 200, other fields unchanged
curl -i -X PUT localhost:3001/profile "${H[@]}" -d '{}'                          # 400
curl -i -X PUT localhost:3001/profile "${H[@]}" -d '{"defaultResume":"nope"}'    # 400
curl -i -X PUT localhost:3001/profile "${H[@]}" -d '{"defaultResume":null}'      # 200, clears it
curl -i -X PUT localhost:3001/profile -H "X-Local-User: nobody" -H "Content-Type: application/json" -d '{"age":30}'   # 404
```

## Gotchas
- Writing `SET name = :name` without a placeholder fails, because `name` is reserved.
- `defaultResume: null` must skip the resume check, or clearing the default would always fail.

---

New to a term? See the [glossary](../../general/glossary.md).
