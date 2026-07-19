from __future__ import annotations

import pytest

from vina.indexer.chunk import chunk_text


# ----------------------------------------------------------------------
# Basic Behaviour
# ----------------------------------------------------------------------

def test_empty_text_returns_no_chunks():
    chunks = list(chunk_text(""))
    assert chunks == []


def test_short_document_returns_single_chunk():
    text = "Python makes testing easy."

    chunks = list(chunk_text(text))

    assert len(chunks) == 1
    assert chunks[0] == text


def test_exact_window_returns_single_chunk():
    text = " ".join(f"word{i}" for i in range(400))

    chunks = list(chunk_text(text))

    assert len(chunks) == 1


# ----------------------------------------------------------------------
# Sliding Window Behaviour
# ----------------------------------------------------------------------

def test_large_document_produces_multiple_chunks():
    text = " ".join(f"word{i}" for i in range(1000))

    chunks = list(chunk_text(text))

    assert len(chunks) > 1


def test_overlap_is_preserved():
    words = [f"word{i}" for i in range(500)]
    text = " ".join(words)

    chunks = list(chunk_text(text))

    assert len(chunks) == 2

    first = chunks[0].split()
    second = chunks[1].split()

    # Last 50 words of first chunk
    overlap1 = first[-50:]

    # First 50 words of second chunk
    overlap2 = second[:50]

    assert overlap1 == overlap2


# ----------------------------------------------------------------------
# Generator Behaviour
# ----------------------------------------------------------------------

def test_returns_generator():
    result = chunk_text("hello world")

    assert hasattr(result, "__iter__")
    assert not isinstance(result, list)


def test_generator_can_be_consumed_once():
    gen = chunk_text("hello world")

    first = list(gen)
    second = list(gen)

    assert len(first) == 1
    assert second == []


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------

@pytest.mark.parametrize(
    "max_words, overlap",
    [
        (0, 0),
        (-1, 0),
    ],
)
def test_invalid_max_words(max_words, overlap):
    with pytest.raises(ValueError):
        list(chunk_text("hello world", max_words=max_words, overlap=overlap))


@pytest.mark.parametrize(
    "max_words, overlap",
    [
        (100, -1),
        (100, 100),
        (100, 101),
    ],
)
def test_invalid_overlap(max_words, overlap):
    with pytest.raises(ValueError):
        list(chunk_text("hello world", max_words=max_words, overlap=overlap))


# ----------------------------------------------------------------------
# Parameterized Chunk Counts
# ----------------------------------------------------------------------

@pytest.mark.parametrize(
    "word_count, expected_chunks",
    [
        (1, 1),
        (100, 1),
        (399, 1),
        (400, 1),
        (401, 2),
        (750, 2),
        (1000, 3),
    ],
)
def test_expected_chunk_count(word_count, expected_chunks):
    text = " ".join(f"w{i}" for i in range(word_count))

    chunks = list(chunk_text(text))

    assert len(chunks) == expected_chunks


# ----------------------------------------------------------------------
# Content Integrity
# ----------------------------------------------------------------------

def test_chunk_contains_original_words():
    text = " ".join(f"word{i}" for i in range(600))

    chunks = list(chunk_text(text))

    reconstructed = " ".join(chunks)

    for word in [
        "word0",
        "word50",
        "word200",
        "word399",
        "word550",
        "word599",
    ]:
        assert word in reconstructed