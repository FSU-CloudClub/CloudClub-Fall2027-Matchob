# Matchob AI

The AI side of Matchob. It reads a pasted job posting, finds the matching lines in a resume, and labels every suggestion **Supported**, **Needs Confirmation** or **Unsupported**.

## Get set up (once)

From the top folder of the repo:

1. `python -m venv .venv`
2. Turn it on. Windows: `.venv\Scripts\activate` · Mac: `source .venv/bin/activate`
3. `pip install -r ai/requirements.txt`
4. `python -m unittest discover ai/tests` should end with `OK`

## Who works where

Only edit your own files, so nobody's work collides.

| Who | Job | Where |
| --- | --- | --- |
| Noah, Duy | The contract: the shape of every AI answer | `contracts/` |
| Noah | Fake resumes and mock answers for Frontend | `fixtures/resumes/`, `fixtures/mock_responses/` |
| Arturo | Clean up job postings | `extraction/` (clean, priority) |
| Duy | Pull the requirements out of a job posting | `extraction/requirements.py` |
| Triet | Job postings, answer keys and the requirements prompt | `fixtures/jobs/`, `prompts/requirement_extraction.v1.md` |
| Rafael | Synonym list and splitting a resume into lines | `matching/` (synonyms, normalize, units) |
| Javier | Keyword search and ranking | `matching/` (search, fusion) |
| Arturo | Call the model and read its JSON reply | `model.py` |
| Javier | Resume suggestions | `suggest.py` |
| Noah, Javier | The suggestions prompt: Noah's honesty rules and console settings, Javier's instructions | `prompts/suggestions.v1.md` |
| Noah | Span check, claim finder, final label and attack tests | `guardrails/`, `fixtures/adversarial/` |

The live app gets its suggestions from Backend's single Bedrock call, which uses the prompt in `prompts/suggestions.v1.md`. `suggest.py` and `extraction/requirements.py` aren't used by it; they're kept for reference.

Each part has its tests in `tests/`.

## Three rules

- Made-up data only. This repo is public.
- Work on a branch and open a pull request. Never commit to `main`.
- `git add` your files by name, never `git add .`
