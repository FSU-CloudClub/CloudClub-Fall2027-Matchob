# Local Setup

**Purpose:** Get a fresh clone running the backend locally on macOS, Linux, or Windows.
**Tech:** Docker Compose, AWS SAM CLI, Python, env files (`.env`, `env.json`).
**Role in the project:** One-time setup, then one command to start everything. Testing details are in [testing.md](testing.md).

## Prerequisites

| Tool | Check with | Notes |
|---|---|---|
| Docker Desktop (running) | `docker compose version` | Compose v2.17+ (any recent Docker Desktop) |
| AWS SAM CLI | `sam --version` | |
| Python 3 | `python3 --version` (Mac/Linux), `python --version` (Windows) | Any 3.x runs `dev.py` |
| Python 3.13 (optional) | `python3.13 --version` (Mac/Linux), `py -3.13 --version` (Windows) | Without it, the build runs inside Docker (slower the first time) |
| AWS CLI v2 (optional) | `aws --version` | Only for inspecting data by hand |
| AWS credentials (only needed for Bedrock) | `aws configure list` | |

## Quick start (recommended)

Make sure Docker Desktop is open, then from the repo root:

**macOS / Linux**
```bash
cd backend/SAMproject
python3 dev.py
```

**Windows (PowerShell)**
```powershell
cd backend\SAMproject
python dev.py
```

The API is ready when you see `Running on http://127.0.0.1:3001`. Press **Ctrl+C** to stop the API and the containers. Run `dev.py --keep` to leave DynamoDB and S3 running after you stop.

### What `dev.py` does

1. Checks that `docker` and `sam` are installed and that Docker is running.
2. Creates `.env` and `env.json` from the `.example` files if they don't exist.
3. Restarts DynamoDB + S3 with Compose and waits for the seed data to load.
4. Runs `sam build`. If Python 3.13 isn't installed, it runs `sam build --use-container` instead.
5. Runs `sam local start-api --port 3001 --env-vars env.json --docker-network matchob-local`.

Every run rebuilds, so code changes are picked up when you restart the script.

## Manual steps

Use these if you'd rather run each piece yourself. All commands run from `backend/SAMproject`.

**1. Create the env files** (first time only)

| macOS / Linux | Windows (PowerShell) |
|---|---|
| `cp .env.example .env` | `Copy-Item .env.example .env` |
| `cp env.example.json env.json` | `Copy-Item env.example.json env.json` |

**2. Start DynamoDB + S3 and wait for the seed** (same on every OS)
```bash
docker compose up -d
docker compose wait dynamodb-init      # exits 0 when "seed complete"
```

**3. Build** (same on every OS)
```bash
sam build                              # needs Python 3.13
sam build --use-container              # use this instead if you don't have Python 3.13
```

**4. Start the API** (same on every OS)
```bash
sam local start-api --port 3001 --env-vars env.json --docker-network matchob-local
```

**5. Call it** (in a second terminal)

| macOS / Linux | Windows (PowerShell) |
|---|---|
| `curl -i -H "X-Local-User: 12345" http://localhost:3001/profile` | `curl.exe -i -H "X-Local-User: 12345" http://localhost:3001/profile` |

On Windows, type `curl.exe`, not `curl`. In PowerShell, `curl` is an alias for `Invoke-WebRequest`, which takes different arguments.

**6. Stop**
```bash
docker compose down
```

## What the env files are

| File | Read by | Holds | Committed? |
|---|---|---|---|
| `.env.example` → `.env` | Docker Compose | `${VARS}` used in `compose.yaml` | example only |
| `env.example.json` → `env.json` | `sam local --env-vars` | Lambda env var values for local runs | example only |

```jsonc
// comments for explanation only: real JSON files can't contain them
{
  "Parameters": {                                  // applies to every function
    "USERS_TABLE": "MatchobUsers",                 // real name (sam local can't resolve !Ref)
    "DYNAMODB_ENDPOINT": "http://dynamodb:8000",   // Compose service name + container port
    "S3_ENDPOINT": "http://s3:9090"                // same for S3
  }
}
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `{"message":"Internal server error"}` (502) and `No module named 'matchob_common'` in the sam terminal | You didn't run `sam build`, or it failed. Run it again (add `--use-container` without Python 3.13), then restart `start-api`. |
| `{"error": "Internal server error"}` (500) and a blank `DYNAMODB_ENDPOINT:` in the sam terminal | `env.json` is missing or you left out `--env-vars env.json`. The Lambda is trying to reach real AWS. |
| Request hangs, then 502 | You left out `--docker-network matchob-local`. |
| `Docker is installed but not running` | Open Docker Desktop and wait for it to finish starting. |
| `'sam' not found on PATH` | Install the SAM CLI, then open a new terminal. |
| `python3` not found (Windows) | Use `python` or `py`. |
| `unknown command: docker compose wait` | Update Docker Desktop. |
| Port 3001, 8000 or 9090 already in use | Stop whatever is using it, or change `DYNAMODB_PORT` / `S3_PORT` in `.env`. |

## Rules

- **Always build before `start-api`.** Without a build, `sam local` runs the raw source code, and the shared layer (`matchob_common`) is missing. `.aws-sam/` is gitignored, so a fresh clone has no build.
- **Adding a Lambda env var:** declare it in `template.yaml` under `Globals → Function → Environment` first. `sam local` ignores any variable in `env.json` that the template doesn't declare. Then add the local value to `env.example.json`.
- **Never** add `AWS_SAM_LOCAL` anywhere. See [auth.md](auth.md).
- `.env` and `env.json` are gitignored. Put shared defaults in the `.example` files.
