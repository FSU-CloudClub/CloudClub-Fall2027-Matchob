""""" Rank fuesion: merge several ranked lists into one
The webapp will run two searches on the same resume:
    Key word search (matching exact words)
    A search that understands meaning (not my job)
    Each gives ranked list of resumes lines then combine into single ranking
"""


#Merge ranked list of indexes into one ranked list
def reciprocal_rank_fusion(ranked_lists, k=60):
    #Start dictionary to accumulate scores for each line index from all list
    points = {}
    
    #Loop through individual ranked list
    for ranked in ranked_lists: 
        
        #Loop through every item in current list tracking its rank
        for position, line_index in enumerate(ranked, start = 1):

            #add points for this postion and save total    
            points[line_index] = points.get(line_index, 0.0) + 1.0 /(k +position)
        
        #Convert accumulated dictionary points into a list of dictionaries
    fused = [
        {"line_index": line_index, "score": score}
        for line_index, score in points.items()
        ]
    #Sort combined results by score (highest first, using the negative sign) 
    # #then line_index if there's a tie
    fused.sort(key = lambda result: (-result["score"], result["line_index"]))
    
    #return final unified ranked list
    return fused