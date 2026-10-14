import re

def priority(line: str) -> str:
    """
    Determine the priority of a line in a job posting.
    Returns "nice" if it indicates that a skill or qualification is preferred, and "must" otherwise. To be used after clean_posting() to filter out non-job lines.
    """
    return "nice" if re.search(
        r"\b(?:preferred|a\s+plus|nice[\s-]+to[\s-]+have|bonus|desired)\b",
        line,
        re.IGNORECASE,
    ) else "must"
