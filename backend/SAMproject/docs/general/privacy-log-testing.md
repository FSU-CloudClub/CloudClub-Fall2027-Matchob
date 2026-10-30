# P9-2: private-data marker testing

Run the automated checks from `backend/SAMproject`:

```sh
.venv/bin/python -m pytest tests/test_private_error_logs.py tests/test_privacy_flow_logs.py -q
```

These checks invoke the Lambda handlers with fake data and inspect real emitted JSON logs, captured stdout/stderr, and Python log records. AWS calls are mocked. Event logging is deliberately enabled through the environment to verify the handlers still suppress request logging.

The success sequence covers profile create/read/update, upload-URL creation, resume rename/download-URL signing through PATCH, listing, download-URL refresh, suggestions, resume deletion, and profile deletion. Tests assert that requests succeed and expected operation logs exist, preventing an empty-log false pass. Separate cases cover invalid input, missing authentication, blocked/invalid model replies, throttling, unexpected suggestions errors, and service failures. The P9-1 tests also cover profile S3 cleanup failure and AWS exception messages.

The fixture represents resume text passed to suggestions and resume metadata passed to upload signing. It does not upload or parse a PDF, run the extension, or read AWS logs. It is not an end-to-end storage integration test.

## Remaining dev-environment check

Use only synthetic data. For an identifiable test run, append a unique run suffix to these markers and put all four personal/resume markers in a fake resume:

| Field | Base marker |
| --- | --- |
| Name | `P9CanaryJane` |
| Email | `p9-canary@example.test` |
| Phone | `555-0199-9272` |
| Resume phrase | `P9_RESUME_SECRET_PHRASE` |
| Job phrase | `P9_JOB_SECRET_PHRASE` |

1. Record deployed revision, UTC start time, synthetic account ID, and the exact markers. Identify the profile, resume, and suggestions Lambda log groups, configured API access/execution logs, any enabled storage-access logs, and extension console contexts. Do not enable request-body logging to perform this check.
2. Create/read/update the fake profile. Upload the fake resume, list it, rename/tag it, preview/download it, and request suggestions using the job marker. Confirm each operation actually succeeds; a stub/404 does not count as coverage.
3. Exercise rejected inputs and unauthenticated requests. In a controlled test environment, exercise service/cleanup failures using fault injection; do not change production permissions to force failures. Record any error paths that cannot be exercised.
4. Delete the resume and profile. Record operation outcomes and the UTC end time. Keep deletion correctness tracked separately under P7.
5. Wait for log delivery, then search the complete run window in every identified log source for **each marker independently**, including JSON-escaped forms for any marker that needs escaping. Search all relevant extension contexts as well. Do not limit the search to ERROR lines. Record log groups/contexts, time window, queries, and hit counts; avoid copying signed URLs or real user data into the evidence.
6. A hit fails the check. Diagnose the emitting source and add a regression test before rerunning. Zero hits count only if expected operation logs are present and every required operation/source was covered. Missing flow steps, inaccessible logs, or missing log delivery leave the result Partial.

Current limitation: backend resume listing/download routing is implemented and included in marker tests, but frontend integration and deployed verification remain outstanding. Automated backend checks can pass now; the full P9-2 criterion stays Partial until the above flow and log search are completed.
