# GET /resumes/{resumeId}/download-url

**Contract:** [api-contracts.md → GET /resumes/{id}/download-url](../../general/api-contracts.md#get-resumesiddownload-url)
**Code:** `src/s3-pipeline/app.py` → `create_download_url(resume_id)`

## What it does
Returns a fresh download link for one resume, for when the link from `GET /resumes` has expired. Backs `resumeApi.getDownloadUrl(id)`.

## How it works
1. `get_user_id(app.current_event.raw_event)`. `None` → 401.
2. `resumes = get_resumes(user_id)`. `None` → 404 `Profile not found`.
3. `stored = resumes.get(resume_id)`. `None` → 404 `Resume not found`.
4. `url = presign_download(stored["s3Key"], stored["name"])`.
5. Log `resume download url created` with `user_id` and `resume_id`, and return `{"downloadUrl": url, "expiresIn": URL_EXPIRES_IN}`. It's sent with status 200.

## Objects and calls

**Route:** `@app.get("/resumes/<resume_id>/download-url")`. Powertools passes the path segment as the `resume_id` argument. The template uses `{resumeId}` for the same segment.

**`presign_download`**: see [helpers.md](../helpers.md#presign_downloadkey-file_name--str). The URL is signed for the resume's current `name`, so a renamed resume downloads under its new name.

## Helpers
| Helper | Where | New or existing | Signature → returns |
|---|---|---|---|
| `get_resumes` | `resume_helpers` | **New** | `(user_id) → dict \| None` |
| `presign_download` | `resume_helpers` | **New** | `(key, file_name) → str` |
| `URL_EXPIRES_IN` | `resume_helpers` | **New** | `300` |

## Errors
| Condition | Status | `error` message | Log |
|---|---|---|---|
| No user | 401 | `Unauthorized` | none |
| No profile | 404 | `Profile not found` | none |
| `resume_id` not in the user's `resumes` (including another user's ID) | 404 | `Resume not found` | none |
| `ClientError` from `get_item` | 500 | `Internal server error` | `logger.exception("dynamodb get_item failed")` |

## Infrastructure
None. The `CreateDownloadUrl` event is in `templates/s3-template.yaml`.

## Done when
```bash
curl -s localhost:3001/resumes/<resumeId>/download-url -H "X-Local-User: u1"     # 200
curl -i localhost:3001/resumes/<resumeId>/download-url -H "X-Local-User: u2"     # 404, not u2's resume
curl -i localhost:3001/resumes/does-not-exist/download-url -H "X-Local-User: u1" # 404
```

## Gotchas
- Don't check that the S3 object exists (`head_object`) first. It costs a network call on every request, and the contract treats a missing upload as a known gap.
- Return 404, not 403, for another user's resume, so nobody can probe which IDs exist.

---

New to a term? See the [glossary](../../general/glossary.md).
