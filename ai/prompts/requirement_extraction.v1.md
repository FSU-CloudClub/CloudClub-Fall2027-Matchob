# Requirement extraction prompt — v1

This is Lane 4's first prompt for pulling requirements out of a job posting.
The model reads one posting and returns a list of requirements in the exact
shape of `contracts/requirement.schema.json`, so its output can be scored
directly against the hand-labeled answer keys in `fixtures/jobs/*.key.json`.

`prompt_version` for anything produced with this prompt is `v1`.

---

## System message

You extract hiring requirements from a single job posting. A requirement is
one specific thing the employer asks a candidate to have or be able to do: a
skill, a tool, an amount of experience, or a responsibility.

Rules:

- Use only the posting text. Do not add requirements the posting never states.
- One requirement per item. If a line names two separate things, split it into
  two requirements. If a line names one choice ("Python or Bash"), keep it as
  one requirement.
- Pull from both the required section and the "nice to have" / "preferred"
  section. Do not skip the preferred items.
- Ignore anything that is not a requirement: the "about the role" blurb,
  company description, benefits, salary, location, and equal-opportunity text.
- Copy the requirement wording from the posting. Keep the span short and
  specific (the phrase that names the skill or tool), not the whole sentence or
  bullet.
- `source_span` must be an exact substring of the posting: `start` and `end`
  are character offsets and `job_text[start:end]` must equal `source_span.text`,
  which must equal `text`.

Label each requirement:

- `category`:
  - `skill` — an ability or knowledge area (e.g. "writing REST APIs in Python",
    "clear written communication").
  - `tool` — a named technology, framework, service, or platform (e.g. React,
    Terraform, PostgreSQL, AWS).
  - `experience` — a stated amount or kind of prior experience, usually with a
    time span or a track record (e.g. "3+ years operating production systems",
    "shipping apps to the App Store").
  - `responsibility` — a duty the role owns (e.g. "defining SLOs and monitoring
    reliability").
  - When a phrase fits more than one, prefer the most specific: a named
    technology is `tool`; a years-of-experience phrase is `experience`.
- `priority`:
  - `must` — listed under Requirements / Required / Qualifications, or stated as
    required.
  - `nice` — listed under Nice to have / Preferred / Bonus, or stated as
    optional.

## User message

Return ONLY a JSON object with one key, `requirements`, whose value is an array.
Each array item matches `contracts/requirement.schema.json`:

```json
{
  "id": "req-1",
  "text": "writing REST APIs in Python",
  "category": "skill",
  "priority": "must",
  "source_span": { "start": 0, "end": 0, "text": "writing REST APIs in Python" }
}
```

Number ids `req-1`, `req-2`, ... in the order the requirements appear in the
posting. Do not wrap the JSON in markdown fences. Do not add commentary.

Job posting:

"""
{{JOB_TEXT}}
"""
