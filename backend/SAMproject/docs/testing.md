# Local Testing

**Purpose:** Run and test endpoints on your machine, without deploying.
**Tech:** Docker Compose (DynamoDB Local, s3mock), AWS SAM CLI (`sam local`), curl.
**Role in the project:** The standard loop for checking a Lambda before it's pushed. Setup comes first: [setup.md](setup.md).

## How the pieces connect

```
sam local (Lambda containers) ──┐
                                ├── Docker network: matchob-local
docker compose ─────────────────┘
  ├── dynamodb       localhost:8000   (in containers: http://dynamodb:8000)
  ├── dynamodb-init  runs once: creates MatchobUsers table + loads docker/seed/users.json
  └── s3             localhost:9090   (in containers: http://s3:9090)
Bedrock → real AWS (no local emulator)
```

Data is in memory: every `docker compose up` starts from the same seed data.

## Walkthrough

### 1. Start the backing services

```bash
docker compose up -d                  # start dynamodb, dynamodb-init, s3 in background
docker compose ps -a                  # dynamodb + s3 "running", dynamodb-init "Exited (0)"
docker compose logs dynamodb-init     # should end with "seed complete"
```

### 2. (Optional) Check the data directly

```bash
export AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local AWS_DEFAULT_REGION=us-east-1  # dummy creds for this terminal only
aws dynamodb scan --table-name MatchobUsers --endpoint-url http://localhost:8000          # list seeded users
aws s3 ls --endpoint-url http://localhost:9090                                            # list buckets
```

### 3. Build

```bash
sam build                             # rerun after ANY code or template change
```

### 4. Invoke one function with an event file (no HTTP)

```bash
sam local invoke GetProfileFunction \
  -e events/get-profile.json \
  --env-vars env.json \
  --docker-network matchob-local
# -e:               the event passed to the handler (already has claims.sub = "12345")
# --env-vars:       apply env.json
# --docker-network: join the Compose network so "dynamodb" resolves
```

Expect `"statusCode": 200` with Sarah's profile.

### 5. Run the API and call it with curl

Terminal 1:
```bash
sam local start-api --port 3001 --env-vars env.json --docker-network matchob-local  # port 3000 is the frontend's
```

Terminal 2:
```bash
curl -i -H "X-Local-User: 12345" http://localhost:3001/profile   # 200: Sarah
curl -i -H "X-Local-User: 99999" http://localhost:3001/profile   # 404: no profile for that user
curl -i http://localhost:3001/profile                            # 401: no user
curl -i -X PUT http://localhost:3001/profile \
  -H "X-Local-User: 12345" \
  -H "Content-Type: application/json" \
  -d '{"name": "Sarah B"}'                                       # JSON body example (no PUT route exists yet)
```

`X-Local-User` takes the place of a Cognito login locally. See [auth.md](auth.md). The "authorizer skipped" warning in terminal 1 is expected.

### 6. Stop

```bash
docker compose down                   # stop + remove containers (data is discarded)
```

## Common tasks

```bash
docker compose run --rm dynamodb-init            # re-seed after editing docker/seed/users.json
docker compose logs -f s3                        # follow one service's logs
docker compose up -d --remove-orphans            # after renaming/removing a service
docker compose config                            # show compose.yaml with variables filled in
```

- **Seed data** goes in `docker/seed/users.json`, in DynamoDB JSON format (`{"S": "..."}`, `{"N": "21"}`). Every top-level key is a table name, so don't add comment keys.
- **New function:** add `events/<name>.json` with `requestContext.authorizer.claims.sub` set, so it works with `sam local invoke`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| curl returns `502 Internal server error` | The Lambda crashed. Read the Python traceback in terminal 1. |
| `Could not connect to the endpoint URL: http://dynamodb:8000` | Compose isn't running, or `--docker-network matchob-local` is missing. |
| `ResourceNotFoundException` | `USERS_TABLE` is missing from `env.json`, or the seed step didn't run. |
| `ModuleNotFoundError: matchob_common` | Run `sam build`. Check `.aws-sam/build/SharedLayer/python/` exists. |
| A code change doesn't show up | Run `sam build` again, then restart `start-api`. |
| 401 even with `X-Local-User` | Function doesn't use `get_user_id`, or the request isn't going through `sam local`. |
| `NoSuchBucket` | Bucket name in `.env` / `UPLOAD_BUCKET` doesn't match. Run `docker compose up -d` to recreate s3. |
