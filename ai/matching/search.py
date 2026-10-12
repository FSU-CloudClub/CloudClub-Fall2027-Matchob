import re

from rank_bm25 import BM25Okapi


def keyword_search(requirement: str, units: list[dict], top_k: int = 5) -> list[str]:
    """Return unit IDs ranked by descending BM25 score."""
    if top_k <= 0 or not units:
        return []

    def words(text):
        return re.findall(r"\w+", text.lower())

    corpus = [words(u["text"]) for u in units]
    if not any(corpus):
        return [u["id"] for u in units[:top_k]]

    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(words(requirement))
    ranked = sorted(range(len(units)), key=lambda i: scores[i], reverse=True)
    return [units[i]["id"] for i in ranked[:top_k]]
