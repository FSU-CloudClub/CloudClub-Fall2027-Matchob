# Suggestions Pipeline Helpers

**Code:** `src/bedrock-pipeline/bedrock_helpers.py`.

Everything below is implemented and tested by `tests/unit/test_bedrock_helpers.py`. This is the reference for names, parameters, return values and behavior. Generic helpers (`read_json_body`, `to_json`, `validate_fields`, `str_length`, `REQUIRED`) already exist in [shared-helpers.md](../general/shared-helpers.md). No new shared helper is needed.

`bedrock_helpers.py` creates `bedrock` and reads `PROMPT_ARN`, `GUARDRAIL_ID` and `GUARDRAIL_VERSION` from the environment. `app.py` imports the functions below and never touches the client directly.

## Constants

| Name | Value | Used by |
|---|---|---|
| `PROMPT_ARN` | `os.environ["PROMPT_ARN"]` | `call_bedrock` |
| `GUARDRAIL_ID` | `os.environ["GUARDRAIL_ID"]` | `call_bedrock` |
| `GUARDRAIL_VERSION` | `os.environ["GUARDRAIL_VERSION"]` | `call_bedrock` |
| `PROMPT_VARIABLES` | See below | `prompt_variables`. The console prompt must use these exact names |
| `BLOCKED_STOP_REASONS` | `{"guardrail_intervened", "content_filtered"}` | `was_blocked` |
| `ERROR_STATUS` | `{"ThrottlingException": 503, "ServiceUnavailableException": 503, "ModelTimeoutException": 504}` | The route, to pick a status for a Bedrock `ClientError`. Any other code → 500 |

```
PROMPT_VARIABLES = {                  # console {{variable}} → where the value comes from
    "resume":             lambda f: f["resumeText"],
    "job_title":          lambda f: f["jobDescription"]["title"],
    "company":            lambda f: f["jobDescription"]["company"] or "",
    "job_description":    lambda f: f["jobDescription"]["text"],
    "supporting_context": lambda f: f["supportingContext"] or "",
}
```

This dict is the only link between our code and the console prompt. When the console owner renames a variable, change it here, not in the route.

## Validators

Follow the shared validator rule: return the cleaned value or raise `ValueError("must ...")`.

### `job_description(value)` → `dict`
- Not a dict → `ValueError("must be an object with title and text")`. Check this first, or `validate_fields`' own message (`Request body must be a JSON object`) ends up in the error.
- Otherwise `validate_fields(value, JOB_DESCRIPTION_FIELDS, partial=False)`. On error, `raise ValueError(error)`. The outer `validate_fields` adds the prefix, so the client sees e.g. `jobDescription title is required`.
- Returns the cleaned dict. `company` is `None` when it wasn't sent.

Pipeline-specific, so it stays in `bedrock_helpers.py`, not the shared layer.

## Field specs (for `validate_fields`)

```
JOB_DESCRIPTION_FIELDS = {
    "title":   (REQUIRED, str_length(1, 200)),
    "company": (None,     str_length(1, 200)),
    "text":    (REQUIRED, str_length(1, 20000)),
}

SUGGESTION_FIELDS = {
    "resumeText":        (REQUIRED, str_length(1, 20000)),
    "jobDescription":    (REQUIRED, job_description),
    "supportingContext": (None,     str_length(1, 2000)),
}
```

Any other field, at either level, is rejected with `Unknown fields: ...`. An optional field sent as `null` is rejected too, because `str_length` only accepts strings. Leave the field out instead.

## Clients

### `bedrock`
`boto3.client("bedrock-runtime", config=Config(read_timeout=25, connect_timeout=5, retries={"total_max_attempts": 1}))`

| Setting | Why |
|---|---|
| `read_timeout=25` | Gives up before the Lambda's 28 s timeout and API Gateway's 29 s, so the route can return its own `504`. See [README → Time limits](README.md#time-limits) |
| `retries={"total_max_attempts": 1}` | No retries. boto3 retries throttling by default, and one retry of a 20-second call blows the 29-second budget. The client retries instead, on `503` and `504` |

No `endpoint_url`: there's no local Bedrock.

## Functions

### `prompt_variables(fields) → dict`
Builds the `promptVariables` for `converse` from the output of `validate_fields(body, SUGGESTION_FIELDS, ...)`:

```
{name: {"text": build(fields)} for name, build in PROMPT_VARIABLES.items()}
```

Every variable is always sent, with `""` for a missing optional field. Bedrock rejects a call that leaves out a variable the prompt uses.

### `call_bedrock(variables) → dict`
The only AWS call in the pipeline. Returns the raw `converse` response.

```
bedrock.converse(
    modelId=PROMPT_ARN,
    promptVariables=variables,
    guardrailConfig={"guardrailIdentifier": GUARDRAIL_ID, "guardrailVersion": GUARDRAIL_VERSION},
)
```

| Param | Why |
|---|---|
| `modelId` | A prompt **version** ARN in place of a model ID. Bedrock loads the prompt's model, system prompt and settings from the console |
| `promptVariables` | Fills the prompt's `{{variables}}` |
| `guardrailConfig` | The guardrail isn't part of the prompt, so every call names it |

Don't pass `system`, `inferenceConfig` or `additionalModelRequestFields`: they come from the prompt, and Bedrock rejects them with a prompt ARN. Let `ClientError` and `ReadTimeoutError` propagate to the route.

### `was_blocked(response) → bool`
`response["stopReason"] in BLOCKED_STOP_REASONS`. When it's `True`, the reply text is the guardrail's canned message, not JSON, so check this before `parse_reply`.

### `parse_reply(response) → dict | None`
1. Join the `text` of every block in `response["output"]["message"]["content"]`.
2. Trim it, and strip a surrounding Markdown code fence (` ```json ... ``` `) if there is one. Models sometimes add one even when told not to.
3. `json.loads` it. `ValueError` → `None`.
4. Not a `dict` (e.g. a list or a string) → `None`. Otherwise return it unchanged.

`None` means the route returns `502`. It doesn't check the shape inside the object; that's the console prompt's job.

---

New to a term? See the [glossary](../general/glossary.md).
