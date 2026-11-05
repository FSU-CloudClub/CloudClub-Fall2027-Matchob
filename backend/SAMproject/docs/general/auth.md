# Auth in Lambdas

**Purpose:** How a Lambda learns who is calling it, in production and locally.
**Tech:** Amazon Cognito, API Gateway Cognito authorizer, shared `get_user_id` helper (`src/shared/matchob_common/auth.py`, shipped as a Lambda layer).
**Role in the project:** Every protected endpoint calls one function to get the user ID, so auth works the same in every Lambda and local testing doesn't need real logins. The frontend/backend token rules are in [api-contracts.md](api-contracts.md).

## Production (AWS)

1. The frontend sends `Authorization: Bearer <token>` from Cognito.
2. **API Gateway** validates the token with the Cognito authorizer before the Lambda runs. Invalid or missing tokens get a 401 from API Gateway, and the Lambda never runs.
3. On success, API Gateway puts the token's claims into the event at `requestContext.authorizer.claims`.
4. The Lambda calls `get_user_id(event)`, which returns `claims.sub`, the Cognito user ID. That value is the DynamoDB `userId` and the S3 key prefix.

The Lambda never checks tokens itself. API Gateway already did.

## Local (`sam local`)

`sam local start-api` **skips** Cognito authorizers, so events arrive with no claims. To fill that gap, `get_user_id` also accepts an `X-Local-User` header, but **only** when the environment variable `AWS_SAM_LOCAL=true` is set:

- The SAM CLI sets `AWS_SAM_LOCAL` automatically inside its local containers.
- AWS never sets it, so the header is ignored in production.
- Real claims are always checked first. An event file with `claims.sub` (`sam local invoke -e ...`) works without the header.

## Rules

- **Always** get the user from `get_user_id(event)`. Never read a user ID from the body, query string, or path.
- **Never** add `AWS_SAM_LOCAL` to `template.yaml`, `env.json`, or any deployed config. Doing so would let anyone choose their user ID in production.
- `None` from `get_user_id` means return `{"error": "Unauthorized"}` with status 401.
- Shared helpers like this live in `src/shared/matchob_common/`. Change them in one place. Every function gets the update after the next `sam build`.

---

New to a term? See the [glossary](glossary.md).
