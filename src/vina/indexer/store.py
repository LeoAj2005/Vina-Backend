import lancedb
import pyarrow as pa
from pathlib import Path
from ..config import APP_DIR

DB_PATH = str(APP_DIR / "lancedb")
TABLE_NAME = "files"

# Schema for our vector database
SCHEMA = pa.schema([
    pa.field("vector", pa.list_(pa.float32(), 384)), # 384 is MiniLM's dimension
    pa.field("filepath", pa.string()),
    pa.field("chunk_index", pa.int32()),
    pa.field("text", pa.string()),
    pa.field("mtime", pa.float64()),
    pa.field("size", pa.int64()),
])

class VectorStore:
    def __init__(self):
        self.db = lancedb.connect(DB_PATH)
        if TABLE_NAME not in self.db.table_names():
            self.db.create_table(TABLE_NAME, schema=SCHEMA)
        self.table = self.db.open_table(TABLE_NAME)

    def get_file_meta(self, filepath: str):
        """Checks if a file is already indexed and up-to-date."""
        try:
            results = self.table.search().where(f"filepath = '{filepath}'", select=["mtime", "size"]).limit(1).to_list()
            if results:
                return results[0]["mtime"], results[0]["size"]
        except Exception:
            pass
        return None, None

    def delete_file_chunks(self, filepath: str):
        """Removes existing chunks for a file before re-inserting."""
        try:
            self.table.delete(f"filepath = '{filepath}'")
        except Exception as e:
            print(f"[Vina] Delete warning for {filepath}: {e}")

    def add_chunks(self, chunks: list[dict]):
        """Inserts new chunks into the database."""
        if chunks:
            self.table.add(chunks)