# Job postings and answer keys (Lane 4)

The answer key for requirement extraction. Ten job postings, every requirement
in each one labeled by hand. This is what lets us put a real accuracy number on
a slide — compare the AI's extracted requirements to these keys instead of
eyeballing it.

## What's here

- `job-01-*.txt` ... `job-10-*.txt` — the postings, plain text, one per file.
- `job-01-*.key.json` ... `job-10-*.key.json` — the hand-labeled answer key for
  each posting.
- `_build_answer_keys.py` — regenerates the `.key.json` files. A human picks the
  requirement phrases and their labels in this file; the script only computes
  the exact character offsets so each `source_span` matches the posting
  byte-for-byte. Re-run it after editing a posting or a label:
  `python ai/fixtures/jobs/_build_answer_keys.py`

Ten roles for variety: frontend, backend, data analyst, full stack, DevOps, ML,
QA, iOS, security, SRE. 77 requirements total — 47 `must`, 30 `nice`.

## Answer key shape

Each `.key.json` holds the posting text plus its requirements. Every requirement
follows `contracts/requirement.schema.json`:

```json
{
  "id": "req-1",
  "text": "building user interfaces with React",
  "category": "skill",
  "priority": "must",
  "source_span": { "start": 203, "end": 238, "text": "building user interfaces with React" }
}
```

`category` is one of `skill`, `tool`, `experience`, `responsibility`.
`priority` is `must` (Requirements section) or `nice` (Nice to have section).
`source_span` is a character range into the posting: `job_text[start:end]`
equals `text`.

## How to score the AI against this

1. Run the extraction prompt (`prompts/requirement_extraction.v1.md`) on a
   posting's `.txt`.
2. Match the model's requirements to the key's requirements (by overlapping
   span or close text).
3. Count: matched (true positive), missed from the key (false negative),
   invented by the model (false positive). Report precision / recall, and
   optionally how often `category` and `priority` agree on matched items.

## Note on the data

The repo is public, so every posting here is written by us, not scraped from a
real listing. They are modeled on how real postings read — an "about the role"
blurb, a Requirements section, a Nice to have section, benefits — so the
extractor faces the same shape it will see in production, without copying anyone
else's text.
