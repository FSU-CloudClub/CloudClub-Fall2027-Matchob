"""Normalize tech terms so different spellings of the same skill match.

Example: normalize("Built JS apps on AWS Lambda") -> "built javascript apps on lambda"
"""

import json
import re
from pathlib import Path

# synonyms.json sits in the same folder as this file. Building the path from
# __file__ means it loads correctly no matter which folder the code runs from.
SYNONYMS_PATH = Path(__file__).parent / "synonyms.json"

with open(SYNONYMS_PATH, encoding="utf-8") as f:
    SYNONYMS = json.load(f)

# Turn {"javascript": ["js", "java script"], ...} into a flat list of
# (alias, name) pairs: [("js", "javascript"), ("java script", "javascript"), ...]
ALIAS_PAIRS = []
for name, aliases in SYNONYMS.items():
    for alias in aliases:
        ALIAS_PAIRS.append((alias, name))

# Longest alias first, so "node.js" is replaced before "js" can turn it
# into "node.javascript".
ALIAS_PAIRS.sort(key=lambda pair: len(pair[0]), reverse=True)


def normalize(text: str) -> str:
    """Lowercase text and replace every alias with its standard name (whole words only)."""
    text = text.lower()
    for alias, name in ALIAS_PAIRS:
        text = re.sub(r"\b" + re.escape(alias) + r"\b", name, text)
    return text