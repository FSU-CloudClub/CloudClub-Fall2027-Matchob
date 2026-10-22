# GET /resumes

**Contract:** [api-contracts.md → GET /resumes](../../general/api-contracts.md#get-resumes)
**Code:** `src/s3-pipeline/app.py` → `list_resumes()`

## What it does
Returns all of the user's resumes, newest first, each with a fresh download link. Backs `resumeApi.getResumes()`.

## How it works
1. `get_user_id(app.current_event.raw_event)`. `None` → 401.
2. `resumes = get_resumes(user_id)`. `None` → 404.
3. Sort `resumes.items()` by `stored["uploadedAt"]`, newest first.
4. Map each `(resume_id, stored)` through `to_resume_object`.
5. Log `resumes listed` with `user_id` and `count`, and return the list. It's sent with status 200. An empty map returns `[]`, not 404.

## Objects and calls

**`get_resumes(user_id)`** does one `table.get_item` with a `ProjectionExpression`, so only the `resumes` map is read. See [helpers.md](../helpers.md#get_resumesuser_id--dict--none).

**`to_resume_object`** calls `presign_client.generate_presigned_url` once per resume. That's local signing with no network call, so 20 resumes cost microseconds, not 20 requests.

**Sorting:** `sorted(resumes.items(), key=lambda kv: kv[1]["uploadedAt"], reverse=True)`. `uploadedAt` strings in the `now_iso()` format sort correctly as text.

## Helpers
| Helper | Where | New or existing | Signature → returns |
|---|---|---|---|
| `get_resumes` | `resume_helpers` | **New** | `(user_id) → dict \| None` |
| `to_resume_object` | `resume_helpers` | **New** | `(resume_id, stored) → dict` |
| `presign_download` | `resume_helpers` | **New** | `(key, file_name) → str`. Used by `to_resume_object` |

## Errors
| Condition | Status | `error` message | Log |
|---|---|---|---|
| No user | 401 | `Unauthorized` | none |
| `get_resumes` returns `None` | 404 | `Profile not found` | none |
| `ClientError` from `get_item` | 500 | `Internal server error` | `logger.exception("dynamodb get_item failed")` |

## Infrastructure
None. The `ListResumes` event and both policies are in `templates/s3-template.yaml`.

## Done when
```bash
curl -s localhost:3001/resumes -H "X-Local-User: u1"         # 200, newest first, each with downloadUrl and expiresIn
curl -i localhost:3001/resumes -H "X-Local-User: nobody"     # 404
curl -i localhost:3001/resumes                               # 401
```
Open a `downloadUrl` in your browser: it should show the PDF. No `s3Key` appears anywhere in the response.

## Gotchas
- Returning the map instead of a list breaks the frontend, which expects `Resume[]`.
- A resume whose upload never finished is still listed, and its link returns S3's `NoSuchKey`. That's a known gap, not a bug in this endpoint.

---

New to a term? See the [glossary](../../general/glossary.md).
