import re
from rank_bm25 import BM25Plus


def keyword_search(requirement: str, units: list[dict], top_k: int = 5) -> list[str]:
    """Return unit IDs ranked by descending BM25 score."""
    if top_k <= 0 or not units:
        return []

    def words(text):
        return re.findall(r"\w+", text.lower())

    #Javier mods
    #This modification implements the empty check that returns nothing since there is nothing can match
    query = words(requirement)
    corpus = [words(u["text"]) for u in units]
    if not query or not any (corpus):
        return[]
    

    #Javier mods
    #We use BM25Plus because this can do the ranking algorithm
    #while OKapi gives a word in half the units zero weight
    bm25 = BM25Plus(corpus)
    scores = bm25.get_scores(query) #one score per unit, same order as units (relevance score)
    
    #Javier mods
    #old shares_a_word in one line:
    #keeps position i of every unit that shares at least one word
    #A tie goes to the earlier unit like before
    matches = [i for i, unit_words in enumerate(corpus) if set(query) & set(unit_words)]

    #Javier mods
    #Sorts heighest first, then earlier postion wins tie
    ranked = sorted(matches, key = lambda i: (-scores[i], i))



    return [units[i]["id"] for i in ranked[:top_k]]

