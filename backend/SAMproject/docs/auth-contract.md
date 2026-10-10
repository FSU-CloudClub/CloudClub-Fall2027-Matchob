# Matchob — Frontend/Backend Authentication Contract

**Status:** Proposed — pending team agreement and AWS integration testing

## Architecture

- Authentication provider: Amazon Cognito User Pools
- Login method: Cognito managed login
- OAuth flow: Authorization Code with PKCE
- Backend: AWS API Gateway REST API + Python Lambda
- Database: Amazon DynamoDB
- User identifier: Cognito `sub` claim

## Frontend responsibilities

1. Redirect users to Cognito for signup and login.
2. Handle the OAuth callback at `/auth/callback`.
3. Exchange authorization codes for tokens using PKCE.
4. Manage authentication sessions and token expiration securely.
5. Attach the agreed authentication token to protected API requests.
6. Redirect unauthenticated users to login when appropriate.

The frontend must not send a user ID to select which user's profile to retrieve.

## Backend responsibilities

1. Configure Cognito User Pool and App Client using AWS SAM.
2. Configure API Gateway with a Cognito authorizer.
3. Require valid authentication for protected endpoints.
4. Extract the verified Cognito `sub` claim in Lambda.
5. Use `sub` as the DynamoDB `userId` partition key.
6. Return consistent JSON responses and HTTP status codes.

## Protected endpoint: GET /profile

**Request**

```http
GET /dev/profile
Authorization: Bearer <TOKEN>
```

No request body or user ID is required.

**Successful response — 200**

```json
{
  "userId": "example-cognito-sub",
  "name": "Sarah",
  "education": "Florida State University"
}
```

**Profile not found — 404**

```json
{
  "error": "Profile not found"
}
```

**Unauthorized — 401**

```json
{
  "error": "Unauthorized"
}
```

An authentication failure may be returned directly by API Gateway rather than Lambda.

**Server error — 500**

```json
{
  "error": "Internal server error"
}
```

## Configuration values

| Variable | Purpose |
|---|---|
| `AWS_REGION` | Region hosting Cognito and API Gateway |
| `COGNITO_USER_POOL_ID` | Cognito User Pool identifier |
| `COGNITO_CLIENT_ID` | Public frontend application client |
| `COGNITO_DOMAIN` | Hosted Cognito login domain |
| `API_BASE_URL` | Base URL for backend requests |

These values will be available after deployment. No client secret is used for the public frontend client.

## Authentication token decision

**Proposed:** Use Cognito access tokens for protected API requests, with an API Gateway method authorization scope configured.

The backend must define the accepted OAuth scope, add it to the Cognito App Client configuration, and enforce it on protected API methods.

Until that configuration is complete, the frontend should not assume access tokens will work with the current REST API authorizer.

## Security rules

- Never put tokens in URL query parameters or logs.
- Never trust a client-provided `userId` for account ownership.
- Never expose AWS access keys in frontend code.
- Use HTTPS outside local development.
- Configure CORS for the approved frontend origin.
- Handle expired sessions and logout securely.

## Decisions to confirm with the team

- Actual frontend framework and authentication library
- Local and production callback URLs
- OAuth authorization scopes
- Token/session storage strategy
- Profile creation when a user first signs up
- Production frontend origin for CORS
