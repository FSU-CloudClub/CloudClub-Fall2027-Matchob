import re


def priority(line: str) -> str:
    return "nice" if re.search(
        r"\b(?:preferred|a\s+plus|nice[\s-]+to[\s-]+have|bonus|desired)\b",
        line,
        re.IGNORECASE,
    ) else "must"
