from __future__ import annotations

import logging
import secrets
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from .config import get_or_create_token
from .search.retrieve import search_files

logger = logging.getLogger("vina.server")

app = FastAPI(
    title="Vina Backend",
    description="High-performance local semantic vector search engine API layer.",
    version="1.0.0"
)

# Cache token at module initialization level for O(1) operational performance.
# Assumption: Token rotation happens strictly on application restart cycles.
_CACHED_TOKEN = get_or_create_token()


# --- Pydantic Data Verification Schemas ---

class ApiSearchResult(BaseModel):
    """API representation of a deduplicated file match result."""
    filepath: str
    score: float = Field(..., description="Vector proximity distance (lower distances represent tighter semantic matches)")
    excerpt: str


class SearchResponse(BaseModel):
    """Unified wrapper structure containing consolidated query output metrics."""
    query: str
    count: int
    results: list[ApiSearchResult]


# --- Security Dependencies ---

async def verify_token(
    x_vina_token: Annotated[
        str | None, 
        Header(description="Local shared secret authorization token")
    ] = None
) -> bool:
    """
    Dependency to enforce local shared secret verification.
    Uses a constant-time comparison algorithm to eliminate timing attack vulnerabilities.
    """
    if not x_vina_token or not secrets.compare_digest(x_vina_token, _CACHED_TOKEN):
        logger.warning("Unauthorized access attempt rejected: invalid or missing security token header.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Invalid or missing token."
        )
    return True


# Reusable dependency type alias to decouple path signatures from framework internals
TokenVerified = Annotated[bool, Depends(verify_token)]


# --- API Endpoints ---

@app.get("/api/health", status_code=status.HTTP_200_OK)
async def health() -> dict[str, str]:
    """Unauthenticated structural health status checkpoint."""
    return {"status": "ok"}


@app.get(
    "/api/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK
)
async def search(
    query: str, 
    limit: Annotated[
        int, 
        Query(ge=1, le=100, description="Maximum number of unique file results to return")
    ] = 10, 
    _: TokenVerified = None
) -> SearchResponse:
    """
    Searches indexed local files for semantic context matches.
    Requires valid 'X-Vina-Token' structural header authorization checks.
    """
    clean_query = query.strip()
    if not clean_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter cannot be empty or pure whitespace."
        )

    # 1. Execute vector query through backend dataclass service
    retrieved_chunks = search_files(clean_query, limit=limit)
    
    # 2. Programmatically generate strongly-typed API response objects
    api_results: list[ApiSearchResult] = []
    
    for match in retrieved_chunks:
        text_body = match.text
        excerpt = (text_body[:200] + "...") if len(text_body) > 200 else text_body
        
        # Safe attribute layout access guaranteed by our internal Dataclass structural shift
        api_results.append(
            ApiSearchResult(
                filepath=match.filepath,
                score=match.distance,
                excerpt=excerpt
            )
        )
        
    # 3. Return fully initialized validation schemas directly for robust type-checking
    return SearchResponse(
        query=clean_query,
        count=len(api_results),
        results=api_results
    )