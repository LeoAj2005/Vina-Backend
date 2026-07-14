from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel
from .config import get_or_create_token
from .search.retrieve import search_files

app = FastAPI(title="Vina Backend")

# --- Pydantic Data Verification Schemas ---

class SearchResult(BaseModel):
    filepath: str
    score: float
    excerpt: str

class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[SearchResult]

# --- Security Dependencies ---

async def verify_token(x_vina_token: str = Header(None)):
    """Dependency to enforce the local shared secret via X-Vina-Token header."""
    expected_token = get_or_create_token()
    if x_vina_token != expected_token:
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid or missing token.")
    return True

# --- API Endpoints ---

@app.get("/api/health")
async def health():
    """Unauthenticated health check."""
    return {"status": "ok"}

@app.get(
    "/api/search",
    response_model=SearchResponse
)
async def search(query: str, limit: int = 10, authorized: bool = Depends(verify_token)):
    """
    Searches the indexed files for a given query.
    Requires 'X-Vina-Token' header verification.
    """
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
    results = search_files(query, limit=limit)
    
    # Format results for explicit match against SearchResponse structure
    return {
        "query": query,
        "count": len(results),
        "results": [
            {
                "filepath": res["filepath"],
                "score": res["score"],
                "excerpt": res["text"][:200] + "..." if len(res["text"]) > 200 else res["text"]
            }
            for res in results
        ]
    }