import re


def keyword_search(requirement: str, units: list[dict], top_k: int = 5) -> list[str]:
    """Return unit IDs ranked by distinct words shared with their text."""
    if top_k <= 0:
        return []

    words = set(re.findall(r"\w+", requirement.lower()))
    scores = []
    for unit in units:
        unit_words = set(re.findall(r"\w+", unit["text"].lower()))
        score = len(words & unit_words)
        if score:
            scores.append((unit["id"], score))

    scores.sort(key=lambda item: item[1], reverse=True)
    return [unit_id for unit_id, _ in scores[:top_k]]
