# Local Testing

**Purpose:** Run and test endpoints on your machine (macOS, Linux, or Windows), without deploying.
**Tech:** Docker Compose (DynamoDB Local, s3mock), AWS SAM CLI (`sam local`), curl.
**Role in the project:** The standard loop for checking a Lambda before it's pushed. Setup comes first: [setup.md](setup.md).

All commands run from `backend/SAMproject`. Commands without an OS label are the same everywhere. On Windows, use PowerShell.

## Unit tests

The unit tests mock AWS services, so Docker, a running backend, and AWS credentials aren't required. Use Python 3.13 to match the Lambda runtime. From `backend/SAMproject`, create a virtual environment and install the test dependencies:

**macOS / Linux**
```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r tests/requirements.txt
.venv/bin/python -m pytest tests
```

**Windows (PowerShell)**
```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r tests/requirements.txt
.\.venv\Scripts\python.exe -m pytest tests
```

If `.venv` already exists, reuse it and skip the creation command. For later runs, only the pytest command is needed unless dependencies change. These commands use the virtual environment directly, so activation isn't required.

Run `tests` rather than only `tests/unit`: the delete-profile tests live directly in `tests/test_delete_user.py`. `pytest.ini` supplies the source import paths, so no manual `PYTHONPATH` setting or SAM build is needed.

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

## Shortcut

`dev.py` runs steps 1, 3 and 5 below for you: start Compose, build, and start the API.

| macOS / Linux | Windows |
|---|---|
| `python3 dev.py` | `python dev.py` |

Then go straight to calling the API in step 5. Ctrl+C stops everything. To pick up a code change, stop the script and run it again.

## Walkthrough

### 1. Start the backing services

```bash
docker compose up -d                  # start dynamodb, dynamodb-init, s3 in background
docker compose wait dynamodb-init     # wait for the seed step (exit code 0 = success)
docker compose ps -a                  # dynamodb + s3 "running", dynamodb-init "Exited (0)"
docker compose logs dynamodb-init     # should end with "seed complete"
```

### 2. (Optional) Check the data directly

Set dummy credentials for this terminal only, then query the local services.

**macOS / Linux**
```bash
export AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local AWS_DEFAULT_REGION=us-east-1
```

**Windows (PowerShell)**
```powershell
$env:AWS_ACCESS_KEY_ID="local"; $env:AWS_SECRET_ACCESS_KEY="local"; $env:AWS_DEFAULT_REGION="us-east-1"
```

**Both**
```bash
aws dynamodb scan --table-name MatchobUsers --endpoint-url http://localhost:8000   # list seeded users
aws s3 ls --endpoint-url http://localhost:9090                                     # list buckets
```

### 3. Build

```bash
sam build                             # needs Python 3.13
sam build --use-container             # use this instead if you don't have Python 3.13
```

**Rerun after ANY code or template change.** Without a build, `sam local` runs the raw source code. The shared layer (`matchob_common`) is then missing, and every request returns `Internal server error`.

### 4. Invoke one function with an event file (no HTTP)

```bash
sam local invoke GetProfileFunction -e events/get-profile.json --env-vars env.json --docker-network matchob-local
```

| Flag | Purpose |
|---|---|
| `-e` | The event passed to the handler (already has `claims.sub = "12345"`) |
| `--env-vars` | Apply `env.json` |
| `--docker-network` | Join the Compose network so `dynamodb` resolves |

Expect `"statusCode": 200` with Sarah's profile.

### 5. Run the API and call it

Terminal 1:
```bash
sam local start-api --port 3001 --env-vars env.json --docker-network matchob-local   # port 3000 is the frontend's
```

It's ready when you see `Running on http://127.0.0.1:3001`.

Terminal 2, **macOS / Linux**:
```bash
curl -i -H "X-Local-User: 12345" http://localhost:3001/profile   # 200: Sarah
curl -i -H "X-Local-User: 99999" http://localhost:3001/profile   # 404: no profile for that user
curl -i http://localhost:3001/profile                            # 401: no user
curl -i -X PUT http://localhost:3001/profile \
  -H "X-Local-User: 12345" \
  -H "Content-Type: application/json" \
  -d '{"name": "Sarah B"}'                                       # JSON body example (no PUT route exists yet)
```

Terminal 2, **Windows (PowerShell)**:
```powershell
curl.exe -i -H "X-Local-User: 12345" http://localhost:3001/profile   # 200: Sarah
curl.exe -i -H "X-Local-User: 99999" http://localhost:3001/profile   # 404: no profile for that user
curl.exe -i http://localhost:3001/profile                            # 401: no user
Invoke-RestMethod -Method Put -Uri http://localhost:3001/profile `
  -Headers @{ "X-Local-User" = "12345" } `
  -ContentType "application/json" `
  -Body '{"name": "Sarah B"}'                                        # JSON body example (no PUT route exists yet)
```

Windows notes:
- Type `curl.exe`, not `curl`. In PowerShell, `curl` is an alias for `Invoke-WebRequest`, which takes different arguments.
- For JSON bodies, use `Invoke-RestMethod` as shown. Older PowerShell versions strip the quotes from `curl.exe -d '{...}'`, which breaks the JSON.
- Postman works the same on every OS.

`X-Local-User` takes the place of a Cognito login locally. See [auth.md](auth.md). The "authorizer skipped" warning in terminal 1 is expected.

### 6. Stop

Press Ctrl+C in terminal 1, then:
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

Check terminal 1 (the `sam local` output) first. The handler prints `DYNAMODB_ENDPOINT:` on every request, and any traceback appears there.

| Symptom | Fix |
|---|---|
| `{"message":"Internal server error"}` (502) and `No module named 'matchob_common'` | You didn't run `sam build`, or it failed. Run it again, then restart `start-api`. |
| `{"error": "Internal server error"}` (500) and a blank `DYNAMODB_ENDPOINT:` | `env.json` is missing or you left out `--env-vars env.json`. |
| Request hangs, then 502, or `Could not connect to the endpoint URL: http://dynamodb:8000` | Compose isn't running, or you left out `--docker-network matchob-local`. |
| `ResourceNotFoundException` | `USERS_TABLE` is missing from `env.json`, or the seed step didn't run (`docker compose logs dynamodb-init`). |
| A code change doesn't show up | Run `sam build` again, then restart `start-api`. |
| 401 even with `X-Local-User` | The function doesn't use `get_user_id`, or the request isn't going through `sam local`. |
| `NoSuchBucket` | Bucket name in `.env` / `UPLOAD_BUCKET` doesn't match. Run `docker compose up -d` to recreate s3. |
| Windows: `curl` errors about `-H` or `-i` | Use `curl.exe` (see step 5). |

---

New to a term? See the [glossary](glossary.md).
