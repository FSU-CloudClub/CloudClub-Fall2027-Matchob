# Suggestions Pipeline (Bedrock)

**Purpose:** Suggest how the user should tailor their resume to one job application.
**Tech:** Python 3.13, Powertools, boto3 Bedrock Runtime client (`converse`).
**Role in the project:** The frontend sends the parsed resume text and the job description. This Lambda passes them to a prompt that's set up in the Bedrock console and returns the model's JSON unchanged. It doesn't read or write DynamoDB or S3, and nothing is saved.

| | |
|---|---|
| Template | `templates/bedrock-template.yaml` (`BedrockStack` in the root) |
| Code | `src/bedrock-pipeline/app.py`, `src/bedrock-pipeline/bedrock_helpers.py` |
| Contract | [api-contracts.md → Suggestions](../general/api-contracts.md#suggestions) |
| Helpers | [helpers.md](helpers.md) and [shared-helpers.md](../general/shared-helpers.md) |

## Endpoints

| Endpoint | Function | Doc |
|---|---|---|
| `POST /suggestions` | `create_suggestions()` | [create-suggestions.md](endpoints/create-suggestions.md) |

Suggested order: `create-suggestions` with its route tests → fill in the IDs → deploy.

## What we own and what the console owns

The model, system prompt, output format and guardrail rules are set up in the Bedrock console by the team that owns the model. We don't change them. Before the first deploy, get these from them:

| From the console | Example | Goes in |
|---|---|---|
| Prompt **version** ARN | `arn:aws:bedrock:us-east-1:123456789012:prompt/ABC123XYZ:1` | `PromptArn` parameter → `PROMPT_ARN` |
| Guardrail ID | `gr1a2b3c4d5e` | `GuardrailId` parameter → `GUARDRAIL_ID` |
| Guardrail version | `1` | `GuardrailVersion` parameter → `GUARDRAIL_VERSION` |

And tell them two things the prompt must match, because the code and the frontend depend on them:

1. **Variable names.** The prompt must use exactly the `{{variables}}` in [`PROMPT_VARIABLES`](helpers.md#constants).
2. **Output format.** The prompt must return the JSON in [api-contracts.md → POST /suggestions](../general/api-contracts.md#post-suggestions), with no text around it.

## Setup tasks (do once, before the endpoint)

All done. Kept here so you know what's already in place.

1. ~~**Create `bedrock_helpers.py`.**~~ Done: everything in [helpers.md](helpers.md) is in `src/bedrock-pipeline/bedrock_helpers.py`, tested by `tests/unit/test_bedrock_helpers.py`.
2. ~~**Clean up `app.py`.**~~ Done: the leftover DynamoDB resource, `table` and `MODEL_ID` are gone. It imports everything the route needs and uses `APIGatewayRestResolver(serializer=to_json)` like the other pipelines.
3. ~~**Update `templates/bedrock-template.yaml`.**~~ Done: see [Infrastructure](#infrastructure).
4. ~~**Update the root `template.yaml`.**~~ Done: root parameters `PromptArn`, `GuardrailId` and `GuardrailVersion` are passed to `BedrockStack` with `UserPoolArn`, and `SuggestionsApiUrl` is a root output. See [nested-stacks.md](../general/nested-stacks.md#how-values-move-between-stacks).
5. ~~**Add the values' placeholders.**~~ Done: `samconfig.toml` has a commented-out `parameter_overrides` line under `[default.deploy.parameters]`, and `env.example.json` has `PROMPT_ARN`, `GUARDRAIL_ID` and `GUARDRAIL_VERSION` as `""`. If your `env.json` predates these, copy them from `env.example.json` (`dev.py` only creates `env.json` when it's missing).

**Before the first deploy:** get the three IDs from the console owner and uncomment `parameter_overrides` in `samconfig.toml`. The root parameters have no defaults, so `sam deploy` refuses to run without them.

## Infrastructure

Everything is in `templates/bedrock-template.yaml`. The `CreateSuggestions` route is declared, so until `create_suggestions()` exists in `app.py`, the path returns Powertools' `404 Not found`.

| Resource | What it is |
|---|---|
| `BedrockApi` | API Gateway, stage `dev`, Cognito authorizer from the `UserPoolArn` parameter |
| `BedrockFunction` | The Lambda. One `Api` event, `CreateSuggestions`: `POST /suggestions` |
| `SharedLayer` | This stack's copy of `src/shared` |

| Parameter | From |
|---|---|
| `UserPoolArn` | `SharedStack.Outputs.UserPoolArn` |
| `PromptArn`, `GuardrailId`, `GuardrailVersion` | Root parameters, set in `samconfig.toml` |

| Environment variable | AWS | Local (`env.json`) |
|---|---|---|
| `PROMPT_ARN` | `!Ref PromptArn` | `""`, or the real ARN for the [smoke test](endpoints/create-suggestions.md#done-when) |
| `GUARDRAIL_ID` | `!Ref GuardrailId` | Same |
| `GUARDRAIL_VERSION` | `!Ref GuardrailVersion` | Same |

**Policy:**

```yaml
      Policies:
        - Statement:
            - Effect: Allow
              Action:
                - bedrock:RenderPrompt
                - bedrock:InvokeModel
                - bedrock:ApplyGuardrail
              Resource: "*"
```

`RenderPrompt` reads the console prompt, `InvokeModel` runs its model and `ApplyGuardrail` runs the guardrail. `"*"` keeps it simple, because the prompt's model can change in the console without a redeploy. If a deployed call fails with `AccessDeniedException`, the log names the missing action.

### Time limits

API Gateway ends every request after 29 seconds. Each limit sits inside the one above it, so the backend, not API Gateway, decides what the client sees:

| Limit | Value | What happens |
|---|---|---|
| boto3 `read_timeout` | 25 s | `ReadTimeoutError` → the route returns `504` as `{ "error": ... }` |
| Lambda `Timeout` | 28 s | The Lambda is killed. API Gateway returns `502` |
| API Gateway | 29 s | API Gateway returns `504` with `{ "message": "Endpoint request timed out" }` |

If real calls come close to 25 seconds, ask the console owner to lower the prompt's max tokens or use a faster model before changing any of these.

## Objects at the top of `app.py`

| Object | What it is |
|---|---|
| `logger` | Powertools `Logger`, service `bedrock` |
| `app` | `APIGatewayRestResolver(serializer=to_json)` |

The Bedrock client and the IDs live in `bedrock_helpers.py`. `app.py` only calls `call_bedrock`, so tests mock one function.

## Every route follows the same shape

1. `get_user_id(app.current_event.raw_event)`. `None` → `401 Unauthorized`. The user ID isn't sent to Bedrock; it's only for auth and logs.
2. `read_json_body` then `validate_fields` with the route's spec. Failure → `400`.
3. One `call_bedrock(...)`. Bedrock errors map to `503`, `504` or `500`.
4. Check the reply: blocked → `422`, not a JSON object → `502`.
5. `logger.info("<what happened>", extra={"user_id": user_id})` and return.

Never log the resume or job text. It's personal data and can be 40,000 characters long.

## Local development

Bedrock has no local emulator, so `python dev.py` can start this Lambda but can't answer a `POST /suggestions` until `env.json` has real IDs. Development is unit-test first: every Bedrock call goes through `call_bedrock`, which the tests mock. See [create-suggestions.md → Done when](endpoints/create-suggestions.md#done-when).

## Known gaps

- **The response shape isn't checked.** The backend only checks that the reply is a JSON object. If the console prompt returns a different shape, the user gets `200` and the frontend breaks.
- **No rate limit per user.** Every call costs money. API Gateway usage plans can add one later.

---

New to a term? See the [glossary](../general/glossary.md).
