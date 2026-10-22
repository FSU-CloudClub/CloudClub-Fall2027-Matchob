# POST /profile

**Contract:** [api-contracts.md → POST /profile](../../general/api-contracts.md#post-profile)
**Status:** Done
**Code:** `src/dynamodb-pipeline/app.py` → `create_user()`

## What it does
Creates the signed-in user's profile. Called once, after sign-up.

## How it works
1. `get_user_id(app.current_event.raw_event)`. `None` → 401.
2. `read_json_body(app.current_event)`. Error → 400.
3. `validate_fields(body, PROFILE_FIELDS, partial=False)`. Every `REQUIRED` field must be present; `websites` defaults to `[]` and `defaultResume` to `None`. Error → 400.
4. If `fields["defaultResume"]` isn't `None` → 400. A new profile has no resumes, so no ID can be valid.
5. Build the item: `{"userId": user_id, **fields, "resumes": {}, "structuredJsonResume": None}`. `userId` comes from the token, never the body.
6. `table.put_item(Item=item, ConditionExpression="attribute_not_exists(userId)")`.
7. Log `profile created` and return `item, 201`.

## Objects and calls

**`table.put_item(Item=..., ConditionExpression="attribute_not_exists(userId)")`**
- `Item`: the whole item. `put_item` replaces any existing item with the same key entirely.
- `ConditionExpression`: makes the write fail if a profile already exists, so POST can never overwrite one. This replaces a separate "does it exist?" read, which could race with another request.
- On failure raises `ClientError` with `error.response["Error"]["Code"] == "ConditionalCheckFailedException"`.

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
| Any `validate_fields` failure | 400 | Its message, e.g. `lastname is required`, `Unknown fields: userId` | none |
| `defaultResume` sent | 400 | `defaultResume must be one of your resumes` | none |
| `ConditionalCheckFailedException` | 409 | `Profile already exists` | none |
| Any other `ClientError` | 500 | `Internal server error` | `logger.exception("dynamodb put_item failed")` |

## Infrastructure
None. The `CreateUser` event is in `templates/dynamodb-template.yaml`.

## Done when
```bash
B='{"firstname":"Sarah","lastname":"Lee","email":"sarah@fsu.edu","phoneNumber":"+18505551234","age":20,"year":"junior","major":"CS"}'
curl -i -X POST localhost:3001/profile -H "X-Local-User: u1" -H "Content-Type: application/json" -d "$B"   # 201
curl -i -X POST localhost:3001/profile -H "X-Local-User: u1" -H "Content-Type: application/json" -d "$B"   # 409
curl -i -X POST localhost:3001/profile -H "X-Local-User: u2" -H "Content-Type: application/json" -d '{"firstname":"A"}'   # 400 lastname is required
```

## Gotchas
- Building the item from `body` instead of `fields` would store untrimmed, unvalidated values.
- `put_item` without the condition silently overwrites an existing profile, including its `resumes`.

---

New to a term? See the [glossary](../../general/glossary.md).
