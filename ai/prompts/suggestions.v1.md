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

## Console settings

Decided by Noah, 2026-10-30. Set these in the club's Bedrock console.

- **Model:** Claude Sonnet, the newest version the region has turned on. It balances
  speed (the reply must come back within 25 s) with following the honesty rules.
- **Contextual grounding check:** on, strict. The grounding source is the resume only;
  the supporting context steers focus and is not a source. Set the exact threshold by
  testing QA's practice cases, including one rewrite with an "[add your number]" blank.
- **Sensitive information:**
  - `US_SOCIAL_SECURITY_NUMBER`: block on input and output. It never belongs on a resume.
  - Custom regex `birth-date`: no action on input, block on output. People with a birth
    date on their resume can still use Matchob, but it never appears in a rewrite.
    `\b([Dd]ate [Oo]f [Bb]irth|DOB|[Bb]orn)\b|\b\d{1,2}[/.-]\d{1,2}[/.-](19|20)\d{2}\b|\b(19|20)\d{2}-\d{2}-\d{2}\b`
- **No masking:** Bedrock reports a mask the same way as a block (`guardrail_intervened`),
  and Backend's code turns both into an error, so masking would only hide the reason.

Still to test in the console: whether the saved prompt can mark the resume as the
grounding source. If it can't, the grounding check has nothing to compare against.

## The rest of the prompt

Javier writes this part: the task, how many suggestions, and the reply format.
