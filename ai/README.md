# Matchob AI

The AI side of Matchob. It reads a pasted job posting, finds the matching lines in a resume, and labels every suggestion **Supported**, **Needs Confirmation** or **Unsupported**.

## Get set up (once)

From the top folder of the repo:

1. `python -m venv .venv`
2. Turn it on. Windows: `.venv\Scripts\activate` · Mac: `source .venv/bin/activate`
3. `pip install -r ai/requirements.txt`
4. `python -m unittest discover ai/tests` should end with `OK`

## Who works where

Only edit your own lane's files, so nobody's work collides.

| Lane | Job | Where |
| --- | --- | --- |
| 1 | The contract: the shape of every AI answer | `contracts/` |
| 2 | Fake resumes and mock answers for Frontend | `fixtures/resumes/`, `fixtures/mock_responses/` |
| 3 | Clean up job postings | `extraction/` |
| 4 | Job postings, answer keys, the prompt | `fixtures/jobs/`, `prompts/` |
| 5 | Synonym list and resume lines | `matching/` (synonyms, normalize, units) |
| 6 | Keyword search and ranking | `matching/` (search, fusion) |
| 7 | Span check and claim finder | `guardrails/` (span_check, claims) |
| 8 | Final label and attack tests | `guardrails/classify.py`, `fixtures/adversarial/` |

Each lane also has one test file in `tests/`.

## Three rules

- Made-up data only. This repo is public.
- Work on a branch and open a pull request. Never commit to `main`.
- `git add` your files by name, never `git add .`
