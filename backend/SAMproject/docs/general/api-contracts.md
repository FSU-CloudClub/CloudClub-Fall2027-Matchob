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
| `422` | The AI guardrail blocked the request |
| `500` | Server error |
| `502` | The AI returned something that isn't a JSON object |
| `503` | The AI is busy. Try again in a few seconds |
| `504` | The AI took too long |

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

**Send:** every required field. `websites` is optional.

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
| `400` | error | A required field is missing or invalid, or a backend-only field was sent |
| `409` | error | The user already has a profile. Use `PUT` |

### `PUT /profile`

**Send:** only the fields you're changing. The rest stay the same.

```json
{ "major": "Data Science" }
```

| Status | Returns | Why |
|---|---|---|
| `200` | The full profile object | So the frontend doesn't have to merge changes itself |
| `400` | error | Empty body, invalid field, or a backend-only field was sent |
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
| `200` | `{ "message": "Resume deleted" }` | Deletes the S3 file and removes it from `resumes` |
| `404` | error | Not found, or not this user's |

### `GET /resumes/{id}/download-url`

Generates a fresh presigned **download** link for one resume. Use it when a link from `GET /resumes` has expired, so the whole list doesn't have to be fetched again.

**Send:** nothing

| Status | Returns | Why |
|---|---|---|
| `200` | `{ "downloadUrl": "https://...", "expiresIn": 300 }` | `expiresIn` is in seconds |
| `404` | error | Not found, or not this user's |

---

## Suggestions

The frontend parses the resume the user picked for this application into plain text. It then sends that text, the job description and any supporting context here. The backend passes them to a prompt that's set up ahead of time in the Bedrock console, with its model, system prompt, output format and guardrail. It returns the model's JSON unchanged. Nothing is saved.

### `POST /suggestions`

**Send:** `jobDescription` matches the `JobDescription` type in `frontend/types/index.ts`.
```json
{
  "resumeText": "Sarah Lee\nComputer Science, FSU...",
  "jobDescription": {
    "title": "Software Engineering Intern",
    "company": "Acme",
    "text": "We're looking for..."
  },
  "supportingContext": "I want to highlight my cloud club projects."
}
```

| Field | Rules |
|---|---|
| `resumeText` | Required, 1–20,000 characters |
| `jobDescription.title` | Required, 1–200 characters |
| `jobDescription.company` | Optional, 1–200 characters |
| `jobDescription.text` | Required, 1–20,000 characters |
| `supportingContext` | Optional, 1–2,000 characters. What the user wants to highlight, from the supporting context screen |

The limits keep calls fast and cheap. Longer inputs take longer to process, which brings the 29-second limit below closer.

| Status | Returns | Why |
|---|---|---|
| `200` | The model's JSON object, unchanged | |
| `400` | error | Missing, empty, too long or unknown field |
| `422` | error | The guardrail blocked the input or the output |
| `502` | error | The model's reply wasn't a JSON object |
| `503` | error | Bedrock throttled the call. Retry after a few seconds |
| `504` | error | No answer within the time limit. Safe to retry |

**The response shape is set by the Bedrock prompt, not the backend.** The prompt must return this, because each item is the `Recommendation` type in `frontend/types/index.ts`:

```json
{
  "suggestions": [
    {
      "id": "1",
      "suggestion": "Quantify the impact of the API you built, e.g. requests per day or latency saved.",
      "reason": "The posting asks for experience with high-traffic services."
    }
  ]
}
```

| Field | Rules |
|---|---|
| `id` | String, unique within the response. The model numbers them `"1"`, `"2"`, ... |
| `suggestion` | String. The change to make |
| `reason` | String. Why it fits this job |

If the prompt's format changes, update this example and the `Recommendation` type in the same PR.

**Time limit:** API Gateway ends any request after 29 seconds and returns its own `504` with the body `{ "message": "Endpoint request timed out" }`. The backend stops waiting on Bedrock before that, so it normally sends the `504` itself, as `{ "error": ... }`. Treat a `504` as retryable either way.

---

New to a term? See the [glossary](glossary.md).
