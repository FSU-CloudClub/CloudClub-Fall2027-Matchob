# Practice tricky cases vs. current guardrail

Safe to share with the AI team: practice cases only.

Run on 2026-10-22 against `classify()` from `origin/noah/final-label-and-attack-tests` (commit 18609d1). **1 of 3 practice cases gets the expected label.**

| Case | Expected | Got | Type | Note |
| --- | --- | --- | --- | --- |
| Growth called doubled when the math says 75% (400 to 700 subscribers) | unsupported | supported | Guardrail bug | Multiplier words like "doubled" aren't checked against the real numbers |
| Sibling database swapped (PostgreSQL to MySQL) | unsupported | unsupported | Match | |
| Correct percentage computed from the resume's numbers (600 to 900 = 50%) | supported | unsupported | Rule disagreement | The labeling guide accepts a calculated figure when the math checks out; the guardrail requires every number to appear in the resume |
