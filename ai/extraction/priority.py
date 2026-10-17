import re

def priority(line: str, heading: str = "") -> str:
    """
    Determine the priority of a line in a job posting.
    Returns "nice" if the line or its section heading indicates a preference,
    and "must" otherwise. Pass the heading supplied by clean_posting().
    """
    return "nice" if re.search(
        r"\b(?:preferred|a\s+plus|nice[\s-]+to[\s-]+have|bonus|desired)\b",
        f"{heading}\n{line}",
        re.IGNORECASE,
    ) else "must"
