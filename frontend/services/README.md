# Resume API boundary

`resumeApi.ts` defines the frontend-facing `ResumeApi` interface. `getResumes()` currently returns sample metadata from `mocks/resumes.ts`; the other methods throw clear not-implemented errors. Feature work can use this boundary without adding backend calls to React components.

| Frontend operation | Expected backend integration |
| --- | --- |
| `getResumes()` | `GET /resumes` or equivalent; return the shared `Resume` model. |
| `getUploadUrl(fileName, contentType)` | `POST /resumes/upload-url` or equivalent. The assigned teammate will build the presigned upload flow. |
| `renameResume(id, name)` / `updateTags(id, tags)` | `PATCH /resumes/:id` or equivalent. |
| `deleteResume(id)` | `DELETE /resumes/:id` or equivalent. |
| `getDownloadUrl(id)` | Return an authorized file URL. |

The backend still needs to specify authentication, upload URL and confirmation payloads, the download response, file limits, and error shapes. The parsing and autofill teams can add their service contracts when those interfaces are agreed. This skeleton does not store AWS credentials or call DynamoDB, S3 SDKs, or AI providers.
