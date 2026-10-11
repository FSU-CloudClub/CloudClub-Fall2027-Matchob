"""Tests for ai/matching/normalize.py and the synonyms.json it loads.

Run from the repo root:  python -m pytest ai/tests -v
"""

import re

import pytest

from ai.matching.normalize import SYNONYMS, normalize


# --- The three cases from the task checklist ---

def test_alias_is_replaced():
    assert normalize("Built JS apps") == "built javascript apps"


def test_multi_word_alias_is_replaced():
    assert normalize("AWS Lambda") == "lambda"


def test_alias_inside_a_word_is_left_alone():
    assert normalize("JSON") == "json"


# --- More cases: each pair is (input, expected output) ---

@pytest.mark.parametrize(
    "text, expected",
    [
        # Longest alias wins, so "node.js" never becomes "node.javascript"
        ("Built Node.js apps", "built node apps"),
        ("React JS and React.js", "react and react"),
        ("Google Cloud Platform", "gcp"),
        ("Mongo DB and MongoDB", "mongo and mongo"),
        ("Continuous Integration/Continuous Deployment", "ci/cd"),
        # Punctuation and position in the sentence don't matter
        ("Experience with JS, TypeScript.", "experience with javascript, typescript."),
        ("JS", "javascript"),
        ("Amazon S3 and AWS EC2", "s3 and ec2"),
        # Ordinary words and look-alikes stay untouched
        ("TS/SCI clearance required", "ts/sci clearance required"),
        ("Go to market", "go to market"),
        ("", ""),
    ],
)
def test_normalize_cases(text, expected):
    assert normalize(text) == expected


def test_running_twice_changes_nothing():
    once = normalize("Built Node.js apps on AWS Lambda with PostgreSQL")
    assert normalize(once) == once


# --- Checks on synonyms.json itself, so future edits can't break normalize ---

def test_everything_is_lowercase():
    for name, aliases in SYNONYMS.items():
        assert name == name.lower(), name
        for alias in aliases:
            assert alias == alias.lower(), alias


def test_no_alias_is_listed_twice_or_is_also_a_name():
    seen = set()
    for aliases in SYNONYMS.values():
        for alias in aliases:
            assert alias not in seen, f"{alias!r} is listed more than once"
            assert alias not in SYNONYMS, f"{alias!r} is also a standard name"
            seen.add(alias)


def test_aliases_start_and_end_with_a_letter_or_number():
    # The \b whole-word rule only works next to letters and numbers,
    # which is why C++ and C# are left out.
    for aliases in SYNONYMS.values():
        for alias in aliases:
            assert alias[0].isalnum() and alias[-1].isalnum(), alias


def test_no_standard_name_contains_an_alias():
    # If a name contained an alias, a later replacement would mangle it.
    # Example: a name "node.js" would become "node.javascript".
    for name in SYNONYMS:
        for aliases in SYNONYMS.values():
            for alias in aliases:
                assert not re.search(r"\b" + re.escape(alias) + r"\b", name), (name, alias)