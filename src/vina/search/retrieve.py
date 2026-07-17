from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from ..indexer.embed import embed_texts
from ..indexer.store import VectorStore

logger = logging.getLogger(__name__)

# Global vector store fallback instance
_DEFAULT_STORE: Optional[VectorStore] = None


@dataclass(slots=True)
class SearchResult:
    """Structured container for deduplicated vector search matches."""
    filepath: str
    distance: float
    text: str
    chunk_index: int


def _get_store() -> VectorStore:
    """Lazily initializes the VectorStore to prevent import-time side effects."""
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = VectorStore()
    return _DEFAULT_STORE


def search_files(
    query: str, 
    limit: int = 10, 
    store: Optional[VectorStore] = None
) -> list[SearchResult]:
    """
    Searches indexed file chunks for a given query and collapses them by file.
    
    Extracts the highest-ranking chunk per unique file using an O(N) early-exit filter.
    """
    # 1. Input validation & normalization
    clean_query = query.strip()
    if not clean_query:
        logger.warning("Search executed with an empty or whitespace-only query.")
        return []

    # Fallback to the lazy-loaded global store if none is injected
    active_store = store or _get_store()
    
    # Clean check: VectorStore configuration guarantees the 'table' attribute exists
    if active_store.table is None:
        logger.error("VectorStore table is uninitialized or unavailable.")
        return []

    # 2. Compute query embeddings
    logger.debug("Generating embeddings for search query.")
    query_vectors = embed_texts([clean_query])
    if not query_vectors:
        logger.warning("Embedding engine returned no vector data for query.")
        return []
    query_vector = query_vectors[0]

    # 3. Query Vector Database
    # Heuristic: We over-fetch chunks to account for duplicates across the same file.
    # Caveat: If highly uniform files contain thousands of sequential matching chunks, 
    # this multiplier may still under-fetch enough unique files to satisfy the limit.
    oversample_limit = limit * 4
    logger.debug("Executing LanceDB vector search (oversample limit: %d).", oversample_limit)
    
    try:
        results = (
            active_store.table
            .search(query_vector)
            .select(["filepath", "text", "chunk_index", "_distance"])
            .limit(oversample_limit)
            .to_list()
        )
    except Exception:
        logger.exception("Database execution failure during vector retrieval.")
        return []

    if not results:
        logger.debug("Vector search returned zero matches.")
        return []

    # 4. Collapse Chunks to Unique Files (Natural Order Optimization)
    # Assumes LanceDB returns search results ordered by nearest-neighbor distance. 
    # When using approximate ANN indexes (like IVF-PQ) without explicit refinement, 
    # ordering may itself be approximate. The first time we encounter a filepath, 
    # we treat it as its best matching chunk.
    seen_files: dict[str, SearchResult] = {}
    
    for row in results:
        filepath = row.get("filepath")
        if not filepath:
            continue
            
        if filepath not in seen_files:
            seen_files[filepath] = SearchResult(
                filepath=filepath,
                distance=float(row.get("_distance", 0.0)),
                text=str(row.get("text", "")),
                chunk_index=int(row.get("chunk_index", 0))
            )
            
            # Early exit optimization: stop iterating once the target limit is filled
            if len(seen_files) == limit:
                break

    logger.debug("Retrieved %d unique file matches after deduplication.", len(seen_files))
    return list(seen_files.values())