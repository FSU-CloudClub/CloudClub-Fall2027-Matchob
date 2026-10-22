# Meeting Notes
This document will hold the notes from each of our meetings.

## Meeting 1
*Date: 10/13/2026*
### Agenda
1. Review (see below)
2. Code and Docs Tour (look through repo)
3. Attempted to set up local env (run `dev.py`)
### Architecture Review 
- Lambda: serverless compute
- DynamoDB: metadata
- S3: resumes
- Bedrock: AI access
```mermaid
flowchart LR
    Client([Client])

    subgraph APIGW["API Gateway"]
        Auth["Authorizer"]
    end

    LS["Lambda: S3"]
    LD["Lambda: DynamoDB"]
    LB["Lambda: Bedrock"]

    S3[("S3<br/>Resumes")]
    DDB[("DynamoDB<br/>User Metadata")]
    BR["Bedrock<br/>AI Models"]

    Client -->|"1. API request"| APIGW
    Auth -->|"2. Authorized"| LS
    Auth -->|"2. Authorized"| LD
    Auth -->|"2. Authorized"| LB

    LS <--> S3
    LD <--> DDB
    LB <--> BR

    LS -.->|"3. Lambda response"| APIGW
    LD -.->|"3. Lambda response"| APIGW
    LB -.->|"3. Lambda response"| APIGW
    APIGW -.->|"4. HTTP response"| Client
```

### SAM Framework
- handle local testing
- handle deployment 
- Libraries: `boto3` (for accessing resources/services), `lambdaPowertools` (organize lambda functions)

### Local Dev Environment 
- SAM will set up a backend "server" to simulate lambdas
- Docker for local testing
- Docker container for DynamoDB and S3 (Bedrock is AI and can not be simulated)
- Everything runs in docker containers
```mermaid
flowchart TB
    Dev([Developer<br/>curl / Postman / Frontend])

    subgraph NET["Docker Network: SAM network"]
        direction TB

        API["sam local start-api<br/>(Lambda functions run in containers)"]

        DDB[("DynamoDB Local<br/>container")]
        S3[("S3 emulator<br/>container")]

        Seed["Temporary seed container<br/>starts, connects to DynamoDB,<br/>inserts seed data, then exits"]
    end

    Dev -->|"localhost port"| API
    API --> DDB
    API --> S3
    Seed -->|"seed data"| DDB
```
*P.S. I made a file called dev.py and it sets up the local environment and runs one test. Run the python file and the docker containers + sam lambda simulation should be running. - Carter*

## Meeting 2
**Date: 10/15/2026**
### Endpoint Assignment
- Creating a user (post) - Tommy
- Editing a user (put) - Cooper
- Deleting a user - Santiago 
- Getting a user core metadata - Schneider
- Get user profile (get) - Carter

### HTTP Request Types
- Get: to get data
- Put: to place new rows
- Delete: to delete rows
- Patch: partial update 
- Put: full update
## Meeting 3
**Date: 10/22/2026**

> **PRs are due this Sunday, 10/25/2026.** One PR per person, against `main`. Before starting, pull `main` once the `backend-refactor` PR (nested stacks + new docs) is merged, and branch from it.

### Backend refactor (Carter)
- **Nested stacks:** `template.yaml` now only wires together one template per service in `templates/` (shared Cognito, profile, resumes, Bedrock), so people working on different services don't edit the same file. See [nested-stacks.md](general/nested-stacks.md).
- **API contracts:** [api-contracts.md](general/api-contracts.md) defines the request and response for every profile and resume endpoint, matching the frontend's `ResumeApi` and types.
- **Profile endpoints rebuilt:** all four `/profile` routes use the new profile fields, validate per field, return proper 404s, and send numbers as numbers.
- **Shared helpers:** request parsing, the JSON serializer and field validation moved to the shared layer (`matchob_common`), so every Lambda can reuse them. See [shared-helpers.md](general/shared-helpers.md).
- **Resumes and Bedrock stacks:** the S3 bucket, resumes API with all 5 routes, and both Lambda handlers are set up and ready for endpoints.
- **Docs:** reorganized into `general/` and one folder per pipeline, with a doc for every endpoint, a [glossary](general/glossary.md) and a [Git workflow](general/git-workflow.md) reference.

### Assignments
Each numbered person owns every task in their rows, so nobody waits on a teammate mid-task. Fill in names:

| Person | Name |
|---|---|
| Person 1 | ______ |
| Person 2 | ______ |
| Person 3 | ______ |
| Person 4 | ______ |
| Person 5 | ______ |
| Person 6 | ______ |

Persons 2–4 use helpers that Person 1 writes. Person 1: open a draft PR with `resume_helpers.py` early (by Friday) so the others can build on it. Until then, code against the signatures in [helpers.md](s3-pipeline/helpers.md).

### Tasks

| # | Task | Person | Depends on | Doc |
|---|---|---|---|---|
| 1 | Add `S3_PUBLIC_ENDPOINT` to `s3-template.yaml`, `env.json` and `env.example.json` | Person 1 | | [s3-pipeline/README.md → Setup tasks](s3-pipeline/README.md#setup-tasks-do-once-before-the-endpoints) |
| 2 | Update the seed user in `docker/seed/users.json` to the new profile fields, with an empty `resumes` map | Person 1 | | [s3-pipeline/README.md → Setup tasks](s3-pipeline/README.md#setup-tasks-do-once-before-the-endpoints) |
| 3 | Add the `str_length` validator to `matchob_common/validators.py` | Person 1 | | [s3-pipeline/helpers.md → Validators](s3-pipeline/helpers.md#validators) |
| 4 | Create `resume_helpers.py`: constants, `UPLOAD_FIELDS`, `presign_client`, `s3_key`, `now_iso`, `presign_upload`, `resume_path_names` | Person 1 | 1, 3 | [s3-pipeline/helpers.md](s3-pipeline/helpers.md) |
| 5 | `POST /resumes/upload-url` | Person 1 | 1, 2, 4 | [create-upload-url.md](s3-pipeline/endpoints/create-upload-url.md) |
| 6 | Add `get_resumes`, `presign_download` and `to_resume_object` to `resume_helpers.py` | Person 2 | 4 | [s3-pipeline/helpers.md → Functions](s3-pipeline/helpers.md#functions) |
| 7 | `GET /resumes` | Person 2 | 5, 6 | [list-resumes.md](s3-pipeline/endpoints/list-resumes.md) |
| 8 | `GET /resumes/{resumeId}/download-url` | Person 2 | 5, 6 | [create-download-url.md](s3-pipeline/endpoints/create-download-url.md) |
| 9 | Add `tag_list` and `RESUME_FIELDS` to `resume_helpers.py` | Person 3 | 3, 4 | [s3-pipeline/helpers.md → Validators](s3-pipeline/helpers.md#validators) |
| 10 | `PATCH /resumes/{resumeId}` | Person 3 | 5, 6, 9 | [update-resume.md](s3-pipeline/endpoints/update-resume.md) |
| 11 | `DELETE /resumes/{resumeId}` | Person 4 | 4, 5 | [delete-resume.md](s3-pipeline/endpoints/delete-resume.md) |
| 12 | ~~Delete the leftover `tests/unit/test_handler.py`~~ Done in the refactor | | | |
| 13 | Rewrite `tests/unit/test_create_user.py` for the new profile fields | Person 5 | | [post-profile.md](dynamodb-pipeline/endpoints/post-profile.md) |
| 14 | Add unit tests for `GET`, `PUT` and `DELETE /profile` | Person 5 | | [dynamodb-pipeline/README.md](dynamodb-pipeline/README.md) and each endpoint doc |
| 15 | Propose how `DELETE /profile` cleans up resume files in S3, for the team to decide | Person 6 | | [delete-profile.md → Gap](dynamodb-pipeline/endpoints/delete-profile.md#gap-resume-files-are-left-in-s3) |
| 16 | Draft the AI (Bedrock) endpoint contracts with the frontend team, using the frontend's `JobDescription` and `Recommendation` types | Person 6 | | [api-contracts.md](general/api-contracts.md), [nested-stacks.md](general/nested-stacks.md) |

**"Depends on"** lists task numbers. A task in another person's rows means: wait for that PR, or build against its documented signature.

### Git workflow to reduce conflicts
Full reference: [git-workflow.md](general/git-workflow.md).
- **One branch per person,** named `<name>/<task>`, created from the latest `main`. Never commit to `main`.
- **Stay in your own files.** Don't reformat or rename code outside your tasks.
- **In shared files** (`resume_helpers.py`, `validators.py`, `env.example.json`, templates), add new code at the end of the section and don't move existing lines.
- **Merge `origin/main` into your branch every day** (`git fetch` then `git merge origin/main`), so conflicts stay small.
- **When resolving a conflict, read the result** before committing. "Accept Both" in YAML often leaves broken templates, so run `sam validate --lint` after.
- **Post in the group chat** before changing anything shared, like a helper's signature, a template or the contract.

### Before opening your PR
- `sam validate --lint` and `sam build` pass.
- Every "Done when" check in your endpoint doc passes against `python dev.py`.
- Change your endpoint's **Status** in its doc and in the pipeline README's endpoint table to "Done".
