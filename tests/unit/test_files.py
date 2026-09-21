from __future__ import annotations

from pathlib import Path

import pytest

from aema.errors import InputFileError
from aema.files import detect_text_encoding, sha256_file, validate_input_file


def test_file_helpers_validate_detect_and_hash(tmp_path: Path) -> None:
    plain = tmp_path / "plain.txt"
    plain.write_text("abc", encoding="utf-8")
    bom = tmp_path / "bom.txt"
    bom.write_text("abc", encoding="utf-16")
    utf8_bom = tmp_path / "utf8-bom.txt"
    utf8_bom.write_text("abc", encoding="utf-8-sig")
    assert validate_input_file(plain) == plain
    assert detect_text_encoding(plain) == "utf-8"
    assert detect_text_encoding(bom) == "utf-16"
    assert detect_text_encoding(utf8_bom) == "utf-8-sig"
    assert sha256_file(plain) == "BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD"


def test_file_helpers_reject_missing_and_directory(tmp_path: Path) -> None:
    with pytest.raises(InputFileError, match="does not exist"):
        validate_input_file(tmp_path / "missing")
    with pytest.raises(InputFileError, match="not a file"):
        validate_input_file(tmp_path)
