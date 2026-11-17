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

`userId`, `resumes` and `structuredJsonResume` are deliberately **not** in the spec, so `validate_fields` rejects them with `Unknown fields: ...`. That's what stops a client from writing another user's ID or editing the resume list directly.

The removed `defaultResume` field is rejected with `400 Unknown fields: defaultResume`, including when its value is null.

**Adding a field:** add one line here, add the row to the [contract](../general/api-contracts.md#profile-object) and the data model in [README.md](README.md), in the same pull request. If no existing validator fits, add one to `matchob_common/validators.py`.


---

New to a term? See the [glossary](../general/glossary.md).
