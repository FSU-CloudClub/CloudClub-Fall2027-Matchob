# Integration Next Steps

Steps to connect the frontend to the deployed AWS backend (stack `univ-proj-backend`, `us-east-1`, profile `univ-dev`).

## 1. Prerequisites (AWS console / CLI)

- [ ] **Refresh SSO:** run `aws sso login --profile univ-dev`.
- [ ] **Get the stack outputs:** `UserPoolId`, `UserPoolClientId`, `ProfileApiUrl`, `ResumesApiUrl`, `SuggestionsApiUrl`.
  ```sh
  aws cloudformation describe-stacks --stack-name univ-proj-backend \
    --profile univ-dev --region us-east-1 --query 'Stacks[0].Outputs'
  ```
- [ ] **Bedrock prompt:** create it in the console and copy its versioned **Prompt ARN** (`arn:aws:bedrock:us-east-1:<account>:prompt/<id>:<version>`).
- [ ] **Bedrock guardrail:** create it and copy the **Guardrail ID** and **Guardrail Version**.
- [ ] **Model ARNs:** copy the **model / inference profile ARNs** the prompt uses. With cross-region inference, include the destination model ARNs.
- [ ] **Model access:** enable access to that model in Bedrock → Model access.
- [ ] **Bucket name:** copy the existing uploads bucket name (`matchob-resumes-<uuid>`) from S3 or the nested stack outputs.
- [ ] **Extension ID:** load the unpacked extension and copy its ID from `chrome://extensions`. It's needed for the Cognito callback URL.
- [ ] **Test user:** create one in Cognito → User pools → `matchob-dev-users`.

## 2. Backend code edits

- [ ] **Fill in `samconfig.toml`:** set `parameter_overrides` to:
  ```
  PromptArn=<arn> GuardrailId=<id> GuardrailVersion=<ver> BedrockModelResourceArns=<arn1,arn2> UploadBucketName=<bucket>
  ```
  `BedrockModelResourceArns` is required and currently missing.
- [ ] **Remove the duplicate keys in `samconfig.toml`:** `stack_name` and `region` are each set in two places, and the commented-out `parameter_overrides` line can go.
- [ ] **Fix the Cognito callback URLs:** in `templates/shared-template.yaml`, add `https://<extension-id>.chromiumapp.org/` to `CallbackURLs` and `LogoutURLs`.
- [ ] **(Optional) Add CORS to the APIs:** add a `Cors` block to each `AWS::Serverless::Api` if you'll call them from content scripts or a web page. Extension pages don't need it.
- [ ] **(Optional) Restrict bucket CORS:** limit `AllowedOrigins` on the uploads bucket to `chrome-extension://<extension-id>`.
- [ ] **Deploy and check:** run `sam build && sam deploy`, then confirm the stack outputs are unchanged.

## 3. Frontend code edits

- [ ] **Add env vars** in `frontend/.env`: `WXT_RESUMES_API_URL`, `WXT_PROFILE_API_URL`, `WXT_SUGGESTIONS_API_URL`, `WXT_COGNITO_USER_POOL_ID`, `WXT_COGNITO_CLIENT_ID`, `WXT_COGNITO_DOMAIN` (`matchob-dev-backend.auth.us-east-1.amazoncognito.com`), `WXT_AWS_REGION`.
- [ ] **Allow AWS hosts:** in `wxt.config.ts`, add these to `host_permissions`:
  - `https://*.execute-api.us-east-1.amazonaws.com/*`
  - `https://*.s3.amazonaws.com/*`
  - `https://*.amazoncognito.com/*`
- [ ] **Add the `identity` permission** to the manifest (for `chrome.identity.launchWebAuthFlow`).
- [ ] **Add an auth service** (`services/auth.ts`). It should:
  - sign users in with the Cognito hosted UI (authorization code flow, PKCE)
  - store the tokens
  - refresh them before they expire
  - expose `getIdToken()`
- [ ] **Update `services/resumeApi.ts`:**
  - Remove the localhost-only guard.
  - Send `Authorization: <ID token>` to remote URLs, and keep `X-Local-User` only for localhost.
  - Read the base URL from `WXT_RESUMES_API_URL`.
- [ ] **Handle `401`:** clear the stored tokens and send the user back to sign-in.
- [ ] **Update error messages:** remove the "local backend" and "local S3" wording in `resumeApi.ts` and `uploadResume.ts`.
- [ ] **Add profile and suggestions clients** pointed at their own API URLs. Each service has a separate API Gateway.
- [ ] **Route new users to profile creation:** when `GET /profile` returns `404`, send the user to create a profile. The resume endpoints also return `404` until one exists.
- [ ] **Smoke test:** sign in → create profile → upload → list → rename/tag → download → delete.
