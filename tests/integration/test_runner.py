from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import vina.indexer.runner as runner


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

@pytest.fixture
def mock_store():
    store = MagicMock()
    return store


# ----------------------------------------------------------------------
# process_file()
# ----------------------------------------------------------------------

def test_process_file_success(monkeypatch, mock_store):
    monkeypatch.setattr(
        runner,
        "extract_text",
        lambda _: "hello world"
    )

    monkeypatch.setattr(
        runner,
        "chunk_text",
        lambda _: ["chunk1", "chunk2"]
    )

    monkeypatch.setattr(
        runner,
        "embed_texts",
        lambda _: [[0.0] * 384, [1.0] * 384]
    )

    result = runner.process_file(
        filepath="notes.txt",
        mtime=1.0,
        size=100,
        store=mock_store,
    )

    assert result == 2

    mock_store.delete_file_chunks.assert_called_once_with("notes.txt")
    mock_store.add_chunks.assert_called_once()


def test_process_file_empty_extraction(monkeypatch, mock_store):
    monkeypatch.setattr(
        runner,
        "extract_text",
        lambda _: ""
    )

    result = runner.process_file(
        "notes.txt",
        mtime=1,
        size=1,
        store=mock_store,
    )

    assert result == 0

    mock_store.add_chunks.assert_not_called()


def test_process_file_no_chunks(monkeypatch, mock_store):
    monkeypatch.setattr(
        runner,
        "extract_text",
        lambda _: "hello"
    )

    monkeypatch.setattr(
        runner,
        "chunk_text",
        lambda _: []
    )

    result = runner.process_file(
        "notes.txt",
        mtime=1,
        size=1,
        store=mock_store,
    )

    assert result == 0

    mock_store.add_chunks.assert_not_called()


def test_process_file_embedding_mismatch(monkeypatch, mock_store):
    monkeypatch.setattr(
        runner,
        "extract_text",
        lambda _: "hello"
    )

    monkeypatch.setattr(
        runner,
        "chunk_text",
        lambda _: ["a", "b", "c"]
    )

    monkeypatch.setattr(
        runner,
        "embed_texts",
        lambda _: [[0.0] * 384]
    )

    result = runner.process_file(
        "notes.txt",
        mtime=1,
        size=1,
        store=mock_store,
    )

    assert result == 0

    mock_store.add_chunks.assert_not_called()


def test_process_file_file_not_found(monkeypatch, mock_store):
    monkeypatch.setattr(
        runner.os,
        "stat",
        lambda *_: (_ for _ in ()).throw(FileNotFoundError())
    )

    result = runner.process_file(
        "missing.txt",
        store=mock_store,
    )

    assert result == 0


def test_process_file_store_failure(monkeypatch, mock_store):
    monkeypatch.setattr(
        runner,
        "extract_text",
        lambda _: "hello"
    )

    monkeypatch.setattr(
        runner,
        "chunk_text",
        lambda _: ["chunk"]
    )

    monkeypatch.setattr(
        runner,
        "embed_texts",
        lambda _: [[0.0] * 384]
    )

    mock_store.add_chunks.side_effect = RuntimeError("boom")

    result = runner.process_file(
        "notes.txt",
        mtime=1,
        size=1,
        store=mock_store,
    )

    assert result == 0


def test_process_file_skips_os_stat_when_metadata_supplied(monkeypatch, mock_store):
    called = False

    def fake_stat(*args):
        nonlocal called
        called = True
        raise AssertionError("os.stat should not be called")

    monkeypatch.setattr(
        runner.os,
        "stat",
        fake_stat,
    )

    monkeypatch.setattr(
        runner,
        "extract_text",
        lambda _: ""
    )

    runner.process_file(
        "notes.txt",
        mtime=123,
        size=456,
        store=mock_store,
    )

    assert called is False


def test_process_file_record_contents(monkeypatch, mock_store):
    monkeypatch.setattr(
        runner,
        "extract_text",
        lambda _: "hello"
    )

    monkeypatch.setattr(
        runner,
        "chunk_text",
        lambda _: ["chunk"]
    )

    monkeypatch.setattr(
        runner,
        "embed_texts",
        lambda _: [[9.0] * 384]
    )

    runner.process_file(
        filepath="notes.txt",
        mtime=10,
        size=20,
        store=mock_store,
    )

    records = mock_store.add_chunks.call_args.args[0]

    assert len(records) == 1

    record = records[0]

    assert record["filepath"] == "notes.txt"
    assert record["chunk_index"] == 0
    assert record["mtime"] == 10
    assert record["size"] == 20
    assert record["text"] == "chunk"

    assert len(record["vector"]) == 384
    
# ----------------------------------------------------------------------
# delete_file()
# ----------------------------------------------------------------------

def test_delete_file_success(mock_store):
    runner.delete_file(
        "notes.txt",
        store=mock_store,
    )

    mock_store.delete_file_chunks.assert_called_once_with("notes.txt")


def test_delete_file_store_failure(mock_store):
    mock_store.delete_file_chunks.side_effect = RuntimeError("boom")

    # Should not propagate
    runner.delete_file(
        "notes.txt",
        store=mock_store,
    )

    mock_store.delete_file_chunks.assert_called_once()

# ----------------------------------------------------------------------
# run_indexer()
# ----------------------------------------------------------------------

from pathlib import Path


def test_run_indexer_missing_folder(monkeypatch, mock_store):
    fake = MagicMock()
    fake.exists.return_value = False

    monkeypatch.setattr(
        runner,
        "Path",
        lambda *_: fake,
    )

    runner.run_indexer(
        "D:/missing",
        store=mock_store,
    )


def test_run_indexer_skips_unsupported_extension(monkeypatch, mock_store):
    monkeypatch.setattr(
        runner.os,
        "walk",
        lambda *_: [
            ("root", [], ["image.png"])
        ],
    )

    fake_path = MagicMock()
    fake_path.exists.return_value = True
    fake_path.resolve.return_value = fake_path

    monkeypatch.setattr(
        runner,
        "Path",
        lambda *_: fake_path,
    )

    runner.run_indexer(
        "root",
        store=mock_store,
    )

    mock_store.get_file_meta.assert_not_called()


def test_run_indexer_skips_unchanged_file(monkeypatch, mock_store):
    monkeypatch.setattr(
        runner.os,
        "walk",
        lambda *_: [
            ("root", [], ["notes.txt"])
        ],
    )

    stat = MagicMock()
    stat.st_mtime = 100
    stat.st_size = 200

    monkeypatch.setattr(
        runner.os,
        "stat",
        lambda *_: stat,
    )

    fake_path = MagicMock()
    fake_path.exists.return_value = True
    fake_path.resolve.return_value = fake_path
    fake_path.as_posix.return_value = "root/notes.txt"

    monkeypatch.setattr(
        runner,
        "Path",
        lambda *_: fake_path,
    )

    mock_store.get_file_meta.return_value = (
        100,
        200,
    )

    runner.run_indexer(
        "root",
        store=mock_store,
    )

    mock_store.get_file_meta.assert_called_once()


def test_run_indexer_processes_changed_file(monkeypatch, mock_store):
    monkeypatch.setattr(
        runner.os,
        "walk",
        lambda *_: [
            ("root", [], ["notes.txt"])
        ],
    )

    stat = MagicMock()
    stat.st_mtime = 100
    stat.st_size = 200

    monkeypatch.setattr(
        runner.os,
        "stat",
        lambda *_: stat,
    )

    fake_path = MagicMock()
    fake_path.exists.return_value = True
    fake_path.resolve.return_value = fake_path
    fake_path.as_posix.return_value = "root/notes.txt"

    monkeypatch.setattr(
        runner,
        "Path",
        lambda *_: fake_path,
    )

    mock_store.get_file_meta.return_value = (
        None,
        None,
    )

    called = {}

    def fake_process(**kwargs):
        called.update(kwargs)
        return 1

    monkeypatch.setattr(
        runner,
        "process_file",
        fake_process,
    )

    runner.run_indexer(
        "root",
        store=mock_store,
    )

    assert called["filepath"] == "root/notes.txt"
    assert called["mtime"] == 100
    assert called["size"] == 200
    assert called["store"] is mock_store


def test_run_indexer_file_removed_during_scan(monkeypatch, mock_store):
    monkeypatch.setattr(
        runner.os,
        "walk",
        lambda *_: [
            ("root", [], ["notes.txt"])
        ],
    )

    monkeypatch.setattr(
        runner.os,
        "stat",
        lambda *_: (_ for _ in ()).throw(FileNotFoundError()),
    )

    fake_path = MagicMock()
    fake_path.exists.return_value = True
    fake_path.resolve.return_value = fake_path
    fake_path.as_posix.return_value = "root/notes.txt"

    monkeypatch.setattr(
        runner,
        "Path",
        lambda *_: fake_path,
    )

    runner.run_indexer(
        "root",
        store=mock_store,
    )


def test_run_indexer_continues_after_processing_error(monkeypatch, mock_store):
    monkeypatch.setattr(
        runner.os,
        "walk",
        lambda *_: [
            ("root", [], ["notes.txt"])
        ],
    )

    stat = MagicMock()
    stat.st_mtime = 1
    stat.st_size = 2

    monkeypatch.setattr(
        runner.os,
        "stat",
        lambda *_: stat,
    )

    fake_path = MagicMock()
    fake_path.exists.return_value = True
    fake_path.resolve.return_value = fake_path
    fake_path.as_posix.return_value = "root/notes.txt"

    monkeypatch.setattr(
        runner,
        "Path",
        lambda *_: fake_path,
    )

    mock_store.get_file_meta.side_effect = RuntimeError()

    # Should not raise
    runner.run_indexer(
        "root",
        store=mock_store,
    )