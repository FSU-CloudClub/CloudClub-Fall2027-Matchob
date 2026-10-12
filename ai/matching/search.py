""" Keyword seach: finds which resume lines match a job requiremnt
Picture:
    Input:
        One requiremnt from a posting   EX: "Python"
        The resume lists in a line      EX: "Bult a... in Python"
    Output:
        The line that matches, best one first
How:
    1. Breaks requriemnt and every reusme line into lowercase
    2. score each line by words it shares with requriemnt 
        (Rare words count more than common)
    3. Return best lines
"""

import re                       #tool for finding patters
from rank_bm25 import BM25Plus  #tool for scoring math

# Identifiying Filler words that say nothing abt skill
STOPWORDS = {
    # Articles & Determiners
    "a", "an", "the", "this", "that", "these", "those",
    
    # Prepositions
    "of", "in", "on", "to", "for", "with", "at", "by", "as", "from", 
    "into", "through", "about", "against", "during", "before", "after", 
    "over", "under", "between", "within", "without",
    
    # Conjunctions
    "and", "or", "but", "so", "nor", "yet", "both", "either", "neither", "also",
    
    # Verbs (Auxiliary & Common)
    "is", "are", "be", "been", "being", "was", "were", "have", "has", "had", 
    "do", "does", "did", "can", "could", "will", "would", "should", "must", 
    "may", "using", "use", "used", "requires", "required", "including", "includes",
    
    # Pronouns
    "they", "them", "their", "we", "our", "you", "your", "who", "which",
    
    # Skill Fluff / Vague Context Words
    "experience", "knowledge", "ability", "abilities", "proficient", "proficiency", 
    "understanding", "strong", "proven", "background", "skills", "skill", "years", "year"
}

# Turn text into a list of lowcase words
def tokenize(text):
        #re.findall:returns every peice of text that fits patter as a list
        #equation: one or more letters/digits + zero or more + or signs
        #text.lower:makes everything lowercase
    words = re.findall(r"[a-z0-9]+[+#]*", text.lower())     
        #Builds list that keeps everything but filler
    return [word for word in words if word not in STOPWORDS]

#Find the resume lines that best match requirment
def keyword_search(requirment, resume_lines, top_k=5):
    #Clearn/Tokenize  requirment string into list of words
    query_words = tokenize(requirment)
    #Clean/Tokenize every single line in resume list
    lines_as_words = [tokenize(line) for line in resume_lines]

    #Gaurd clause: If req is empty or no words return empty list
    if not query_words or not any(lines_as_words):
        return []

    bm25 = BM25Plus(lines_as_words)     #Start the ranking algorithm
    scores = bm25.get_scores(query_words)   #Clac relevance scores for all resume lines against query words
    results = []    #Start an empty list to hold match results

    #Loop through every resume line along with its line number (index)
    for index, line in enumerate (resume_lines):
        #Check if req and resume line share atleast one key word
        shares_a_word = bool(set(query_words) & set (lines_as_words[index]))

        #If they share package the match details and add to result list
        if shares_a_word:
            results.append(
                {
                    "line_index": index,
                    "text": line,
                    "score": float(scores[index]),
                }
            )
    #Stor results by score (highest first) and then by line index
    results.sort(key = lambda result: (-result["score"], result["line_index"]))
    return results[:top_k]  #return only top K matches (default is 5)






