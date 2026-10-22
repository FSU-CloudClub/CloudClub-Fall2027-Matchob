# PATCH /resumes/{resumeId}

**Contract:** [api-contracts.md → PATCH /resumes/{id}](../../general/api-contracts.md#patch-resumesid)
**Code:** `src/s3-pipeline/app.py` → `update_resume(resume_id)`

## What it does
Renames a resume, replaces its tags, or both. Backs `resumeApi.renameResume(id, name)` and `resumeApi.updateTags(id, tags)`. Only metadata changes; the file in S3 is untouched.

## How it works
1. `get_user_id(app.current_event.raw_event)`. `None` → 401.
2. `read_json_body(app.current_event)`. Error → 400.
3. `validate_fields(body, RESUME_FIELDS, partial=True)`. Error → 400.
4. Build one `SET` clause per validated field, on the nested path: `#resumes.#resumeId.#name = :name`, `#resumes.#resumeId.#tags = :tags`.
5. `table.update_item(...)` with the resume-exists condition and `ReturnValues="ALL_NEW"`. `ConditionalCheckFailedException` → 404.
6. `stored = result["Attributes"]["resumes"][resume_id]`.
7. Log `resume updated` with `user_id`, `resume_id` and the changed field names, and return `to_resume_object(resume_id, stored), 200`.

## Objects and calls

**`table.update_item(...)`**

| Parameter | Value | Why |
|---|---|---|
| `Key` | `{"userId": user_id}` | The caller's own profile |
| `UpdateExpression` | `"SET #resumes.#resumeId.#name = :name, #resumes.#resumeId.#tags = :tags"` (only the fields sent) | Changes those two attributes of one resume and nothing else |
| `ExpressionAttributeNames` | `resume_path_names(resume_id)` plus `{"#name": "name"}` and/or `{"#tags": "tags"}` | `name` is a reserved word, and the resume ID is a map key |
| `ExpressionAttributeValues` | `{":name": ..., ":tags": ...}` | The validated values |
| `ConditionExpression` | `"attribute_exists(#resumes.#resumeId)"` | Without it, `SET` on a missing resume fails with a confusing `ValidationException` or creates a broken partial entry. This also covers "no profile" and "another user's resume" |
| `ReturnValues` | `"ALL_NEW"` | Returns the whole profile after the update, so the full resume is available without a second read. `UPDATED_NEW` would return only the changed fields |

## Helpers
| Helper | Where | New or existing | Signature → returns |
|---|---|---|---|
| `read_json_body`, `validate_fields` | shared | Existing | See [shared-helpers.md](../../general/shared-helpers.md) |
| `str_length` | `matchob_common.validators` | **New** | `(low, high) → validator` |
| `tag_list` | `resume_helpers` | **New** | `(value) → list[str]` |
| `RESUME_FIELDS` | `resume_helpers` | **New** | Spec, used with `partial=True` |
| `resume_path_names`, `to_resume_object` | `resume_helpers` | **New** | See [helpers.md](../helpers.md) |

## Errors
| Condition | Status | `error` message | Log |
|---|---|---|---|
| No user | 401 | `Unauthorized` | none |
| Body isn't JSON | 400 | `Invalid JSON body` | none |
| Bad or no fields | 400 | From `validate_fields`, e.g. `Provide at least one field to update`, `name must be 1-100 characters`, `tags must be a list of at most 10 strings, each 1-30 characters` | none |
| `ConditionalCheckFailedException` | 404 | `Resume not found` | none |
| Any other `ClientError` | 500 | `Internal server error` | `logger.exception("dynamodb update_item failed")` |

## Infrastructure
None. The `UpdateResume` event is in `templates/s3-template.yaml`.

## Done when
```bash
H=(-H "X-Local-User: u1" -H "Content-Type: application/json")
curl -s -X PATCH localhost:3001/resumes/<resumeId> "${H[@]}" -d '{"name":"SWE Resume"}'                  # 200, tags unchanged
curl -s -X PATCH localhost:3001/resumes/<resumeId> "${H[@]}" -d '{"tags":["swe","swe","intern"]}'        # 200, tags ["swe","intern"]
curl -s -X PATCH localhost:3001/resumes/<resumeId> "${H[@]}" -d '{"tags":[]}'                            # 200, tags []
curl -i -X PATCH localhost:3001/resumes/<resumeId> "${H[@]}" -d '{}'                                     # 400
curl -i -X PATCH localhost:3001/resumes/<resumeId> "${H[@]}" -d '{"s3Key":"x"}'                          # 400 Unknown fields
curl -i -X PATCH localhost:3001/resumes/nope "${H[@]}" -d '{"name":"x"}'                                 # 404
```

## Gotchas
- `tags` **replaces** the list. Don't append.
- Don't read the profile, change the resume in Python and `put_item` it back. A concurrent upload or delete between the read and the write would be lost.

---

New to a term? See the [glossary](../../general/glossary.md).
