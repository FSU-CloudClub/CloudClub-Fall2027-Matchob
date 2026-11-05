# GET /resumes/{resumeId}/download-url

**Contract:** [api-contracts.md → GET /resumes/{id}/download-url](../../general/api-contracts.md#get-resumesiddownload-url)
**Code:** `src/s3-pipeline/app.py` → `create_download_url(resume_id)`

## What it does
Returns a fresh download link for one resume, for when the link from `GET /resumes` has expired. Backs `resumeApi.getDownloadUrl(id)`.

## How it works
1. `get_user_id(app.current_event.raw_event)`. `None` → 401.
2. Validate the resume ID; invalid opaque IDs → 400. Read `get_resumes(user_id)`; a missing profile or resume → 404 `Resume not found`.
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
| No profile | 404 | `Resume not found` | none |
| `resume_id` not in the user's `resumes` (including another user's ID) | 404 | `Resume not found` | none |
| Service/transport/signing failure or malformed stored metadata | 500 | `Internal server error` | Fixed `resume download failed` message; no exception text or traceback |

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

## Review verification — October 29, 2026

Added 12 endpoint tests through the Lambda router for owner success, cross-user
isolation, missing profile/resume, no authentication, service/transport/timeouts,
signing failures, malformed metadata, and real log-output redaction. Request-event
logging is explicitly disabled, including when enabled by the environment.

Run `.venv/bin/python -m pytest tests -q` from `backend/SAMproject`: 93 tests pass.

## Local SAM integration verification — October 29, 2026

Passed through `sam local start-api` on port 3001 using the built root template,
DynamoDB Local and S3Mock on `matchob-local`. Two unique synthetic profiles and a
PDF fixture were created for this run; all temporary records and the object were
removed afterward.

| Check | Result |
| --- | --- |
| Create owner and second profile | 201 each |
| Create upload URL and PUT PDF to S3Mock | 201 / 200 |
| Owner requests download URL | 200 |
| Response expiresIn and signed X-Amz-Expires | 300 seconds |
| Fetch returned URL from S3Mock | 200; bytes exactly match uploaded PDF |
| Other account requests owner's resume | 404 |
| Other account supplies owner's userId in query | 404 |
| No login | 401 |
| Nonexistent resume | 404 |
| Nonexistent profile | 404 |

The local API used `X-Local-User`; SAM skipped the Cognito authorizer as expected.
This verifies container execution, routing, local storage integration, and actual
local file retrieval. It does not prove deployed Cognito/IAM enforcement, S3 public
access blocking, or rejection after URL expiration. Those checks remain pending a
dev AWS deployment. No AWS resources were deployed or changed during this test.

Merge-resolution verification (October 29, 2026): removed the duplicate download route and combined ID validation with safe error handling. Missing profiles and missing/foreign resumes all return the same generic 404. Updated the test expectation and made duplicate-route warnings fail endpoint tests. Full merged suite: 261 passed, 34 subtests passed, with no warnings. Prior local SAM results above predate this merge-resolution fix.
