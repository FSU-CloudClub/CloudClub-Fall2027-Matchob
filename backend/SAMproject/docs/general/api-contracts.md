# API Contracts

## Every request

- **Header:** `Authorization: <Cognito ID token>`. Locally, send `X-Local-User: <any-id>` instead.
- **Never send `userId`.** The backend takes it from the token, so users can't act as someone else.
- **Errors are always `{ "error": "<message>" }`.** Act on the status code, not the message.

| Status | Why |
|---|---|
| `400` | Bad body: invalid JSON, missing, wrong-type or unknown field |
| `401` | Missing or invalid token |
| `404` | It doesn't exist, or it belongs to another user |
| `409` | It already exists |
| `500` | Server error |

When deployed, a bad token is rejected by API Gateway before the Lambda runs, so that `401` body is `{ "message": "Unauthorized" }` instead.

---

## Profile

### Profile object

| Field | Type | Who sets it | Rules |
|---|---|---|---|
| `userId` | string | Backend | From the token |
| `firstname` | string | Frontend | Required, non-empty |
| `lastname` | string | Frontend | Required, non-empty |
| `email` | string | Frontend | Required, valid email |
| `phoneNumber` | string | Frontend | Required. A string so country codes and leading zeros survive |
| `age` | number | Frontend | Required, whole number 13–120 |
| `year` | string | Frontend | Required: `freshman`, `sophomore`, `junior`, `senior` or `graduate` |
| `major` | string | Frontend | Required, non-empty |
| `websites` | string[] | Frontend | Optional, defaults to `[]`. Each must start with `http://` or `https://` |
| `defaultResume` | string \| null | Frontend | Optional, defaults to `null`. Must be a key of `resumes`, so it can only be set with `PUT` once a resume exists. `null` clears it |
| `resumes` | object | Backend | Every resume the user has, keyed by resume ID. Only the resume endpoints change it, so it always matches S3. Starts as `{}` |
| `structuredJsonResume` | object \| null | Backend | Filled in by resume parsing. `null` until then |

What `resumes` looks like on the profile:

```json
"resumes": {
  "3f6c1b2e-...": {
    "s3Key": "users/a1b2c3d4-.../resumes/3f6c1b2e-....pdf",
    "name": "SWE Resume.pdf",
    "tags": ["software"],
    "contentType": "application/pdf",
    "uploadedAt": "2026-10-22T14:03:00Z"
  }
}
```

- **A map, not a list:** rename, tag and delete can update `resumes.<id>` directly, without searching a list or overwriting a concurrent edit.
- **`s3Key`, not a URL:** S3 links expire after minutes. The key is the permanent pointer, and the backend signs a fresh link from it when one is needed.
- **Size limit:** a DynamoDB item is limited to 400 KB, so keep large data like full resume text out of it.

### `GET /profile`

**Send:** nothing

| Status | Returns | Why |
|---|---|---|
| `200` | Profile object | |
| `404` | error | No profile yet. Send the user to create one |

### `POST /profile`

**Send:** every required field. `websites` is optional. Leave out `defaultResume`, because a new profile has no resumes yet.

```json
{
  "firstname": "Sarah",
  "lastname": "Lee",
  "email": "sarah@fsu.edu",
  "phoneNumber": "+18505551234",
  "age": 20,
  "year": "junior",
  "major": "Computer Science",
  "websites": ["https://github.com/sarahlee"]
}
```

| Status | Returns | Why |
|---|---|---|
| `201` | Profile object | Created |
| `400` | error | A required field is missing or invalid, a backend-only field was sent, or `defaultResume` was set |
| `409` | error | The user already has a profile. Use `PUT` |

### `PUT /profile`

**Send:** only the fields you're changing. The rest stay the same.

```json
{ "major": "Data Science", "defaultResume": "3f6c1b2e-..." }
```

| Status | Returns | Why |
|---|---|---|
| `200` | The full profile object | So the frontend doesn't have to merge changes itself |
| `400` | error | Empty body, invalid field, a backend-only field was sent, or `defaultResume` isn't one of the user's resumes |
| `404` | error | No profile yet. Use `POST` |

### `DELETE /profile`

**Send:** nothing

| Status | Returns | Why |
|---|---|---|
| `200` | `{ "message": "Profile deleted" }` | |
| `404` | error | Nothing to delete |

---

## Resumes

Resumes live in the profile's `resumes` map, and the files live in S3. These endpoints match `ResumeApi` in `frontend/services/resumeApi.ts`. Each one needs an existing profile, or it returns `404`.

### Resume object

This is what the resume endpoints return. It's the [stored resume](#profile-object) plus its `id` and a fresh `downloadUrl`, without the internal `s3Key`. It extends the `Resume` type in `frontend/types/index.ts`.

```json
{
  "id": "3f6c1b2e-...",
  "name": "SWE Resume.pdf",
  "tags": ["software"],
  "contentType": "application/pdf",
  "uploadedAt": "2026-10-22T14:03:00Z",
  "downloadUrl": "https://...",
  "expiresIn": 300
}
```

| Field | Rules |
|---|---|
| `id` | Set by the backend |
| `name` | 1–100 characters. Starts as the file name |
| `tags` | Up to 10, each 1–30 characters. Starts as `[]` |
| `contentType` | Set from the upload |
| `uploadedAt` | Set by the backend. ISO 8601 UTC |
| `downloadUrl` | A temporary link, signed for each response, so files are never public |
| `expiresIn` | Seconds until `downloadUrl` stops working. Fetch again after that |

Files must be PDF or DOCX, 5 MB at most. The frontend checks the size, because an S3 upload link can't.

### `GET /resumes`

**Send:** nothing

| Status | Returns | Why |
|---|---|---|
| `200` | Resume object[], newest first | Everything the resume page needs, links included, in one request. `[]` if the user has none |
| `404` | error | No profile yet |

### `POST /resumes/upload-url`

Generates the presigned **upload** link and adds the resume to the profile.

**Send:**
```json
{ "fileName": "SWE Resume.pdf", "contentType": "application/pdf" }
```

| Status | Returns | Why |
|---|---|---|
| `201` | `{ "resumeId": "...", "uploadUrl": "https://..." }` | The file goes straight to S3, so large files don't pass through the API |
| `400` | error | Missing field, or the file type isn't PDF or DOCX |
| `404` | error | No profile yet |

Then upload the file: `PUT` the bytes to `uploadUrl` with the same `Content-Type`, and no `Authorization` header. The link expires after 5 minutes.

```ts
const { uploadUrl } = await resumeApi.getUploadUrl(file.name, file.type);
await fetch(uploadUrl, { method: "PUT", headers: { "Content-Type": file.type }, body: file });
```

### `PATCH /resumes/{id}`

**Send:** `name`, `tags` or both. `tags` replaces the whole list.
```json
{ "name": "SWE Resume - Fall", "tags": ["software", "internship"] }
```

| Status | Returns | Why |
|---|---|---|
| `200` | The full resume object | |
| `400` | error | Empty body or an invalid field |
| `404` | error | Not found, or not this user's |

### `DELETE /resumes/{id}`

**Send:** nothing

| Status | Returns | Why |
|---|---|---|
| `200` | `{ "message": "Resume deleted" }` | Deletes the S3 file and removes it from `resumes`. Clears `defaultResume` if it was the default |
| `404` | error | Not found, or not this user's |

### `GET /resumes/{id}/download-url`

Generates a fresh presigned **download** link for one resume. Use it when a link from `GET /resumes` has expired, so the whole list doesn't have to be fetched again.

**Send:** nothing

| Status | Returns | Why |
|---|---|---|
| `200` | `{ "downloadUrl": "https://...", "expiresIn": 300 }` | `expiresIn` is in seconds |
| `404` | error | Not found, or not this user's |

---

New to a term? See the [glossary](glossary.md).
