from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vina.indexer.store import VECTOR_DIMENSION, VectorStore


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

@pytest.fixture
def store():
    """
    Create a VectorStore instance without opening a real LanceDB database.
    """
    store = VectorStore.__new__(VectorStore)

    store.db = MagicMock()
    store.table = MagicMock()

    return store


# ----------------------------------------------------------------------
# get_file_meta()
# ----------------------------------------------------------------------

def test_get_file_meta_success(store):
    store.table.search.return_value.where.return_value.select.return_value.limit.return_value.to_list.return_value = [
        {
            "mtime": 123.45,
            "size": 999,
        }
    ]

    mtime, size = store.get_file_meta("file.txt")

    assert mtime == 123.45
    assert size == 999


def test_get_file_meta_missing(store):
    store.table.search.return_value.where.return_value.select.return_value.limit.return_value.to_list.return_value = []

    assert store.get_file_meta("missing.txt") == (None, None)


def test_get_file_meta_database_failure(store):
    store.table.search.side_effect = RuntimeError("boom")

    assert store.get_file_meta("file.txt") == (None, None)


# ----------------------------------------------------------------------
# delete_file_chunks()
# ----------------------------------------------------------------------

def test_delete_chunks(store):
    store.delete_file_chunks("abc.txt")

    store.table.delete.assert_called_once()


def test_delete_chunks_database_failure(store):
    store.table.delete.side_effect = RuntimeError("database error")

    # Should not raise
    store.delete_file_chunks("abc.txt")


# ----------------------------------------------------------------------
# add_chunks()
# ----------------------------------------------------------------------

def test_add_single_chunk(store):
    chunk = {
        "vector": [0.0] * VECTOR_DIMENSION,
        "filepath": "file.txt",
        "chunk_index": 0,
        "text": "hello",
        "mtime": 1.0,
        "size": 10,
    }

    store.add_chunks([chunk])

    store.table.add.assert_called_once_with([chunk])


def test_add_multiple_chunks(store):
    chunks = []

    for i in range(5):
        chunks.append(
            {
                "vector": [float(i)] * VECTOR_DIMENSION,
                "filepath": "file.txt",
                "chunk_index": i,
                "text": f"text {i}",
                "mtime": 1.0,
                "size": 100,
            }
        )

    store.add_chunks(chunks)

    store.table.add.assert_called_once()


def test_add_empty_chunk_list(store):
    store.add_chunks([])

    store.table.add.assert_not_called()


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------

@pytest.mark.parametrize(
    "length",
    [
        0,
        1,
        100,
        383,
        385,
        500,
    ],
)
def test_invalid_vector_dimension(store, length):
    chunk = {
        "vector": [0.0] * length,
        "filepath": "file.txt",
        "chunk_index": 0,
        "text": "hello",
        "mtime": 1.0,
        "size": 100,
    }

    with pytest.raises(ValueError):
        store.add_chunks([chunk])


def test_none_vector(store):
    chunk = {
        "vector": None,
        "filepath": "file.txt",
        "chunk_index": 0,
        "text": "hello",
        "mtime": 1.0,
        "size": 100,
    }

    with pytest.raises(ValueError):
        store.add_chunks([chunk])


# ----------------------------------------------------------------------
# Database Failure
# ----------------------------------------------------------------------

def test_database_add_failure(store):
    store.table.add.side_effect = RuntimeError("write failure")

    chunk = {
        "vector": [0.0] * VECTOR_DIMENSION,
        "filepath": "file.txt",
        "chunk_index": 0,
        "text": "hello",
        "mtime": 1.0,
        "size": 100,
    }

    with pytest.raises(RuntimeError):
        store.add_chunks([chunk])