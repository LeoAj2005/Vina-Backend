from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

from .chunk import chunk_text
from .embed import embed_texts
from .extract import extract_text
from .store import VectorStore

logger = logging.getLogger(__name__)

# Track supported types via set-lookup syntax for O(1) matching speed
SUPPORTED_EXTS = {".pdf", ".docx", ".txt", ".json"}

# Global vector store fallback instance to prevent eager import-time connections
_DEFAULT_STORE: Optional[VectorStore] = None


def _get_store() -> VectorStore:
    """Lazily initializes the VectorStore instance to prevent early connection side effects."""
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = VectorStore()
    return _DEFAULT_STORE


def process_file(
    filepath: str, 
    mtime: Optional[float] = None, 
    size: Optional[int] = None,
    store: Optional[VectorStore] = None
) -> int:
    """
    Processes, extracts, chunks, embeds, and updates a single file in the vector database.
    Accepts pre-computed metadata stats to avoid duplicate disk I/O operations.
    """
    active_store = store or _get_store()
    try:
        # 1. Reuse passed metadata stats if available, otherwise read from disk defensively
        if mtime is None or size is None:
            stat = os.stat(filepath)
            current_mtime = stat.st_mtime
            current_size = stat.st_size
        else:
            current_mtime = mtime
            current_size = size

        # 2. Extract text data layer
        text = extract_text(filepath)
        if not text:
            logger.debug("Extraction yielded zero usable text characters for: %s", filepath)
            return 0
            
        # 3. Dissect body text into operational chunks
        chunks = chunk_text(text)
        if not chunks:
            logger.debug("Text segmentation split yielded zero chunks for: %s", filepath)
            return 0
            
        # 4. Generate queryable text embeddings
        vectors = embed_texts(chunks)
        
        # Guard check: Ensure absolute vector-to-chunk array mapping alignment
        if len(vectors) != len(chunks):
            logger.error(
                "Embedding vector array mismatch for %s. Generated %d vectors for %d text chunks.",
                filepath, len(vectors), len(chunks)
            )
            return 0
        
        # 5. Build transaction records matrix
        records = [
            {
                "vector": vec,
                "filepath": filepath,
                "chunk_index": idx,
                "text": chunk,
                "mtime": current_mtime,
                "size": current_size,
            }
            for idx, (vec, chunk) in enumerate(zip(vectors, chunks))
        ]
        
        # 6. Atomic swap operation inside database layer
        active_store.delete_file_chunks(filepath)
        active_store.add_chunks(records)
        
        logger.info("Successfully indexed asset: %s (%d text chunks committed)", Path(filepath).name, len(chunks))
        return len(chunks)
        
    except FileNotFoundError:
        logger.warning("File vanished from filesystem layer during index processing execution: %s", filepath)
        return 0
    except Exception as err:
        logger.exception("Catastrophic processing pipeline failure for target asset %s: %s", filepath, err)
        return 0


def delete_file(filepath: str, store: Optional[VectorStore] = None) -> None:
    """Removes a file's chunks completely from the vector store index layer."""
    active_store = store or _get_store()
    try:
        active_store.delete_file_chunks(filepath)
        logger.info("Evicted file footprints completely from vector index: %s", Path(filepath).name)
    except Exception as err:
        logger.exception("Failed to purge target asset from database index: %s. Error: %s", filepath, err)


def run_indexer(target_folder: str, store: Optional[VectorStore] = None) -> None:
    """
    Performs an incremental directory-wide baseline sync scan across the target directory.
    Optimized to minimize file handle creation and filesystem tracking overhead.
    """
    logger.info("Starting baseline indexer execution targeting: %s", target_folder)
    active_store = store or _get_store()
    
    start_time = time.time()
    files_processed = 0
    files_skipped = 0
    
    path_root = Path(target_folder).resolve(strict=False)
    if not path_root.exists():
        logger.warning("Target folder sync execution aborted: Path does not exist: %s", path_root)
        return

    # Leverage os.walk using direct string operations to protect memory allocations
    for root, _, files in os.walk(str(path_root)):
        for file in files:
            # High-performance string suffix extraction (bypasses thousands of Path instances)
            _, ext = os.path.splitext(file)
            ext_lower = ext.lower()
            
            if ext_lower not in SUPPORTED_EXTS:
                continue
                
            filepath = os.path.join(root, file)
            normalized_path = Path(filepath).resolve(strict=False).as_posix()
            
            try:
                # Capture metadata stats once
                stat = os.stat(normalized_path)
                current_mtime = stat.st_mtime
                current_size = stat.st_size
                
                # Verify existing cached items within database record index
                db_mtime, db_size = active_store.get_file_meta(normalized_path)
                
                if db_mtime == current_mtime and db_size == current_size:
                    files_skipped += 1
                    continue
                
                # Forward pre-computed disk stats into the processing step to avoid redundant read cycles
                chunks_added = process_file(
                    filepath=normalized_path, 
                    mtime=current_mtime, 
                    size=current_size, 
                    store=active_store
                )
                if chunks_added > 0:
                    files_processed += 1
                    
            except FileNotFoundError:
                # Catch case where temporary files get removed during our folder traversal pass
                logger.debug("Tracked asset vanished intermediate to directory scanning loops: %s", normalized_path)
                continue
            except Exception as err:
                logger.error("Error executing baseline diagnostic check for asset: %s. Error: %s", normalized_path, err)
                
    elapsed = time.time() - start_time
    logger.info("Baseline directory indexing synchronization completed in %.2fs", elapsed)
    logger.info("Sync Summary -> Files Analyzed & Re-Indexed: %d | Up-to-date Items Skipped: %d", files_processed, files_skipped)