"""Input file validation, encoding detection, and hashing."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TextIO

from aema.errors import InputFileError


def detect_text_encoding(path: Path) -> str:
    """Detect supported BOM encodings; default to UTF-8 with optional BOM."""
    checked = validate_input_file(path)
    try:
        with checked.open("rb") as stream:
            prefix = stream.read(4)
    except OSError as exc:
        raise InputFileError(f"cannot read input file {checked}: {exc}") from exc
    if prefix.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    if prefix.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    return "utf-8"


def open_text(path: Path, *, newline: str | None = None) -> TextIO:
    """Open a validated text input with deterministic encoding detection."""
    checked = validate_input_file(path)
    try:
        return checked.open(
            "r", encoding=detect_text_encoding(checked), errors="strict", newline=newline
        )
    except (OSError, UnicodeError) as exc:
        raise InputFileError(f"cannot open input file {checked}: {exc}") from exc


def validate_input_file(path: Path) -> Path:
    """Require an existing regular file."""
    checked = Path(path)
    if not checked.exists():
        raise InputFileError(f"input file does not exist: {checked}")
    if not checked.is_file():
        raise InputFileError(f"input path is not a file: {checked}")
    return checked


def sha256_file(path: Path) -> str:
    """Hash a file without loading it into memory."""
    checked = validate_input_file(path)
    digest = hashlib.sha256()
    try:
        with checked.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise InputFileError(f"cannot hash input file {checked}: {exc}") from exc
    return digest.hexdigest().upper()
