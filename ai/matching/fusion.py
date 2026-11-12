
def rrf(*ranked_lists, k=60) -> list:
    # Implement the Reciprocal Rank Fusion (RRF) algorithm to combine multiple ranked lists into a single ranked list.
    scores = {}
    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, start=1):
            scores[item] = scores.get(item, 0) + 1 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)