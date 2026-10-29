# POST /resumes/upload-url

**Contract:** [api-contracts.md → POST /resumes/upload-url](../../general/api-contracts.md#post-resumesupload-url)
**Code:** `src/s3-pipeline/app.py` → `create_upload_url()`

## What it does
Adds a new resume to the user's profile and returns a presigned URL the browser uploads the file to, straight to S3.

The signed MIME header is still only a caller claim. Actual content is checked by
`upload_validator.lambda_handler`, triggered by S3 object creation under
`quarantine/`. See [upload-validation.md](../upload-validation.md) for validation,
cleanup, race handling, and local testing. Downloads are blocked until validation
succeeds; a successful PUT alone is not sufficient.

## How it works
1. `get_user_id(app.current_event.raw_event)`. `None` → 401.
2. `read_json_body(app.current_event)`. Error → 400.
3. `validate_fields(body, UPLOAD_FIELDS, partial=False)`. Error → 400.
4. `resume_id = str(uuid.uuid4())`. The backend picks the ID, never the client.
5. `key = s3_key(user_id, resume_id, fields["contentType"])`.
6. Build the stored resume: `{"s3Key": key, "status": "pending", "name": fields["fileName"], "tags": [], "contentType": fields["contentType"], "uploadedAt": now_iso()}`.
7. Add it to the profile with `table.update_item` (below). `ConditionalCheckFailedException` → 404.
8. `upload_url = presign_upload(key, fields["contentType"])`.
9. Log `resume upload url created` with `user_id` and `resume_id`, and return `{"resumeId": resume_id, "uploadUrl": upload_url}, 201`.

Write to DynamoDB **before** presigning. If the write fails, the client never gets a URL, so there's never a file in S3 with no record.

## Objects and calls

**`table.update_item(...)`**

| Parameter | Value | Why |
|---|---|---|
| `Key` | `{"userId": user_id}` | The caller's own profile |
| `UpdateExpression` | `"SET #resumes.#resumeId = :resume"` | Adds one entry to the map without touching the others |
| `ExpressionAttributeNames` | `resume_path_names(resume_id)` | The resume ID is a map key, so it's a name |
| `ExpressionAttributeValues` | `{":resume": stored}` | The dict from step 6 |
| `ConditionExpression` | `"attribute_exists(userId)"` | Without it, `update_item` would create a profile with only a `resumes` field for a user who has none |

**`presign_upload(key, content_type)`**: see [helpers.md](../helpers.md#presign_uploadkey-content_type--str). No network call; it can't fail because of a missing object.

## Helpers
| Helper | Where | New or existing | Signature → returns |
|---|---|---|---|
| `read_json_body` | `matchob_common.http` | Existing | `(current_event) → (body, error)` |
| `validate_fields` | `matchob_common.validators` | Existing | `(body, spec, partial) → (fields, error)` |
| `str_length` | `matchob_common.validators` | **New** | `(low, high) → validator` |
| `UPLOAD_FIELDS`, `ALLOWED_CONTENT_TYPES` | `resume_helpers` | **New** | Spec and constants |
| `s3_key`, `now_iso`, `presign_upload`, `resume_path_names` | `resume_helpers` | **New** | See [helpers.md](../helpers.md) |

## Errors
| Condition | Status | `error` message | Log |
|---|---|---|---|
| No user | 401 | `Unauthorized` | none |
| Body isn't JSON | 400 | `Invalid JSON body` | none |
| Missing or bad field | 400 | From `validate_fields`, e.g. `fileName is required`, `contentType must be one of: application/pdf, ...` | none |
| `ConditionalCheckFailedException` | 404 | `Profile not found` | none |
| `ClientError` code `ValidationException` | 500 | `Internal server error` | `logger.exception(...)`. Means the profile has no `resumes` map; see Gotchas |
| Any other `ClientError` | 500 | `Internal server error` | `logger.exception("dynamodb update_item failed")` |

## Infrastructure
- `templates/s3-template.yaml` defines the API and S3 validator, scoped IAM permissions, and quarantine cleanup rules.
- Needs `S3_PUBLIC_ENDPOINT` (already set up, see setup task 2 in [README.md](../README.md#setup-tasks-do-once-before-the-endpoints)).

## Done when
```bash
H=(-H "X-Local-User: u1" -H "Content-Type: application/json")
# create a profile for u1 first (see post-profile.md)
R=$(curl -s -X POST localhost:3001/resumes/upload-url "${H[@]}" -d '{"fileName":"test.pdf","contentType":"application/pdf"}')
echo "$R"                                                              # 201 {"resumeId": ..., "uploadUrl": "http://localhost:9090/..."}
URL=$(echo "$R" | python3 -c 'import json,sys; print(json.load(sys.stdin)["uploadUrl"])')
curl -i -X PUT "$URL" -H "Content-Type: application/pdf" --data-binary @some.pdf   # 200 from s3mock
aws s3 ls s3://matchob-uploads/quarantine/users/u1/resumes/ --endpoint-url http://localhost:9090   # quarantined; locally invoke the validator separately

curl -i -X POST localhost:3001/resumes/upload-url "${H[@]}" -d '{"fileName":"x.png","contentType":"image/png"}'      # 400
curl -i -X POST localhost:3001/resumes/upload-url -H "X-Local-User: nobody" -H "Content-Type: application/json" -d '{"fileName":"a.pdf","contentType":"application/pdf"}'   # 404
```

## Gotchas
- The upload URL must contain `localhost:9090`, not `s3:9090`. If it says `s3:9090`, you presigned with `s3` instead of `presign_client`.
- The `PUT` to S3 must send exactly the signed `Content-Type`, or S3 rejects it with `SignatureDoesNotMatch` (403).
- `SET resumes.<id>` fails with `ValidationException` if the profile has no `resumes` map at all. Profiles from `POST /profile` and the local seed user always have one.
- Don't use the client's `fileName` in the S3 key. It can contain `/`, spaces or `..`. It's only the display `name`.

---

New to a term? See the [glossary](../../general/glossary.md).
