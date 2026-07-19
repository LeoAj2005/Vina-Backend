from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ----------------------------------------------------------------------
# Temporary Test Files
# ----------------------------------------------------------------------

@pytest.fixture
def sample_text() -> str:
    return (
        "Python is an interpreted programming language. "
        "It supports object-oriented programming and functional programming. "
        "Pytest is commonly used for automated testing."
    )


@pytest.fixture
def txt_file(tmp_path: Path) -> Path:
    file = tmp_path / "sample.txt"
    file.write_text(
        "Hello from pytest!\nThis is a temporary text file.",
        encoding="utf-8",
    )
    return file


@pytest.fixture
def json_file(tmp_path: Path) -> Path:
    file = tmp_path / "sample.json"

    file.write_text(
        json.dumps(
            {
                "name": "Vina",
                "version": "0.1.0",
                "language": "Python",
            }
        ),
        encoding="utf-8",
    )

    return file


@pytest.fixture
def invalid_pdf(tmp_path: Path) -> Path:
    """
    Creates a fake PDF.

    This intentionally does NOT contain a valid PDF header.
    Used to verify graceful error handling.
    """
    file = tmp_path / "broken.pdf"

    file.write_bytes(
        b"This is definitely not a PDF."
    )

    return file


# ----------------------------------------------------------------------
# Mock Embedding Model
# ----------------------------------------------------------------------

@pytest.fixture
def fake_embedding():
    """
    Returns one 384-dimensional embedding.
    """

    return [[0.1] * 384]


@pytest.fixture
def fake_embedder(monkeypatch):
    """
    Prevent FastEmbed from loading during tests.
    """

    from vina.indexer import embed

    monkeypatch.setattr(
        embed,
        "embed_texts",
        lambda texts, **kwargs: [[0.0] * 384 for _ in texts],
    )


# ----------------------------------------------------------------------
# Mock Vector Store
# ----------------------------------------------------------------------

@pytest.fixture
def mock_store():
    """
    Lightweight fake VectorStore.
    """

    store = MagicMock()

    store.table = MagicMock()

    store.get_file_meta.return_value = (None, None)

    store.add_chunks.return_value = None

    store.delete_file_chunks.return_value = None

    return store


# ----------------------------------------------------------------------
# Dummy Search Results
# ----------------------------------------------------------------------

@pytest.fixture
def fake_search_results():
    from vina.search.retrieve import SearchResult

    return [
        SearchResult(
            filepath="notes/python.txt",
            distance=0.15,
            text="Python is awesome.",
            chunk_index=0,
        ),
        SearchResult(
            filepath="notes/pytest.txt",
            distance=0.23,
            text="Pytest makes testing easy.",
            chunk_index=1,
        ),
    ]


# ----------------------------------------------------------------------
# Common Paths
# ----------------------------------------------------------------------

@pytest.fixture
def temp_directory(tmp_path: Path) -> Path:
    """
    Empty temporary directory for watcher/indexer tests.
    """
    return tmp_path