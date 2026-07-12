import os
import time
from pathlib import Path
from .config import TARGET_FOLDER, get_or_create_token, APP_DIR
from .indexer.extract import extract_text
from .indexer.chunk import chunk_text
from .indexer.embed import embed_texts
from .indexer.store import VectorStore

def run_indexer():
    print(f"[Vina] Starting indexer on: {TARGET_FOLDER}")
    store = VectorStore()
    
    supported_exts = {".pdf", ".docx", ".txt", ".json"}
    start_time = time.time()
    files_processed = 0
    files_skipped = 0
    
    for root, _, files in os.walk(TARGET_FOLDER):
        for file in files:
            filepath = os.path.join(root, file)
            ext = Path(file).suffix.lower()
            
            if ext not in supported_exts:
                continue
                
            try:
                stat = os.stat(filepath)
                current_mtime = stat.st_mtime
                current_size = stat.st_size
                
                # Change Detection: skip if unchanged
                db_mtime, db_size = store.get_file_meta(filepath)
                if db_mtime == current_mtime and db_size == current_size:
                    files_skipped += 1
                    continue
                    
                # Extract & Chunk
                text = extract_text(filepath)
                if not text:
                    continue
                    
                chunks = chunk_text(text)
                if not chunks:
                    continue
                    
                # Embed
                vectors = embed_texts(chunks)
                
                # Prepare records for LanceDB
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
                
                # Delete old chunks and insert new ones
                store.delete_file_chunks(filepath)
                store.add_chunks(records)
                files_processed += 1
                print(f"[Vina] Indexed: {file} ({len(chunks)} chunks)")
                
            except Exception as e:
                print(f"[Vina] Error processing {filepath}: {e}")
                
    elapsed = time.time() - start_time
    print(f"\n[Vina] Indexing complete in {elapsed:.2f}s")
    print(f"[Vina] Files processed: {files_processed} | Files skipped (up-to-date): {files_skipped}")

def main():
    # Ensure token exists
    _ = get_or_create_token()
    
    # Run the Phase 1 test
    run_indexer()
    
    # We'll start the server in Phase 2+
    # import uvicorn
    # uvicorn.run("vina.server:app", host="127.0.0.1", port=8765, log_level="info")

if __name__ == "__main__":
    main()