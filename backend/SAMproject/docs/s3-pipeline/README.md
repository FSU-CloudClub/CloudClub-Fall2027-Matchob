# Resumes Pipeline (S3)

**Purpose:** Upload, list, rename, tag, download and delete the signed-in user's resume files.
**Tech:** Python 3.13, Powertools, boto3 S3 client (presigned URLs) and DynamoDB resource API.
**Role in the project:** Files live in S3. Their metadata lives in the profile's `resumes` map in the users table. This Lambda keeps the two in sync.

| | |
|---|---|
| Template | `templates/s3-template.yaml` (`ResumesStack` in the root) |
| Code | `src/s3-pipeline/app.py`, `src/s3-pipeline/resume_helpers.py` |
| Contract | [api-contracts.md → Resumes](../general/api-contracts.md#resumes) |
| Helpers | [helpers.md](helpers.md) and [shared-helpers.md](../general/shared-helpers.md) |

## Endpoints

| Endpoint | Function | Doc |
|---|---|---|
| `GET /resumes` | `list_resumes()` | [list-resumes.md](endpoints/list-resumes.md) |
| `POST /resumes/upload-url` | `create_upload_url()` | [create-upload-url.md](endpoints/create-upload-url.md) |
| `PATCH /resumes/{resumeId}` | `update_resume(resume_id)` | [update-resume.md](endpoints/update-resume.md) |
| `DELETE /resumes/{resumeId}` | `delete_resume(resume_id)` | [delete-resume.md](endpoints/delete-resume.md) |
| `GET /resumes/{resumeId}/download-url` | `create_download_url(resume_id)` | [create-download-url.md](endpoints/create-download-url.md) |

Suggested order: setup tasks → `create-upload-url` (nothing else works without a resume) → `list-resumes` → `create-download-url` → `update-resume` → `delete-resume`.

## Setup tasks (do once, before the endpoints)

All done. Kept here so you know what's already in place.

1. ~~**Create `resume_helpers.py`**~~ Done: every helper in [helpers.md](helpers.md) is in `src/s3-pipeline/resume_helpers.py`, and `str_length` is in `matchob_common/validators.py`.
2. ~~**Declare `S3_PUBLIC_ENDPOINT`.**~~ Done: `templates/s3-template.yaml` declares it as `""` (real S3 in AWS), and `env.example.json` sets it to `http://localhost:9090`. The Lambda talks to s3mock at `http://s3:9090` (`S3_ENDPOINT`), but presigned URLs must say `localhost:9090` for your browser, and the host is part of the signature. So `presign_client` signs with `S3_PUBLIC_ENDPOINT`; signing makes no network call. If your `env.json` predates these, copy `S3_ENDPOINT` and `S3_PUBLIC_ENDPOINT` from `env.example.json` (`dev.py` only creates `env.json` when it's missing).
3. ~~**Update the local seed user.**~~ Done: `docker/seed/users.json` matches the [profile data model](../dynamodb-pipeline/README.md#data-model), including `"resumes": {"M": {}}`.

## Infrastructure

Everything is in `templates/s3-template.yaml`. All 5 routes are already declared, so until a route function exists in `app.py`, its path returns Powertools' `404 Not found`.

| Resource | What it is |
|---|---|
| `UploadBucket` | Private bucket, all public access blocked. CORS allows `GET` and `PUT` from any origin, so the browser can use presigned URLs. Narrow `AllowedOrigins` to the extension's origin before production |
| `ResumesApi` | API Gateway, stage `dev`, Cognito authorizer from the `UserPoolArn` parameter |
| `ResumesFunction` | The Lambda. `S3CrudPolicy` on the bucket, `DynamoDBCrudPolicy` on the users table, one `Api` event per route |
| `SharedLayer` | This stack's copy of `src/shared` |

| Parameter | From |
|---|---|
| `UserPoolArn` | `SharedStack.Outputs.UserPoolArn` |
| `UsersTableName` | `ProfileStack.Outputs.UsersTableName` |

| Environment variable | AWS | Local (`env.json`) |
|---|---|---|
| `USERS_TABLE` | The table name from `ProfileStack` | `MatchobUsers` |
| `UPLOAD_BUCKET` | The generated bucket name | `matchob-uploads` (created by s3mock on start) |
| `S3_ENDPOINT` | `""` (real S3) | `http://s3:9090` |
| `S3_PUBLIC_ENDPOINT` | `""` (real S3) | `http://localhost:9090` |
| `DYNAMODB_ENDPOINT` | `""` (real DynamoDB) | `http://dynamodb:8000` |

A presigned URL carries the Lambda role's permissions, so `S3CrudPolicy` is what allows the browser's upload and download. No extra permission is needed for presigning itself.

## Objects at the top of `app.py`

| Object | What it is |
|---|---|
| `table` | DynamoDB `Table` for the users table. Resumes are read and written inside each user's item |
| `s3` | S3 client for calls the Lambda makes itself (`delete_object`). Uses `S3_ENDPOINT` |
| `BUCKET` | `UPLOAD_BUCKET` |
| `logger` | Powertools `Logger`, service `resumes` |
| `app` | `APIGatewayRestResolver(serializer=to_json)` |

## Storage design

```
users table, one item per user                     S3 bucket
userId: "abc"                                      users/abc/resumes/3f6c....pdf
resumes:                                           users/abc/resumes/9a1d....docx
  "3f6c...": {s3Key, name, tags,
              contentType, uploadedAt}
  "9a1d...": {...}
defaultResume: "3f6c..."
```

- **Key format:** `quarantine/users/<userId>/resumes/<resumeId>.pdf` for uploads; `users/<userId>/resumes/<resumeId>/validated/<uuid>.pdf` after validation. The `userId` prefix keeps users' files apart and makes "delete everything for a user" one prefix.
- **Never store URLs.** Store `s3Key` and sign a fresh URL for each response.
- **Write to DynamoDB with nested paths** (`resumes.<id>`, `resumes.<id>.name`) and a `ConditionExpression`, so each write touches one resume and fails cleanly if it doesn't exist.
- **Ownership comes for free.** Every read and write uses the caller's own `userId` as the key, so another user's `resumeId` is simply "not found" (404).

## Every route follows the same shape

1. `get_user_id(app.current_event.raw_event)`. `None` → `401 Unauthorized`.
2. Routes with a body: `read_json_body` then `validate_fields` with the route's spec. Failure → `400`.
3. One conditional DynamoDB call. `ConditionalCheckFailedException` → `404`.
4. The S3 step, if any: presign (never fails for a missing object) or `delete_object`.
5. `logger.info("<what happened>", extra={"user_id": user_id, "resume_id": resume_id})` and return.
6. Any other `ClientError` → `logger.exception(...)` and `500 Internal server error`.

## Known gaps (from the contract's open decisions)

- **Abandoned uploads.** Pending records have no download URL. If the upload never completes or validation exhausts retries, metadata remains pending; the user can delete it or upload again.
- **Validation follows storage.** Invalid bytes briefly enter private quarantine. The validator enforces PDF contents and 5 MiB before promotion; see [upload-validation.md](upload-validation.md).
- **`DELETE /profile` leaves files behind.** See [delete-profile.md](../dynamodb-pipeline/endpoints/delete-profile.md#gap-resume-files-are-left-in-s3).

---

New to a term? See the [glossary](../general/glossary.md).
