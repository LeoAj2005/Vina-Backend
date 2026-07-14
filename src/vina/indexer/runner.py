import os
import time
import logging
from pathlib import Path
from .extract import extract_text
from .chunk import chunk_text
from .embed import embed_texts
from .store import VectorStore

logger = logging.getLogger(__name__)

# Shared instance keeps connection open for both indexer & watcher
store = VectorStore()
SUPPORTED_EXTS = {".pdf", ".docx", ".txt", ".json"}

def process_file(filepath: str) -> int:
    """Processes, embeds, and updates a single file in the vector database."""
    try:
        path_obj = Path(filepath)
        stat = os.stat(filepath)
        current_mtime = stat.st_mtime
        current_size = stat.st_size

        text = extract_text(filepath)
        if not text:
            return 0
            
        chunks = chunk_text(text)
        if not chunks:
            return 0
            
        vectors = embed_texts(chunks)
        
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
        
        store.delete_file_chunks(filepath)
        store.add_chunks(records)
        logger.info(f"Indexed asset: {path_obj.name} ({len(chunks)} chunks)")
        return len(chunks)
        
    except Exception as e:
        logger.error(f"Error processing {filepath}: {e}", exc_info=True)
        return 0

def delete_file(filepath: str):
    """Removes a file's records completely from the vector store."""
    try:
        store.delete_file_chunks(filepath)
        logger.info(f"Removed from index: {Path(filepath).name}")
    except Exception as e:
        logger.error(f"Error removing {filepath}: {e}", exc_info=True)

def run_indexer(target_folder: str):
    """Performs the initial baseline scan across the dynamically provided target directory."""
    logger.info(f"Starting baseline indexer execution on: {target_folder}")
    
    start_time = time.time()
    files_processed = 0
    files_skipped = 0
    
    if not os.path.exists(target_folder):
        logger.warning(f"Target folder target path does not exist: {target_folder}")
        return

    for root, _, files in os.walk(target_folder):
        for file in files:
            filepath = Path(root, file).resolve().as_posix()
            ext = Path(file).suffix.lower()
            
            if ext not in SUPPORTED_EXTS:
                continue
                
            try:
                stat = os.stat(filepath)
                current_mtime = stat.st_mtime
                current_size = stat.st_size
                
                db_mtime, db_size = store.get_file_meta(filepath)
                
                if db_mtime == current_mtime and db_size == current_size:
                    files_skipped += 1
                    continue
                    
                chunks_added = process_file(filepath)
                if chunks_added > 0:
                    files_processed += 1
                    
            except Exception as e:
                logger.error(f"Error checking metadata for {filepath}: {e}")
                
    elapsed = time.time() - start_time
    logger.info(f"Baseline indexing complete in {elapsed:.2f}s")
    logger.info(f"Files processed: {files_processed} | Files skipped (up-to-date): {files_skipped}")