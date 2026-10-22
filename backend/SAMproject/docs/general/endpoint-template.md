# Endpoint Doc Template

**Purpose:** The format every endpoint doc in `docs/<pipeline>/endpoints/` follows.
**Role in the project:** One endpoint, one file, so each endpoint can be assigned to one person and docs don't cause merge conflicts. A dev should be able to build the endpoint from its doc alone.

Copy everything below the line into `docs/<pipeline>/endpoints/<endpoint-name>.md`.

**Rules**
- Describe the design: steps, function names, parameters, return values. Don't paste a full implementation, because it goes stale the first time the code changes.
- Don't copy the request and response shapes. Link to [api-contracts.md](api-contracts.md), which is the single source of truth.
- Anything every endpoint in the pipeline shares (clients, the stack, shared helpers) goes in the pipeline's `README.md` and `helpers.md`. Link to it instead of repeating it.

---

```markdown
# <METHOD> <path>

**Contract:** [api-contracts.md → <METHOD> <path>](../../general/api-contracts.md#<anchor>)
**Status:** Not started | In progress | Done
**Code:** `src/<pipeline>/app.py` → `<function_name>()`

## What it does
One or two sentences, from the user's point of view.

## How it works
The steps in order. Each step names the function or AWS call it uses.
1. Get the user ID with `get_user_id(...)`. None → 401.
2. ...
N. Log `<event name>` and return `<status>`.

## Objects and calls
For each object the endpoint touches (`app.current_event`, `table`, `s3`, `logger`):
the exact method, each parameter and why it's set that way, and what it returns.

## Helpers
| Helper | Where | New or existing | Signature → returns |
|---|---|---|---|

## Errors
| Condition | Status | `error` message | Log |
|---|---|---|---|
Include every row in the contract, plus how to tell apart cases that raise the same exception.

## Infrastructure
Template events, permissions and environment variables this endpoint needs, and whether they
already exist. "None, already in `templates/<file>.yaml`" is a valid answer.

## Done when
curl commands against `python dev.py` (port 3001) and the expected status for each.

## Gotchas
Things that look right but aren't.

---

New to a term? See the [glossary](../../general/glossary.md).
```

---

New to a term? See the [glossary](glossary.md).
