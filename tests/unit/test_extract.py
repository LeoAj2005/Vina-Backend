from __future__ import annotations

import json
from pathlib import Path

import pytest

from vina.indexer.extract import extract_text


# ----------------------------------------------------------------------
# TXT
# ----------------------------------------------------------------------

def test_extract_txt(txt_file: Path):
    text = extract_text(str(txt_file))

    assert "Hello from pytest!" in text
    assert "temporary text file" in text


def test_extract_empty_txt(tmp_path: Path):
    file = tmp_path / "empty.txt"
    file.write_text("", encoding="utf-8")

    assert extract_text(str(file)) == ""


# ----------------------------------------------------------------------
# JSON
# ----------------------------------------------------------------------

def test_extract_json(json_file: Path):
    text = extract_text(str(json_file))

    assert "Vina" in text
    assert "version" in text
    assert "Python" in text


def test_invalid_json(tmp_path: Path):
    file = tmp_path / "broken.json"

    file.write_text(
        '{"name":"vina",}',
        encoding="utf-8",
    )

    assert extract_text(str(file)) == ""


# ----------------------------------------------------------------------
# Missing Files
# ----------------------------------------------------------------------

def test_missing_file():
    assert extract_text("does_not_exist.txt") == ""


# ----------------------------------------------------------------------
# Corrupted PDF
# ----------------------------------------------------------------------

def test_invalid_pdf_returns_empty_string(invalid_pdf):
    assert extract_text(str(invalid_pdf)) == ""


# ----------------------------------------------------------------------
# Unknown Extension
# ----------------------------------------------------------------------

def test_unknown_extension_returns_empty(tmp_path: Path):
    file = tmp_path / "notes.xyz"

    file.write_text(
        "hello",
        encoding="utf-8",
    )

    assert extract_text(str(file)) == ""


# ----------------------------------------------------------------------
# Text Normalization
# ----------------------------------------------------------------------

def test_whitespace_normalization(tmp_path: Path):
    file = tmp_path / "normalize.txt"

    file.write_text(
        "Hello      World\n\n\n\nPython\t\tTesting",
        encoding="utf-8",
    )

    text = extract_text(str(file))

    assert "Hello World" in text
    assert "Python Testing" in text


# ----------------------------------------------------------------------
# Null Byte Removal
# ----------------------------------------------------------------------

def test_null_bytes_removed(tmp_path: Path):
    file = tmp_path / "null.txt"

    file.write_bytes(
        b"Hello\x00World"
    )

    text = extract_text(str(file))

    assert "\x00" not in text
    assert "Hello" in text
    assert "World" in text


# ----------------------------------------------------------------------
# Unicode
# ----------------------------------------------------------------------

@pytest.mark.parametrize(
    "content",
    [
        "தமிழ் மொழி",
        "日本語です",
        "Привет мир",
        "مرحبا بالعالم",
        "😀 Python",
    ],
)
def test_unicode_support(tmp_path: Path, content: str):
    file = tmp_path / "unicode.txt"

    file.write_text(
        content,
        encoding="utf-8",
    )

    text = extract_text(str(file))

    assert content in text


# ----------------------------------------------------------------------
# Large File
# ----------------------------------------------------------------------

def test_large_text_file(tmp_path: Path):
    file = tmp_path / "large.txt"

    content = ("Python Testing\n" * 10000)

    file.write_text(
        content,
        encoding="utf-8",
    )

    text = extract_text(str(file))

    assert len(text) > 100000