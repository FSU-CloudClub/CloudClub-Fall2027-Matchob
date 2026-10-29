"""QA guardrail harness: run tricky cases through classify() and report how often it gets the label right.

Usage (from the repo root, with the venv active):
    python -m qa.harness.run_cases qa/tricky_cases/tricky_cases_practice.json
    python -m qa.harness.run_cases ai/fixtures/adversarial/cases.json --out results.md
    python -m qa.harness.run_cases ~/Projects/matchob-private/tricky_cases_locked.json --out ~/Projects/matchob-private/results_locked.md

Each case file is a JSON list of objects with at least:
    name, source (the resume line), suggestion (MatchOB's rewrite), expected (supported / needs_confirmation / unsupported)
Optional: kind, pile, evidence (a user note), why.

LOCKED CASES NEVER GO IN THE REPO. Keep the locked file (and its results) outside this folder and
pass its path in. Results for locked cases are shared as counts only.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from ai.guardrails.classify import classify

LABELS = ["supported", "needs_confirmation", "unsupported"]
STRICTNESS = {label: i for i, label in enumerate(LABELS)}  # higher = stricter


def norm_label(label):
    """'Needs Confirmation' / 'needs confirmation' / 'needs_confirmation' -> 'needs_confirmation'."""
    return str(label).strip().lower().replace(" ", "_").replace("-", "_")


def load_cases(path):
    cases = json.loads(Path(path).expanduser().read_text())
    if not isinstance(cases, list):
        sys.exit(f"{path}: expected a JSON list of cases")
    problems = []
    for i, case in enumerate(cases):
        for field in ("source", "suggestion", "expected"):
            if not isinstance(case.get(field), str):
                problems.append(f"case {i} ({case.get('name', 'no name')}): missing '{field}'")
        if isinstance(case.get("expected"), str) and norm_label(case["expected"]) not in LABELS:
            problems.append(f"case {i} ({case.get('name')}): unknown expected label '{case['expected']}'")
    if problems:
        sys.exit("Fix these before running:\n  " + "\n  ".join(problems))
    return cases


def verdict(expected, got):
    """correct, too_lenient (the dangerous miss: MatchOB would let it through) or too_strict."""
    if got == expected:
        return "correct"
    return "too_lenient" if STRICTNESS[got] < STRICTNESS[expected] else "too_strict"


def run(cases):
    rows = []
    for case in cases:
        # classify takes the suggestion FIRST, then the resume text, then the optional user note.
        result = classify(case["suggestion"], case["source"], case.get("evidence", ""))
        expected, got = norm_label(case["expected"]), result["status"]
        rows.append(dict(name=case.get("name", "(no name)"), kind=case.get("kind", "(no kind)"),
                         expected=expected, got=got, verdict=verdict(expected, got),
                         reasons=result["reasons"]))
    return rows


def report(rows, path):
    n = len(rows)
    correct = sum(r["verdict"] == "correct" for r in rows)
    v = Counter(r["verdict"] for r in rows)
    lines = [f"# Guardrail results: {Path(path).name}", "",
             f"Run {date.today().isoformat()} against `classify()` on the current branch.", "",
             f"**{correct} of {n} correct ({correct / n:.0%}).** "
             f"Too lenient (would let a bad claim through): {v['too_lenient']}. "
             f"Too strict (would flag an honest rewrite): {v['too_strict']}.", "",
             "## By kind", "", "| Kind | Correct | Total |", "|---|---|---|"]
    by_kind = defaultdict(list)
    for r in rows:
        by_kind[r["kind"]].append(r)
    for kind, rs in sorted(by_kind.items()):
        lines.append(f"| {kind} | {sum(r['verdict'] == 'correct' for r in rs)} | {len(rs)} |")
    lines += ["", "## Expected vs. got", "", "| expected \\ got | " + " | ".join(LABELS) + " |",
              "|---|" + "---|" * len(LABELS)]
    for e in LABELS:
        lines.append(f"| {e} | " + " | ".join(str(sum(r['expected'] == e and r['got'] == g for r in rows)) for g in LABELS) + " |")
    misses = [r for r in rows if r["verdict"] != "correct"]
    lines += ["", "## Misses", ""]
    if not misses:
        lines.append("None.")
    for r in misses:
        why = "; ".join(r["reasons"]) or "no rule fired"
        lines.append(f"- **{r['name']}** ({r['kind']}): expected `{r['expected']}`, got `{r['got']}` "
                     f"({r['verdict'].replace('_', ' ')}). Guardrail's reasons: {why}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Run QA tricky cases through the guardrail.")
    parser.add_argument("cases", help="path to a JSON list of cases")
    parser.add_argument("--out", help="also write the markdown report to this file")
    args = parser.parse_args()
    rows = run(load_cases(args.cases))
    text = report(rows, args.cases)
    print(text)
    if args.out:
        out = Path(args.out).expanduser()
        out.write_text(text)
        print(f"Saved to {out}")


if __name__ == "__main__":
    main()
