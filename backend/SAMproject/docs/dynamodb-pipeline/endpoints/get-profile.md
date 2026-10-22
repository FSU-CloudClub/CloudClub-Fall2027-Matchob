# GET /profile

**Contract:** [api-contracts.md → GET /profile](../../general/api-contracts.md#get-profile)
**Code:** `src/dynamodb-pipeline/app.py` → `get_profile()`

## What it does
Returns the signed-in user's full profile, including their `resumes` map.

## How it works
1. `get_user_id(app.current_event.raw_event)`. `None` → 401.
2. `table.get_item(Key={"userId": user_id})`.
3. Read `response.get("Item")`. Missing → 404.
4. `logger.info("profile fetched", extra={"user_id": user_id})` and return the item. It's sent with status 200.

## Objects and calls

**`table.get_item(Key={"userId": user_id})`**
- `Key`: the full primary key. The table only has a partition key, so it's just `userId`.
- Returns a dict. It has an `"Item"` key **only if the item exists**. It never returns `None` and never raises for a missing item, so check for `"Item"`, not for `None`.
- The response also has `ResponseMetadata`. Never return the whole response, only `Item`.

**`app.current_event.raw_event`**: the original API Gateway event, which `get_user_id` needs.

## Helpers
| Helper | Where | New or existing | Signature → returns |
|---|---|---|---|
| `get_user_id` | `matchob_common.auth` | Existing | `(event) → str \| None` |
| `to_json` | `matchob_common.http` | Existing | Set once on the resolver. Turns `age` back into a number |

## Errors
| Condition | Status | `error` message | Log |
|---|---|---|---|
| No user | 401 | `Unauthorized` | none |
| No `Item` in the response | 404 | `Profile not found` | none |
| `ClientError` from `get_item` | 500 | `Internal server error` | `logger.exception("dynamodb get_item failed")` |

## Infrastructure
None. The `GetProfile` event and `DynamoDBCrudPolicy` are in `templates/dynamodb-template.yaml`.

## Done when
```bash
curl -i localhost:3001/profile -H "X-Local-User: u1"     # 404 before POST, 200 after
curl -i localhost:3001/profile                           # 401
```
The 200 body has `"age": 20`, a number, not `"20"`.

## Gotchas
- Returning `response` instead of `response["Item"]` sends DynamoDB's metadata to the client.
- Without `serializer=to_json` on the resolver, numbers come back as strings.

---

New to a term? See the [glossary](../../general/glossary.md).
