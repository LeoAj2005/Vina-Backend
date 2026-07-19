from __future__ import annotations

import logging
from typing import Any, Optional

import lancedb
from lancedb.expr import col, lit
import pyarrow as pa

from ..config import APP_DIR

logger = logging.getLogger("vina.store")

DB_PATH = str(APP_DIR / "lancedb")
TABLE_NAME = "files"
VECTOR_DIMENSION = 384

# Schema blueprint for our LanceDB vector storage layer.
# Using explicit fixed_size_list guarantees exact dimension compliance at the database kernel layer.
SCHEMA = pa.schema([
    pa.field("vector", pa.list_(pa.float32(), VECTOR_DIMENSION)),
    pa.field("filepath", pa.string()),
    pa.field("chunk_index", pa.int32()),
    pa.field("text", pa.string()),
    pa.field("mtime", pa.float64()),
    pa.field("size", pa.int64()),
])


class VectorStore:
    """
    High-performance vector database interface leveraging LanceDB and PyArrow.
    Handles embedding storage, metadata lookups, and programmatic chunk deletions.
    """

    def __init__(self) -> None:
        try:
            self.db = lancedb.connect(DB_PATH)
            if TABLE_NAME not in self.db.table_names():
                logger.info("Database table '%s' not found. Materializing new instance with target schema.", TABLE_NAME)
                self.db.create_table(TABLE_NAME, schema=SCHEMA)
            
            self.table = self.db.open_table(TABLE_NAME)
        except Exception:
            logger.exception("Fatal initialization failure within the LanceDB storage matrix engine.")
            raise

    def get_file_meta(self, filepath: str) -> tuple[Optional[float], Optional[int]]:
        """
        Checks if a file is already indexed and extracts its file attributes.
        Returns a tuple of (mtime, size). Returns (None, None) if missing or unindexed.
        """
        try:
            # Type-safe expression builder bypasses manual string quote manipulation entirely
            results = (
                self.table
                .search()
                .where(col("filepath") == lit(filepath))
                .select(["mtime", "size"])
                .limit(1)
                .to_list()
            )
            
            if results and "mtime" in results[0] and "size" in results[0]:
                row = results[0]
                return float(row["mtime"]), int(row["size"])
                
        except Exception as err:
            logger.error("Failed to extract filesystem metadata vectors for target path: %s. Error: %s", filepath, err)
            
        return None, None

    def delete_file_chunks(self, filepath: str) -> None:
        """Removes all historical text chunk vector payloads mapped to a specific file path."""
        try:
            logger.debug("Evicting vector chunks for file index target: %s", filepath)
            # Programmatic filtering handles strange directory character matrices cleanly
            self.table.delete(col("filepath") == lit(filepath))
        except Exception:
            logger.exception("Structural database deletion failure targeting file vector blocks: %s", filepath)

    def add_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """
        Inserts processed text chunk records and target embeddings into LanceDB.
        Performs explicit validation checks on vector array constraints.
        """
        if not chunks:
            logger.warning("Invocation of add_chunks bypassed due to empty data collection payload.")
            return

        # Pre-flight Dimension Diagnostic Check
        for idx, chunk in enumerate(chunks):
            vector = chunk.get("vector")
            if vector is None or len(vector) != VECTOR_DIMENSION:
                actual_dim = len(vector) if vector is not None else 0
                logger.error(
                    "Vector dimension boundary error at index %d! Expected exactly %d elements, but received %d.",
                    idx, VECTOR_DIMENSION, actual_dim
                )
                raise ValueError(
                    f"Malformed vector chunk dimension at index {idx}. Expected {VECTOR_DIMENSION}, got {actual_dim}."
                )

        try:
            logger.debug("Committing %d vector payloads to LanceDB storage record layers.", len(chunks))
            self.table.add(chunks)
        except Exception:
            logger.exception("Database transaction execution aborted during data batch insertion.")
            raise