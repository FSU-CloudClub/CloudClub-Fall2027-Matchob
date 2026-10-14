# Local Setup

**Purpose:** Get a fresh clone ready to run the backend locally.
**Tech:** Docker Compose, AWS SAM CLI, env files (`.env`, `env.json`).
**Role in the project:** One-time setup before anything in [testing.md](testing.md) works.

## Prerequisites

| Tool | Check with |
|---|---|
| Docker Desktop (running) | `docker compose version` |
| AWS SAM CLI | `sam --version` |
| AWS CLI v2 | `aws --version` |
| Python 3.13 | `python3.13 --version` |
| AWS credentials (only needed for Bedrock) | `aws configure list` |

## Steps

```bash
cd backend/SAMproject                 # all commands run from here
cp .env.example .env                  # Compose variables (ports, bucket name)
cp env.example.json env.json          # Lambda env vars for sam local
docker compose up -d                  # start DynamoDB + S3 and seed test data
sam build                             # build functions + shared layer
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

## Rules

- **Adding a Lambda env var:** declare it in `template.yaml` under `Globals → Function → Environment` first. `sam local` ignores any variable in `env.json` that the template doesn't declare. Then add the local value to `env.example.json`.
- **Never** add `AWS_SAM_LOCAL` anywhere. See [auth.md](auth.md).
- `.env` and `env.json` are gitignored. Put shared defaults in the `.example` files.
