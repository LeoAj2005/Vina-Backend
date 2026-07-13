# src/vina/search/retrieve.py
from ..indexer.embed import embed_texts
from ..indexer.store import VectorStore

# Reuse the store instance
store = VectorStore()

def search_files(query: str, limit: int = 10) -> list[dict]:
    """Searches the indexed files for a given query."""
    
    # 1. Embed the query (FastEmbed expects a list)
    query_vectors = embed_texts([query])
    if not query_vectors:
        return []
    query_vector = query_vectors[0]
    
    # 2. Search LanceDB
    # We request more results than 'limit' because we need to collapse chunks into files
    results = store.table.search(query_vector).limit(limit * 4).to_list()
    
    if not results:
        return []
        
    # 3. Collapse: Keep only the highest-scoring chunk per file
    seen_files = {}
    for row in results:
        filepath = row["filepath"]
        score = row["_distance"] # Lower distance is better in LanceDB
        
        if filepath not in seen_files or score < seen_files[filepath]["score"]:
            seen_files[filepath] = {
                "filepath": filepath,
                "score": score,
                "text": row["text"],
                "chunk_index": row["chunk_index"]
            }
            
    # Sort by score (ascending, since distance is lower=better) and apply limit
    collapsed = sorted(seen_files.values(), key=lambda x: x["score"])[:limit]
    return collapsed