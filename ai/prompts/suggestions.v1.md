# Suggestions prompt — v1

This is the Bedrock console prompt behind Backend's `POST /suggestions`. Backend
fills in five variables and returns the model's reply unchanged, so the reply
must be exactly the shape in `backend/SAMproject/docs/general/api-contracts.md`
(POST /suggestions): `{"suggestions": [{"id", "suggestion", "reason"}]}`.

Each `suggestion` is a finished rewrite of one resume bullet, not advice.

Variables, exact names (`company` and `supporting_context` can be empty):
`{{resume}}`, `{{job_title}}`, `{{company}}`, `{{job_description}}`,
`{{supporting_context}}`. Renaming one in the console breaks every call until
Backend renames it too.

---

## Honesty rules

These go into the system message as written. The console guardrail checks each
reply against the resume and blocks the whole reply if one rewrite drifts, so
these rules are what keep users from getting no suggestions.

- Only reword what the resume already says. Do not add numbers, tools or job
  titles the resume doesn't have. The supporting context only says what to
  focus on; it is never a source of facts.
- If a number would make a bullet stronger but the resume doesn't give one,
  leave a blank such as "[add your number]" for the user to fill in.
- Never add a skill or tool from the job posting unless the resume already has
  it.

## The rest of the prompt

Javier writes this part: the task, how many suggestions, and the reply format.
