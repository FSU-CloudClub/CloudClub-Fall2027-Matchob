# POST /suggestions

**Contract:** [api-contracts.md → POST /suggestions](../../general/api-contracts.md#post-suggestions)
**Code:** `src/bedrock-pipeline/app.py` → `create_suggestions()`

## What it does
Takes the user's resume text and a job description and returns the model's suggestions for tailoring the resume to that job. Nothing is saved.

## How it works
1. `get_user_id(app.current_event.raw_event)`. `None` → 401.
2. `read_json_body(app.current_event)`. Error → 400.
3. `validate_fields(body, SUGGESTION_FIELDS, partial=False)`. Error → 400.
4. `variables = prompt_variables(fields)`.
5. `response = call_bedrock(variables)`. Errors are mapped below.
6. `was_blocked(response)` → 422.
7. `reply = parse_reply(response)`. `None` → 502.
8. Log `suggestions created` with `user_id` and `stop_reason`, and return `reply`. It's sent with status 200.

**Why `was_blocked` before `parse_reply`:** a blocked reply is the guardrail's plain-text message, so parsing it would report a `502` instead of a `422`.

## Objects and calls

**`call_bedrock(variables)`**: see [helpers.md](../helpers.md#call_bedrockvariables--dict). It's the only network call, and the only thing the tests mock.

| What it raises | Where it comes from | Status |
|---|---|---|
| `ClientError` with a code in `ERROR_STATUS` | Bedrock is busy or the model timed out | `ERROR_STATUS[code]` (503 or 504) |
| Any other `ClientError` | Wrong ARN, missing permission, a variable the prompt doesn't know | 500 |
| `ReadTimeoutError` / `ConnectTimeoutError` | No answer within the client's 25 s `read_timeout` | 504 |

Connection failures return `503`. Unexpected route exceptions return a generic JSON `500`; only the exception type is logged to avoid logging request text.

`ReadTimeoutError` is in `botocore.exceptions`, but it isn't a `ClientError`, so it needs its own `except`.

**The response:** only two parts are used, `response["stopReason"]` (by `was_blocked`) and `response["output"]["message"]["content"]` (by `parse_reply`). The model's JSON is returned as-is. Don't add, rename or wrap fields; the contract's shape comes from the console prompt.

## Helpers
| Helper | Where | New or existing | Signature → returns |
|---|---|---|---|
| `get_user_id` | `matchob_common.auth` | Existing | `(event) → str \| None` |
| `read_json_body` | `matchob_common.http` | Existing | `(current_event) → (body, error)` |
| `validate_fields` | `matchob_common.validators` | Existing | `(body, spec, partial) → (fields, error)` |
| `str_length`, `REQUIRED` | `matchob_common.validators` | Existing | Used in the field specs |
| `SUGGESTION_FIELDS`, `JOB_DESCRIPTION_FIELDS`, `job_description` | `bedrock_helpers` | **New** | Specs and validator |
| `prompt_variables`, `call_bedrock`, `was_blocked`, `parse_reply`, `ERROR_STATUS` | `bedrock_helpers` | **New** | See [helpers.md](../helpers.md) |

## Errors
| Condition | Status | `error` message | Log |
|---|---|---|---|
| No user | 401 | `Unauthorized` | none |
| Body isn't JSON | 400 | `Invalid JSON body` | none |
| Missing or bad field | 400 | From `validate_fields`, e.g. `resumeText is required`, `jobDescription title is required` | none |
| `was_blocked(response)` | 422 | `Request blocked by content filters` | `logger.info("suggestions blocked", extra={"user_id": ..., "stop_reason": ...})` |
| `parse_reply` returns `None` | 502 | `AI returned an invalid response` | `logger.error("invalid model reply", extra={"user_id": ..., "stop_reason": ...})`. `stop_reason` `max_tokens` means the reply was cut off: ask the console owner to raise the prompt's max tokens |
| `ClientError` code `ThrottlingException` or `ServiceUnavailableException` | 503 | `AI service is busy, try again` | `logger.warning("bedrock busy", extra={"code": ...})` |
| `ClientError` code `ModelTimeoutException` | 504 | `AI service timed out` | `logger.warning("bedrock timed out")` |
| `ReadTimeoutError` | 504 | `AI service timed out` | `logger.warning("bedrock timed out")` |
| Any other `ClientError` | 500 | `Internal server error` | `logger.exception("bedrock converse failed")`. Usually setup: a wrong `PROMPT_ARN`, a missing permission or a renamed variable |

Never put the request text in a log, including in `extra`.

## Infrastructure
None. The `CreateSuggestions` event, the Bedrock permissions, `Timeout: 28` and `PROMPT_ARN`, `GUARDRAIL_ID` and `GUARDRAIL_VERSION` are already in `templates/bedrock-template.yaml`. See [README.md → Infrastructure](../README.md#infrastructure).

## Done when
Bedrock can't run locally, so this endpoint is done when its unit tests pass. No AWS calls, no Docker:

```bash
pytest tests/unit/test_bedrock_helpers.py tests/unit/test_create_suggestions.py
```

**`tests/unit/test_bedrock_helpers.py`** already exists and passes. It covers the helpers, so it should keep passing; don't edit it unless you change a helper:

| Test | Expect |
|---|---|
| `prompt_variables` with every field | Every name in `PROMPT_VARIABLES`, each as `{"text": ...}` |
| `prompt_variables` without `company` or `supportingContext` | Those variables are `{"text": ""}`, not missing |
| `job_description` with a string, a list or `None` | `ValueError("must be an object with title and text")` |
| `job_description` missing `title`, or with an unknown key | `ValueError` with `validate_fields`' message |
| `was_blocked` with `stopReason` `guardrail_intervened`, `content_filtered`, `end_turn` | `True`, `True`, `False` |
| `parse_reply` with a JSON object | The same dict |
| `parse_reply` with the object inside ` ```json ` fences | The same dict |
| `parse_reply` with plain text, `[]`, `"text"` or a cut-off object | `None` |

**`tests/unit/test_create_suggestions.py`** is yours to write: the route. Copy the `endpoint` fixture from [test_create_upload_url.py](../../../tests/unit/test_create_upload_url.py) (load `src/bedrock-pipeline/app.py`, drop `bedrock_helpers` from `sys.modules`). Then patch `get_user_id`, set `app.current_event.json_body` and patch `call_bedrock` with a `MagicMock` whose `return_value` is a fake `converse` response:

```python
def fake_response(text, stop_reason="end_turn"):
    return {"stopReason": stop_reason, "output": {"message": {"content": [{"text": text}]}}}
```

| Test | Expect |
|---|---|
| Valid body, reply `{"suggestions": [...]}` | `200` and the reply unchanged; `call_bedrock` called once with `prompt_variables(fields)` |
| `get_user_id` returns `None` | `401`, `call_bedrock` not called |
| Malformed JSON, `{}`, a missing field, a field too long, an unknown field, `jobDescription` as a string | `400`, `call_bedrock` not called |
| `stop_reason="guardrail_intervened"` | `422` |
| Reply isn't JSON, or is a JSON list | `502` |
| `side_effect=ClientError({"Error": {"Code": "ThrottlingException"}}, "Converse")` | `503` |
| `side_effect=ClientError(...)` with `ModelTimeoutException` | `504` |
| `side_effect=ReadTimeoutError(endpoint_url="x")` | `504` |
| `side_effect=ClientError(...)` with `AccessDeniedException` | `500` |

**Optional smoke test** once the console prompt exists. Put the three real IDs in `env.json`, have AWS credentials set up (`sam local` passes them to the container), then run `python dev.py`:

```bash
curl -i -X POST localhost:3001/suggestions -H "X-Local-User: u1" -H "Content-Type: application/json" \
  -d '{"resumeText":"Sarah Lee. CS student at FSU. Built a REST API in Python.","jobDescription":{"title":"Backend Intern","text":"Python, AWS, REST APIs."}}'
# 200 {"suggestions": [...]}
```

Check the Lambda's log for how long the call took. If it's anywhere near 25 seconds, tell the console owner (see [README → Time limits](../README.md#time-limits)).

## Gotchas
- `modelId` takes the prompt **version** ARN (ends in `:1`, `:2`, ...). A prompt ARN without a version, or a model ID, skips the console prompt.
- `ReadTimeoutError` isn't a `ClientError`. `except ClientError` alone lets a timeout become an unhandled 500.
- Leave retries off on the client. boto3 retries throttling by default, which can turn one slow call into two and pass 29 seconds.
- A renamed `{{variable}}` in the console fails every call with `ValidationException` (500) until `PROMPT_VARIABLES` is updated.
- `"company": null` is a 400. The frontend should leave optional fields out instead of sending `null`.
- An optional field sent as `""` is a 400 too (`must be 1-2000 characters`). Leave it out.

---

New to a term? See the [glossary](../../general/glossary.md).
