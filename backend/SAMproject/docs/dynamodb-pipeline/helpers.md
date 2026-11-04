# Profile Pipeline Helpers

**Code:** `src/dynamodb-pipeline/profile_helpers.py`

Helpers only the profile Lambda uses. Generic helpers (`read_json_body`, `to_json`, `validate_fields` and the validators) are in [shared-helpers.md](../general/shared-helpers.md).

## `PROFILE_FIELDS`

The spec passed to `validate_fields`: `{field: (default, validator)}`. It's the single place that decides which profile fields a client may send and how each is checked.

| Field | Default | Validator |
|---|---|---|
| `firstname` | `REQUIRED` | `non_empty_str` |
| `lastname` | `REQUIRED` | `non_empty_str` |
| `email` | `REQUIRED` | `email` |
| `phoneNumber` | `REQUIRED` | `non_empty_str` |
| `age` | `REQUIRED` | `int_between(13, 120)` |
| `year` | `REQUIRED` | `one_of("freshman", "sophomore", "junior", "senior", "graduate")` |
| `major` | `REQUIRED` | `non_empty_str` |
| `websites` | `[]` | `url_list` |
| `defaultResume` | `None` | `optional_str` |

`userId`, `resumes` and `structuredJsonResume` are deliberately **not** in the spec, so `validate_fields` rejects them with `Unknown fields: ...`. That's what stops a client from writing another user's ID or editing the resume list directly.

**Adding a field:** add one line here, add the row to the [contract](../general/api-contracts.md#profile-object) and the data model in [README.md](README.md), in the same pull request. If no existing validator fits, add one to `matchob_common/validators.py`.

## `profile_exists(table, user_id) → bool`

| Parameter | Meaning |
|---|---|
| `table` | The DynamoDB `Table` from `app.py` |
| `user_id` | The signed-in user's ID |

Calls `table.get_item(Key={"userId": user_id}, ProjectionExpression="userId")` and returns whether an `Item` came back. `ProjectionExpression` fetches only the key, so the read stays small however big the profile is.

**When to use it:** only after a conditional write fails with more than one possible cause. In `PUT /profile`, a failed condition means either "no profile" (404) or "`defaultResume` isn't one of your resumes" (400), and this read tells them apart. Don't call it before a write to check existence, because the profile could be deleted between the read and the write. Put the check in the write's `ConditionExpression` instead.

AWS errors propagate to the router's AWS exception handler, which logs a fixed message without exception details and returns generic JSON 500. A failed read must not imply that the profile is missing.

---

New to a term? See the [glossary](../general/glossary.md).
