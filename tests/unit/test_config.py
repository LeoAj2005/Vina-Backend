from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

import vina.config as config


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

@pytest.fixture
def isolated_config(monkeypatch, tmp_path):
    """
    Redirect all filesystem locations into pytest's temp directory.
    """

    monkeypatch.setattr(config, "APP_DIR", tmp_path)

    monkeypatch.setattr(
        config,
        "CONFIG_FILE",
        tmp_path / "config.json",
    )

    monkeypatch.setattr(
        config,
        "TOKEN_FILE",
        tmp_path / "token",
    )

    monkeypatch.setattr(
        config,
        "LOG_DIR",
        tmp_path,
    )

    config._logging_initialized = False

    return tmp_path


# ----------------------------------------------------------------------
# _atomic_write_text()
# ----------------------------------------------------------------------

def test_atomic_write_text(isolated_config):
    target = isolated_config / "sample.txt"

    config._atomic_write_text(
        target,
        "hello world",
    )

    assert target.exists()
    assert target.read_text() == "hello world"


# ----------------------------------------------------------------------
# get_config()
# ----------------------------------------------------------------------

def test_get_config_creates_default(isolated_config):
    cfg = config.get_config()

    assert cfg["port"] == 8765
    assert cfg["host"] == "127.0.0.1"

    assert config.CONFIG_FILE.exists()


def test_get_config_reads_existing(isolated_config):
    expected = {
        "target_folder": "D:/Course",
        "host": "0.0.0.0",
        "port": 9000,
    }

    config.CONFIG_FILE.write_text(
        json.dumps(expected),
        encoding="utf-8",
    )

    cfg = config.get_config()

    assert cfg == expected


def test_get_config_repairs_corrupted_file(isolated_config):
    config.CONFIG_FILE.write_text(
        "{broken json",
        encoding="utf-8",
    )

    cfg = config.get_config()

    assert cfg == config.DEFAULT_CONFIG

    backup = config.CONFIG_FILE.with_suffix(".corrupted")

    assert backup.exists()


# ----------------------------------------------------------------------
# Token
# ----------------------------------------------------------------------

def test_create_token(isolated_config):
    token = config.get_or_create_token()

    assert token

    assert config.TOKEN_FILE.exists()

    assert (
        config.TOKEN_FILE.read_text().strip()
        == token
    )


def test_existing_token_reused(isolated_config):
    config.TOKEN_FILE.write_text(
        "abc123",
        encoding="utf-8",
    )

    assert config.get_or_create_token() == "abc123"


# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------

def test_setup_logging_returns_logger(isolated_config):
    logger = config.setup_logging()

    assert isinstance(logger, logging.Logger)


def test_setup_logging_is_idempotent(isolated_config):
    logger1 = config.setup_logging()

    handler_count = len(logging.getLogger().handlers)

    logger2 = config.setup_logging()

    assert logger1 is logger2

    assert len(logging.getLogger().handlers) == handler_count


# ----------------------------------------------------------------------
# Failure Handling
# ----------------------------------------------------------------------

def test_atomic_write_failure(monkeypatch, isolated_config):

    def boom(*args, **kwargs):
        raise OSError("disk failure")

    monkeypatch.setattr(
        Path,
        "write_text",
        boom,
    )

    with pytest.raises(OSError):
        config._atomic_write_text(
            isolated_config / "a.txt",
            "hello",
        )


def test_token_read_failure(monkeypatch, isolated_config):
    config.TOKEN_FILE.write_text("abc")

    def fail(*args, **kwargs):
        raise OSError()

    monkeypatch.setattr(
        Path,
        "read_text",
        fail,
    )

    token = config.get_or_create_token()

    assert token