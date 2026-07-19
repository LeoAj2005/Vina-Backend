from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import vina.indexer.watcher as watcher


# ----------------------------------------------------------------------
# Fake Timer
# ----------------------------------------------------------------------

class FakeTimer:
    def __init__(self, interval, func, args=()):
        self.interval = interval
        self.func = func
        self.args = args

        self.started = False
        self.cancelled = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

@pytest.fixture
def handler():
    return watcher.VinaEventHandler(
        debounce_interval_seconds=0.1
    )


# ----------------------------------------------------------------------
# _get_clean_path()
# ----------------------------------------------------------------------

def test_get_clean_path(handler):
    path = handler._get_clean_path("folder/../folder/file.txt")

    assert path.endswith("folder/file.txt")
    assert "\\" not in path


# ----------------------------------------------------------------------
# _debounce_process()
# ----------------------------------------------------------------------

def test_debounce_creates_timer(monkeypatch, handler):
    monkeypatch.setattr(
        watcher.threading,
        "Timer",
        FakeTimer,
    )

    handler._debounce_process("a.txt")

    assert "a.txt" in handler._timers

    timer = handler._timers["a.txt"]

    assert timer.started
    assert timer.interval == 0.1


def test_debounce_replaces_existing_timer(monkeypatch, handler):
    monkeypatch.setattr(
        watcher.threading,
        "Timer",
        FakeTimer,
    )

    handler._debounce_process("a.txt")

    first = handler._timers["a.txt"]

    handler._debounce_process("a.txt")

    second = handler._timers["a.txt"]

    assert first.cancelled
    assert second is not first


# ----------------------------------------------------------------------
# _execute_and_clear()
# ----------------------------------------------------------------------

def test_execute_process(monkeypatch, handler):
    called = {}

    monkeypatch.setattr(
        watcher,
        "process_file",
        lambda path: called.setdefault("path", path),
    )

    handler._timers["notes.txt"] = FakeTimer(
        0,
        lambda: None,
    )

    handler._execute_and_clear(
        "notes.txt",
        False,
    )

    assert called["path"] == "notes.txt"

    assert "notes.txt" not in handler._timers


def test_execute_delete(monkeypatch, handler):
    called = {}

    monkeypatch.setattr(
        watcher,
        "delete_file",
        lambda path: called.setdefault("path", path),
    )

    handler._timers["notes.txt"] = FakeTimer(
        0,
        lambda: None,
    )

    handler._execute_and_clear(
        "notes.txt",
        True,
    )

    assert called["path"] == "notes.txt"

    assert "notes.txt" not in handler._timers


def test_execute_handles_exception(monkeypatch, handler):
    monkeypatch.setattr(
        watcher,
        "process_file",
        lambda *_: (_ for _ in ()).throw(RuntimeError()),
    )

    handler._timers["bad.txt"] = FakeTimer(
        0,
        lambda: None,
    )

    # Should never raise
    handler._execute_and_clear(
        "bad.txt",
        False,
    )

    assert "bad.txt" not in handler._timers


# ----------------------------------------------------------------------
# stop_all_timers()
# ----------------------------------------------------------------------

def test_stop_all_timers(handler):
    t1 = FakeTimer(0, lambda: None)
    t2 = FakeTimer(0, lambda: None)

    handler._timers = {
        "a": t1,
        "b": t2,
    }

    handler.stop_all_timers()

    assert t1.cancelled
    assert t2.cancelled

    assert handler._timers == {}

# ----------------------------------------------------------------------
# Event Dispatch
# ----------------------------------------------------------------------

from unittest.mock import MagicMock


def test_on_created(monkeypatch, handler):
    calls = []

    monkeypatch.setattr(
        handler,
        "_debounce_process",
        lambda path, is_delete=False: calls.append((path, is_delete)),
    )

    event = MagicMock()
    event.is_directory = False
    event.src_path = "folder/file.txt"

    handler.on_created(event)

    assert len(calls) == 1
    assert calls[0][1] is False


def test_on_modified(monkeypatch, handler):
    calls = []

    monkeypatch.setattr(
        handler,
        "_debounce_process",
        lambda path, is_delete=False: calls.append((path, is_delete)),
    )

    event = MagicMock()
    event.is_directory = False
    event.src_path = "folder/file.txt"

    handler.on_modified(event)

    assert len(calls) == 1
    assert calls[0][1] is False


def test_on_deleted(monkeypatch, handler):
    calls = []

    monkeypatch.setattr(
        handler,
        "_debounce_process",
        lambda path, is_delete=False: calls.append((path, is_delete)),
    )

    event = MagicMock()
    event.is_directory = False
    event.src_path = "folder/file.txt"

    handler.on_deleted(event)

    assert len(calls) == 1
    assert calls[0][1] is True


def test_on_moved(monkeypatch, handler):
    calls = []

    monkeypatch.setattr(
        handler,
        "_debounce_process",
        lambda path, is_delete=False: calls.append((path, is_delete)),
    )

    event = MagicMock()
    event.is_directory = False
    event.src_path = "old/file.txt"
    event.dest_path = "new/file.txt"

    handler.on_moved(event)

    assert len(calls) == 2

    # old path deleted
    assert calls[0][1] is True

    # new path indexed
    assert calls[1][1] is False


# ----------------------------------------------------------------------
# Directory Events
# ----------------------------------------------------------------------

@pytest.mark.parametrize(
    "method",
    [
        "on_created",
        "on_modified",
        "on_deleted",
        "on_moved",
    ],
)
def test_directory_events_are_ignored(monkeypatch, handler, method):
    called = False

    def fake(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(
        handler,
        "_debounce_process",
        fake,
    )

    event = MagicMock()
    event.is_directory = True
    event.src_path = "folder"

    if method == "on_moved":
        event.dest_path = "folder2"

    getattr(handler, method)(event)

    assert called is False

# ----------------------------------------------------------------------
# file_watcher_scope()
# ----------------------------------------------------------------------

from pathlib import Path


class FakeObserver:
    def __init__(self):
        self.schedule_called = False
        self.start_called = False
        self.stop_called = False
        self.join_called = False

    def schedule(self, handler, path, recursive):
        self.schedule_called = True
        self.handler = handler
        self.path = path
        self.recursive = recursive

    def start(self):
        self.start_called = True

    def stop(self):
        self.stop_called = True

    def join(self):
        self.join_called = True


def test_file_watcher_scope(monkeypatch, tmp_path):
    observer = FakeObserver()

    monkeypatch.setattr(
        watcher,
        "Observer",
        lambda: observer,
    )

    with watcher.file_watcher_scope(str(tmp_path)) as obs:
        assert obs is observer

    assert observer.schedule_called
    assert observer.start_called
    assert observer.stop_called
    assert observer.join_called


def test_file_watcher_scope_missing_directory(tmp_path):
    missing = tmp_path / "does_not_exist"

    with pytest.raises(FileNotFoundError):
        with watcher.file_watcher_scope(str(missing)):
            pass