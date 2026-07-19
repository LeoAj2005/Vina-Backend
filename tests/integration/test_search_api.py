from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

import vina.server as server


client = TestClient(server.app)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

@dataclass
class FakeResult:
    filepath: str
    distance: float
    text: str


@pytest.fixture
def auth_header():
    return {
        "X-Vina-Token": server._CACHED_TOKEN
    }


# ----------------------------------------------------------------------
# /api/health
# ----------------------------------------------------------------------

def test_health():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok"
    }


# ----------------------------------------------------------------------
# verify_token()
# ----------------------------------------------------------------------

def test_search_requires_token():
    response = client.get(
        "/api/search",
        params={"query": "python"},
    )

    assert response.status_code == 403


def test_search_rejects_invalid_token():
    response = client.get(
        "/api/search",
        params={"query": "python"},
        headers={
            "X-Vina-Token": "wrong-token"
        },
    )

    assert response.status_code == 403


# ----------------------------------------------------------------------
# Empty Query
# ----------------------------------------------------------------------

def test_empty_query(auth_header):
    response = client.get(
        "/api/search",
        params={"query": ""},
        headers=auth_header,
    )

    assert response.status_code == 400


def test_whitespace_query(auth_header):
    response = client.get(
        "/api/search",
        params={"query": "      "},
        headers=auth_header,
    )

    assert response.status_code == 400


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------

@pytest.mark.parametrize(
    "limit",
    [
        0,
        -1,
        101,
    ],
)
def test_invalid_limit(limit, auth_header):
    response = client.get(
        "/api/search",
        params={
            "query": "python",
            "limit": limit,
        },
        headers=auth_header,
    )

    assert response.status_code == 422


# ----------------------------------------------------------------------
# Successful Search
# ----------------------------------------------------------------------

def test_search_success(monkeypatch, auth_header):
    monkeypatch.setattr(
        server,
        "search_files",
        lambda query, limit=10: [
            FakeResult(
                filepath="notes.txt",
                distance=0.15,
                text="Python is awesome",
            )
        ],
    )

    response = client.get(
        "/api/search",
        params={"query": "python"},
        headers=auth_header,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["query"] == "python"
    assert body["count"] == 1

    result = body["results"][0]

    assert result["filepath"] == "notes.txt"
    assert result["score"] == 0.15
    assert result["excerpt"] == "Python is awesome"


def test_search_truncates_excerpt(monkeypatch, auth_header):
    monkeypatch.setattr(
        server,
        "search_files",
        lambda query, limit=10: [
            FakeResult(
                filepath="long.txt",
                distance=0.2,
                text="A" * 300,
            )
        ],
    )

    response = client.get(
        "/api/search",
        params={"query": "python"},
        headers=auth_header,
    )

    assert response.status_code == 200

    excerpt = response.json()["results"][0]["excerpt"]

    assert len(excerpt) == 203
    assert excerpt.endswith("...")


def test_search_returns_empty_results(monkeypatch, auth_header):
    monkeypatch.setattr(
        server,
        "search_files",
        lambda query, limit=10: [],
    )

    response = client.get(
        "/api/search",
        params={"query": "python"},
        headers=auth_header,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["count"] == 0
    assert body["results"] == []