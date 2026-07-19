from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vina.search.retrieve import SearchResult, search_files


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

@pytest.fixture
def mock_store():
    store = MagicMock()
    store.table = MagicMock()
    return store


# ----------------------------------------------------------------------
# Empty Query
# ----------------------------------------------------------------------

def test_empty_query_returns_empty(mock_store):
    assert search_files("", store=mock_store) == []


def test_whitespace_query_returns_empty(mock_store):
    assert search_files("     ", store=mock_store) == []


# ----------------------------------------------------------------------
# VectorStore unavailable
# ----------------------------------------------------------------------

def test_table_none_returns_empty(mock_store):
    mock_store.table = None

    assert search_files("python", store=mock_store) == []


# ----------------------------------------------------------------------
# Embedding failure
# ----------------------------------------------------------------------

def test_embedding_returns_empty(monkeypatch, mock_store):
    monkeypatch.setattr(
        "vina.search.retrieve.embed_texts",
        lambda *_args, **_kwargs: [],
    )

    assert search_files("python", store=mock_store) == []


# ----------------------------------------------------------------------
# Database failure
# ----------------------------------------------------------------------

def test_database_exception(monkeypatch, mock_store):
    monkeypatch.setattr(
        "vina.search.retrieve.embed_texts",
        lambda *_args, **_kwargs: [[0.0] * 384],
    )

    mock_store.table.search.side_effect = RuntimeError()

    assert search_files("python", store=mock_store) == []


# ----------------------------------------------------------------------
# No search results
# ----------------------------------------------------------------------

def test_no_results(monkeypatch, mock_store):
    monkeypatch.setattr(
        "vina.search.retrieve.embed_texts",
        lambda *_args, **_kwargs: [[0.0] * 384],
    )

    (
        mock_store.table
        .search.return_value
        .select.return_value
        .limit.return_value
        .to_list.return_value
    ) = []

    assert search_files("python", store=mock_store) == []


# ----------------------------------------------------------------------
# Single Result
# ----------------------------------------------------------------------

def test_single_result(monkeypatch, mock_store):
    monkeypatch.setattr(
        "vina.search.retrieve.embed_texts",
        lambda *_args, **_kwargs: [[0.0] * 384],
    )

    (
        mock_store.table
        .search.return_value
        .select.return_value
        .limit.return_value
        .to_list.return_value
    ) = [
        {
            "filepath": "notes.txt",
            "text": "Python",
            "chunk_index": 0,
            "_distance": 0.15,
        }
    ]

    results = search_files(
        "python",
        store=mock_store,
    )

    assert len(results) == 1

    result = results[0]

    assert isinstance(result, SearchResult)

    assert result.filepath == "notes.txt"
    assert result.text == "Python"
    assert result.chunk_index == 0
    assert result.distance == 0.15


# ----------------------------------------------------------------------
# Deduplication
# ----------------------------------------------------------------------

def test_duplicate_file_collapses(monkeypatch, mock_store):
    monkeypatch.setattr(
        "vina.search.retrieve.embed_texts",
        lambda *_args, **_kwargs: [[0.0] * 384],
    )

    (
        mock_store.table
        .search.return_value
        .select.return_value
        .limit.return_value
        .to_list.return_value
    ) = [
        {
            "filepath": "a.txt",
            "text": "chunk1",
            "chunk_index": 0,
            "_distance": 0.10,
        },
        {
            "filepath": "a.txt",
            "text": "chunk2",
            "chunk_index": 1,
            "_distance": 0.20,
        },
    ]

    results = search_files(
        "python",
        store=mock_store,
    )

    assert len(results) == 1
    assert results[0].text == "chunk1"


# ----------------------------------------------------------------------
# Limit
# ----------------------------------------------------------------------

def test_limit(monkeypatch, mock_store):
    monkeypatch.setattr(
        "vina.search.retrieve.embed_texts",
        lambda *_args, **_kwargs: [[0.0] * 384],
    )

    rows = []

    for i in range(20):
        rows.append(
            {
                "filepath": f"{i}.txt",
                "text": f"text{i}",
                "chunk_index": 0,
                "_distance": float(i),
            }
        )

    (
        mock_store.table
        .search.return_value
        .select.return_value
        .limit.return_value
        .to_list.return_value
    ) = rows

    results = search_files(
        "python",
        limit=5,
        store=mock_store,
    )

    assert len(results) == 5


# ----------------------------------------------------------------------
# Missing filepath rows
# ----------------------------------------------------------------------

def test_missing_filepath_is_skipped(monkeypatch, mock_store):
    monkeypatch.setattr(
        "vina.search.retrieve.embed_texts",
        lambda *_args, **_kwargs: [[0.0] * 384],
    )

    (
        mock_store.table
        .search.return_value
        .select.return_value
        .limit.return_value
        .to_list.return_value
    ) = [
        {
            "filepath": "",
            "text": "bad",
            "chunk_index": 0,
            "_distance": 0.1,
        },
        {
            "filepath": "good.txt",
            "text": "good",
            "chunk_index": 1,
            "_distance": 0.2,
        },
    ]

    results = search_files(
        "python",
        store=mock_store,
    )

    assert len(results) == 1
    assert results[0].filepath == "good.txt"