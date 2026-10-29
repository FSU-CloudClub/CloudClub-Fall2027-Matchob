# Resume upload validation

The upload API accepts `application/pdf` only and creates `pending` metadata.
A presigned PUT writes to `quarantine/users/<userId>/resumes/<resumeId>.pdf`.
The API role can write quarantine objects but cannot read them or write promoted
objects. The bucket is private.

S3 ObjectCreated events under `quarantine/` invoke `UploadValidationFunction`.
It reads at most 5 MiB + 1 byte, ignoring the claimed MIME type and filename.
`pypdf` strict parsing checks the document, page tree, and page content streams.
Empty, oversized, malformed, encrypted, zero-page, and over-100-page PDFs fail.
A PDF header alone is insufficient. Scanned PDFs do not require extractable text.
This is file-format validation, not malware scanning or PDF sanitization.
Parser diagnostics and document contents are not logged.

On success, the worker writes the exact validated bytes to a fresh key under
`users/<userId>/resumes/<resumeId>/validated/<uuid>.pdf`. It never copies from the
mutable upload key. A conditional metadata update switches `pending` to
`validated` and points `s3Key` at the promoted object. Competing workers use
separate keys; a losing worker deletes only its own candidate. A deleted resume
cannot be recreated by validation. Replaying an upload URL cannot overwrite an
accepted document. Rejected files get `rejected` status and are deleted.

GET list, PATCH responses, and GET download-url only issue download URLs for
validated records with promoted keys. Other records have `downloadUrl: null` and
`expiresIn: 0`; download-url returns 409. The API role additionally limits S3 GET
to the promoted prefix. Existing records without status are `unverified` and
require re-upload; no legacy file is silently trusted. There is currently no
backend processor that reads resume objects from S3. Any future processor must
use the same validated-status gate and promoted key. The suggestions API accepts
client-supplied text independently of this file flow.

## Failures and retention

Infrastructure failures propagate for Lambda retry. Duplicate notifications and
notifications arriving after deletion are safe. Uncommitted promotion candidates
carry `validation=pending`; the tag is removed after metadata commit, including
on retry. Bucket lifecycle rules expire those tagged candidates and quarantine
objects after one day. S3 lifecycle deletion is asynchronous, not a strict
24-hour deletion guarantee. Rejected files are deleted immediately in the normal
path; lifecycle is the fallback for crashes, failed cleanup, and abandoned files.

A parser timeout or exhausted infrastructure retries leaves the record pending
and unavailable. Metadata is not automatically expired; delete the record and
retry with a new upload if necessary. Monitor Lambda errors/throttles in AWS.

## Deployment and client integration

Deploy the updated S3 SAM stack, including both Lambda functions, IAM permissions,
S3 event notification, and lifecycle rules. Upload URLs still return the same
`resumeId` and `uploadUrl` fields. The backend now rejects DOCX, matching the
frontend PDF picker. After PUT, poll GET /resumes until the status is validated or
rejected. Never enable preview/download while pending. The frontend currently
uses a mock upload service and is not yet connected to this API.

The local s3mock/SAM API setup does not automatically invoke the validator.
For local testing, invoke `UploadValidationFunction` with an S3 event containing
`eventSource: aws:s3`, `eventName: ObjectCreated:Put`, the configured bucket name,
and the URL-encoded quarantine key, using the same local environment overrides.
Deploying is required to verify real S3 notifications and IAM enforcement.

Run backend unit tests and template validation:

```sh
.venv/bin/python -m pytest tests/unit -q
sam validate --lint --template-file templates/s3-template.yaml
```

References: [pypdf PdfReader](https://pypdf.readthedocs.io/en/stable/modules/PdfReader.html)
and [AWS S3 event prefix filtering](https://aws.amazon.com/blogs/compute/avoiding-recursive-invocation-with-amazon-s3-and-aws-lambda/).
