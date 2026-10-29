# Resumes Pipeline Helpers

**Code:** `src/s3-pipeline/resume_helpers.py`.

Everything below is implemented. This is the reference for names, parameters, return values and behavior. Generic helpers (`read_json_body`, `to_json`, `validate_fields`, the validators) already exist in [shared-helpers.md](../general/shared-helpers.md).

`resume_helpers.py` creates `table`, `BUCKET` and `presign_client`. `app.py` imports `table` and `BUCKET` from it, so each client is created once. `app.py` keeps its own `s3` client for calls the Lambda makes itself, like `delete_object`.

## Constants

| Name | Value | Used by |
|---|---|---|
| `ALLOWED_CONTENT_TYPES` | `{"application/pdf": "pdf"}` | Upload validation and the file extension in `s3_key` |
| `URL_EXPIRES_IN` | `300` | Every presigned URL, and the `expiresIn` field in responses |

## Validators

Follow the shared validator rule: return the cleaned value or raise `ValueError("must ...")`.

### `str_length(low, high)` → validator (in `matchob_common/validators.py`)
Builds a validator that accepts a string whose trimmed length is from `low` to `high`, and returns it trimmed. Message: `must be {low}-{high} characters`. Generic, so it goes in the shared layer.

### `tag_list(value)` → `list[str]`
- Must be a list of at most 10 items.
- Each item must be a string, 1–30 characters after trimming.
- Removes duplicates, keeping the first occurrence's order.
- Message on any failure: `must be a list of at most 10 strings, each 1-30 characters`.

## Field specs (for `validate_fields`)

```
UPLOAD_FIELDS = {
    "fileName":    (REQUIRED, str_length(1, 100)),
    "contentType": (REQUIRED, one_of(*ALLOWED_CONTENT_TYPES)),
}

RESUME_FIELDS = {                     # only ever used with partial=True
    "name": (REQUIRED, str_length(1, 100)),
    "tags": (REQUIRED, tag_list),
}
```

Any other field, including `id`, `s3Key` or `uploadedAt`, is rejected with `Unknown fields: ...`.

## Clients

### `presign_client`
An S3 client used **only** for `generate_presigned_url`.
- `endpoint_url = os.environ.get("S3_PUBLIC_ENDPOINT") or None`
- `config = Config(signature_version="s3v4", s3={"addressing_style": "path" if endpoint_url else "virtual"})`

Why a second client: presigning happens entirely in the Lambda, with no network call, and the host goes into the signature. Locally the URL must say `localhost:9090` for your browser, while the Lambda itself talks to `s3:9090`. In AWS both are `None`, so both clients are the same.

Why `s3v4` and `virtual`: real S3 expects Signature Version 4 and bucket-in-hostname URLs. s3mock needs bucket-in-path, hence `path` only when there's a custom endpoint.

## Functions

### `s3_key(user_id, resume_id, content_type) → str`
Returns `quarantine/users/{user_id}/resumes/{resume_id}.{ALLOWED_CONTENT_TYPES[content_type]}`. Call it only with a validated `content_type`.

### `now_iso() → str`
The current UTC time as `2026-10-22T14:03:00Z`: `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`. Used for `uploadedAt`. This format sorts correctly as a string, which `list_resumes` relies on.

### `presign_upload(key, content_type) → str`
`presign_client.generate_presigned_url("put_object", Params={"Bucket": BUCKET, "Key": key, "ContentType": content_type}, ExpiresIn=URL_EXPIRES_IN)`

| Param | Why |
|---|---|
| `"put_object"` | Allows PUT to the quarantine key; reusable until expiry |
| `ContentType` | Signed into the URL, so the browser must send the **same** `Content-Type` header. This checks the caller's declared type only; non-PDF bytes can still be uploaded with `application/pdf` |
| `ExpiresIn` | Seconds the URL works |

### `presign_download(key, file_name) → str`
`presign_client.generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": key, "ResponseContentDisposition": f'inline; filename="{file_name}"'}, ExpiresIn=URL_EXPIRES_IN)`

`ResponseContentDisposition` makes S3 send the resume's current `name` as the filename when the user saves it, instead of the UUID key. `inline` lets the browser show a PDF instead of forcing a download. Strip `"` from `file_name` first, or the header breaks.

### `to_resume_object(resume_id, stored) → dict`
Turns a stored resume (from the profile's `resumes` map) into the contract's [resume object](../general/api-contracts.md#resume-object):

```
{
  "id": resume_id,
  "name": stored["name"],
  "tags": stored["tags"],
  "contentType": stored["contentType"],
  "uploadedAt": stored["uploadedAt"],
  "status": stored.get("status", "unverified"),
  "downloadUrl": presign_download(stored["s3Key"], stored["name"]) if is_validated(stored) else None,
  "expiresIn": URL_EXPIRES_IN if is_validated(stored) else 0,
}
```

`is_validated(stored)` requires validated status and a promoted key; legacy records fail closed. Never include `s3Key`. Every endpoint that returns a resume uses this function, so the shape stays consistent.

### `get_resumes(user_id) → dict | None`
Reads only the `resumes` map: `table.get_item(Key={"userId": user_id}, ConsistentRead=True, ProjectionExpression="#resumes", ExpressionAttributeNames={"#resumes": "resumes"})`.
- No `Item` in the response → `None` (no profile → the caller returns 404).
- Otherwise → `item.get("resumes", {})`.

`ProjectionExpression` skips the rest of the profile, including `structuredJsonResume`, which can be large. Let `ClientError` propagate, and let the route turn it into a 500.

### `resume_path_names(resume_id) → dict`
`{"#resumes": "resumes", "#resumeId": resume_id}`. The `ExpressionAttributeNames` every nested write needs. A map key is an attribute **name** in DynamoDB, so the resume ID always goes in names, never in values or directly in the expression string. Add more entries (`"#name": "name"`) as a route needs them.

---

New to a term? See the [glossary](../general/glossary.md).
