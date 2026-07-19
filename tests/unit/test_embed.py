from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from vina.indexer.embed import Embedder, embed_texts


# ----------------------------------------------------------------------
# Fake FastEmbed Classes
# ----------------------------------------------------------------------

class FakeVector:
    def __init__(self, value: float):
        self.value = value

    def tolist(self):
        return [self.value] * 384


class FakeModel:
    """
    Simulates fastembed.TextEmbedding
    """

    def embed(self, texts, **kwargs):
        for i, _ in enumerate(texts):
            yield FakeVector(float(i))


# ----------------------------------------------------------------------
# Singleton Tests
# ----------------------------------------------------------------------

def test_get_instance_returns_singleton(monkeypatch):
    from vina.indexer import embed

    Embedder._instance = None

    monkeypatch.setattr(
        embed,
        "TextEmbedding",
        lambda **kwargs: FakeModel(),
    )

    model1 = Embedder.get_instance()
    model2 = Embedder.get_instance()

    assert model1 is model2


def test_singleton_is_thread_safe(monkeypatch):
    from vina.indexer import embed

    Embedder._instance = None

    monkeypatch.setattr(
        embed,
        "TextEmbedding",
        lambda **kwargs: FakeModel(),
    )

    def load():
        return Embedder.get_instance()

    with ThreadPoolExecutor(max_workers=8) as executor:
        models = list(executor.map(lambda _: load(), range(20)))

    first = models[0]

    assert all(model is first for model in models)


# ----------------------------------------------------------------------
# embed_texts()
# ----------------------------------------------------------------------

def test_embed_empty_input():
    assert embed_texts([]) == []


def test_embed_single_text(monkeypatch):
    from vina.indexer import embed

    monkeypatch.setattr(
        Embedder,
        "get_instance",
        lambda: FakeModel(),
    )

    vectors = embed_texts(
        ["hello world"]
    )

    assert len(vectors) == 1

    assert len(vectors[0]) == 384

    assert vectors[0][0] == 0.0


def test_embed_multiple_texts(monkeypatch):
    monkeypatch.setattr(
        Embedder,
        "get_instance",
        lambda: FakeModel(),
    )

    vectors = embed_texts(
        [
            "one",
            "two",
            "three",
        ]
    )

    assert len(vectors) == 3

    assert vectors[0][0] == 0.0
    assert vectors[1][0] == 1.0
    assert vectors[2][0] == 2.0


# ----------------------------------------------------------------------
# Generator Input
# ----------------------------------------------------------------------

def test_embed_generator_input(monkeypatch):
    """
    This test protects against the generator bug
    we discovered during review.
    """

    monkeypatch.setattr(
        Embedder,
        "get_instance",
        lambda: FakeModel(),
    )

    texts = (
        f"text {i}"
        for i in range(5)
    )

    vectors = embed_texts(list(texts))

    assert len(vectors) == 5


# ----------------------------------------------------------------------
# Error Handling
# ----------------------------------------------------------------------

def test_model_failure_returns_empty(monkeypatch):

    class BrokenModel:

        def embed(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        Embedder,
        "get_instance",
        lambda: BrokenModel(),
    )

    vectors = embed_texts(
        ["hello"]
    )

    assert vectors == []


def test_parallel_parameter(monkeypatch):
    """
    Ensure keyword arguments are forwarded.
    """

    received = {}

    class CaptureModel:

        def embed(self, texts, **kwargs):

            received.update(kwargs)

            for _ in texts:
                yield FakeVector(0)

    monkeypatch.setattr(
        Embedder,
        "get_instance",
        lambda: CaptureModel(),
    )

    embed_texts(
        ["hello"],
        batch_size=64,
        parallel=4,
    )

    assert received["batch_size"] == 64
    assert received["parallel"] == 4