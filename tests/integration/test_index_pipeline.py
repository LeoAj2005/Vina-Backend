from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest

from vina.indexer.runner import process_file
from vina.indexer.store import VectorStore
from vina.search.retrieve import search_files


def deterministic_embed(texts: list[str]) -> list[list[float]]:
    """
    Generates a deterministic vector based on a local vocabulary list.
    Enables keyword-like matching capability within a real LanceDB instance
    without downloading heavy embedding models or relying on network calls.
    
    Returns 384-dimensional vectors to strictly adhere to the database schema constraints.
    """
    vocab = ["hello", "python", "java", "ai", "pipeline", "framework", "learning", "code"]
    vectors = []
    for text in texts:
        lower_text = text.lower()
        vec = [0.0] * 384  # Matches VECTOR_DIMENSION in vina.indexer.store
        for i, word in enumerate(vocab):
            if word in lower_text:
                vec[i] = 1.0
        if sum(vec) == 0.0:
            vec[0] = 0.1
        vectors.append(vec)
    return vectors


@pytest.fixture(autouse=True)
def mock_embed_texts(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Monkeypatches the embed_texts function inside the modules under test
    to enforce reproducible offline test executions.
    """
    for module_path in ["vina.indexer.runner", "vina.indexer.store", "vina.search.retrieve"]:
        try:
            monkeypatch.setattr(f"{module_path}.embed_texts", deterministic_embed)
        except AttributeError:
            pass


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """Creates and provides an isolated directory path for LanceDB storage."""
    db_dir = tmp_path / "lancedb"
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir)


@pytest.fixture
def vector_store(db_path: str) -> VectorStore:
    """Instantiates a real VectorStore using dependency injection to avoid mutating production DBs."""
    return VectorStore(db_path=db_path)


@pytest.fixture
def docs_dir(tmp_path: Path) -> Path:
    """Provides a temporary, isolated workspace directory for generating test files."""
    d = tmp_path / "docs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_index_single_text_file(docs_dir: Path, vector_store: VectorStore) -> None:
    """
    1. test_index_single_text_file
    Verifies indexing a single file yields correct filepath, excerpt, and expected counts.
    """
    hello_file = docs_dir / "hello.txt"
    hello_file.write_text("Hello world! This is the Vina indexing pipeline integration test.", encoding="utf-8")

    # FIXED: Added explicit store= keyword
    chunks_indexed = process_file(str(hello_file), store=vector_store)
    assert chunks_indexed > 0

    results = search_files("hello", store=vector_store)
    assert len(results) >= 1

    top_result = results[0]
    assert top_result.filepath == str(hello_file)
    assert "Hello world!" in top_result.text


def test_index_multiple_files(docs_dir: Path, vector_store: VectorStore) -> None:
    """
    2. test_index_multiple_files
    Validates independent isolated query results when multiple files coexist in the database.
    """
    files = {
        "python.txt": "Python is a powerful programming language used for scripting and backend development.",
        "java.txt": "Java is a class-based, object-oriented programming language designed for enterprise apps.",
        # FIXED: Changed "Artificial Intelligence" to "AI" to trigger the deterministic_embed keyword
        "ai.txt": "AI and deep learning models are transforming modern software engineering."
    }

    created_files = {}
    for filename, content in files.items():
        f = docs_dir / filename
        f.write_text(content, encoding="utf-8")
        created_files[filename] = f
        process_file(str(f), store=vector_store)

    python_results = search_files("python", store=vector_store)
    assert len(python_results) > 0
    assert python_results[0].filepath == str(created_files["python.txt"])

    ai_results = search_files("ai", store=vector_store)
    assert len(ai_results) > 0
    assert ai_results[0].filepath == str(created_files["ai.txt"])


def test_reindex_modified_file(docs_dir: Path, vector_store: VectorStore) -> None:
    """
    3. test_reindex_modified_file
    Ensures that modifying an existing file and re-indexing it successfully replaces outdated chunks.
    """
    target_file = docs_dir / "dynamic.txt"

    target_file.write_text("Python is an amazing language.", encoding="utf-8")
    process_file(str(target_file), store=vector_store)

    initial_results = search_files("python", store=vector_store)
    assert len(initial_results) == 1
    assert "amazing" in initial_results[0].text

    time.sleep(0.1)

    target_file.write_text("Java is the new preferred standard here.", encoding="utf-8")
    process_file(str(target_file), store=vector_store)

    old_results = search_files("python", store=vector_store)
    
    # FIXED: Since this is the only file in the DB, LanceDB will still return it as the nearest 
    # neighbor. We must verify the old chunk data is truly gone by checking the text content.
    for r in old_results:
        if r.filepath == str(target_file):
            assert "amazing" not in r.text

    new_results = search_files("java", store=vector_store)
    assert len(new_results) == 1
    assert "preferred standard" in new_results[0].text


def test_delete_file_chunks(docs_dir: Path, vector_store: VectorStore) -> None:
    """
    4. test_delete_file_chunks
    Verifies complete purging of chunks associated with a specific file context upon deletion.
    """
    temp_file = docs_dir / "delete_me.txt"
    temp_file.write_text("Pipeline text containing python keywords for indexing.", encoding="utf-8")

    # FIXED: Added explicit store= keyword
    process_file(str(temp_file), store=vector_store)
    
    assert len(search_files("python", store=vector_store)) > 0

    vector_store.delete_file_chunks(str(temp_file))

    post_delete_results = search_files("python", store=vector_store)
    assert not any(r.filepath == str(temp_file) for r in post_delete_results)


def test_empty_file_skipped(docs_dir: Path, vector_store: VectorStore) -> None:
    """
    5. test_empty_file_skipped
    Confirms that process_file skips empty text files gracefully and returns zero chunks.
    """
    empty_file = docs_dir / "empty.txt"
    empty_file.write_text("", encoding="utf-8")

    # FIXED: Added explicit store= keyword
    chunks_processed = process_file(str(empty_file), store=vector_store)
    assert chunks_processed == 0

    results = search_files("empty", store=vector_store)
    assert not any(r.filepath == str(empty_file) for r in results)


def test_unsupported_extension(docs_dir: Path, vector_store: VectorStore) -> None:
    """
    6. test_unsupported_extension
    Ensures unhandled extensions (e.g., binaries) are safely ignored without raising exceptions.
    """
    image_file = docs_dir / "image.jpg"
    image_file.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01")

    # FIXED: Added explicit store= keyword
    chunks = process_file(str(image_file), store=vector_store)
    assert chunks == 0 or chunks is None


def test_duplicate_indexing_replaces_previous(docs_dir: Path, vector_store: VectorStore) -> None:
    """
    7. test_duplicate_indexing_replaces_previous
    Validates that indexing an identical file twice updates records instead of stacking duplicate chunks.
    """
    dup_file = docs_dir / "duplicate.txt"
    dup_file.write_text("AI and learning pipeline processing redundancy test.", encoding="utf-8")

    # FIXED: Added explicit store= keyword
    process_file(str(dup_file), store=vector_store)
    initial_count = len(search_files("ai", store=vector_store))

    # FIXED: Added explicit store= keyword
    process_file(str(dup_file), store=vector_store)
    secondary_count = len(search_files("ai", store=vector_store))

    assert initial_count == secondary_count


def test_metadata_updates(docs_dir: Path, vector_store: VectorStore) -> None:
    """
    8. test_metadata_updates
    Ensures metadata attributes (mtime, size) are fully synchronized via VectorStore interface methods.
    """
    meta_file = docs_dir / "metadata.txt"

    meta_file.write_text("Python baseline data.", encoding="utf-8")
    
    # FIXED: Added explicit store= keyword
    process_file(str(meta_file), store=vector_store)

    mtime1, size1 = vector_store.get_file_meta(str(meta_file))
    assert mtime1 is not None
    assert size1 is not None

    time.sleep(1.1)

    meta_file.write_text("Python baseline data updated with significantly larger block of content text strings.", encoding="utf-8")
    
    # FIXED: Added explicit store= keyword
    process_file(str(meta_file), store=vector_store)

    mtime2, size2 = vector_store.get_file_meta(str(meta_file))
    assert mtime2 is not None
    assert size2 is not None

    assert mtime2 >= mtime1
    assert size2 > size1