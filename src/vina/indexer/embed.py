from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from fastembed import TextEmbedding

from ..config import MODELS_DIR

logger = logging.getLogger("vina.embedder")

# Global lock guaranteeing mutual exclusion during model allocation passes
_MODEL_INIT_LOCK = threading.Lock()


class Embedder:
    """
    Thread-safe Singleton wrapper managing the lifecycle of the underlying 
    fastembed ONNX runtime text transformer.
    """
    _instance: Optional[TextEmbedding] = None

    @classmethod
    def get_instance(cls) -> TextEmbedding:
        """
        Retrieves the shared TextEmbedding instance handle.
        Uses double-checked locking to prevent duplicate model initialization.
        """
        if cls._instance is None:
            with _MODEL_INIT_LOCK:
                if cls._instance is None:
                    logger.info("Initializing fastembed context. Target loading directory: %s", MODELS_DIR)
                    # Let initialization errors bubble up explicitly so startup faults trace cleanly
                    cls._instance = TextEmbedding(
                        model_name="sentence-transformers/all-MiniLM-L6-v2",
                        cache_dir=str(MODELS_DIR)
                    )
                    logger.info("TextEmbedding framework initialized successfully.")
        return cls._instance


def embed_texts(
    texts: list[str], 
    batch_size: int = 256, 
    parallel: Optional[int] = None
) -> list[list[float]]:
    """
    Generates dense vector embeddings across an input array of text chunks.
    Allows structural parameter configuration adjustments to optimize offline indexing scale workloads.
    
    Args:
        texts: Text fragments to embed.
        batch_size: Number of strings processed simultaneously per inference cycle (Default: 256).
        parallel: Parallel execution worker count. Set to 0 to auto-detect CPU cores. 
                  Set to None to use default single-process threading patterns.
    """
    if not texts:
        return []

    # 1. Resolve Singleton (Initialization errors bubble up deliberately to catch configuration faults early)
    model = Embedder.get_instance()
    
    # 2. Execute vector transformation inference loop
    try:
        logger.debug(
            "Executing embedding generation pass for %d text assets (batch_size=%d, parallel=%s).", 
            len(texts), batch_size, parallel
        )
        
        # Stream model generator arrays natively through numpy .tolist() representations
        embeddings_gen = model.embed(texts, batch_size=batch_size, parallel=parallel)
        return [vec.tolist() for vec in embeddings_gen]
        
    except Exception as err:
        logger.exception("Inference processing pipeline dropped due to internal error constraints: %s", err)
        return []