from __future__ import annotations

from pathlib import Path

import pytest

from aema.errors import ParseError
from aema.parsers.packages import PackageUidParser


def test_packages_preserve_shared_and_multiuser_uids(fixture_dir: Path) -> None:
    result = PackageUidParser(fixture_dir / "packages.txt").parse_result()
    assert [record["uid"] for record in result.records[:2]] == [10001, 10001]
    assert result.records[2]["uid"] == 1_010_042
    assert len(result.to_frame()) == 3


def test_packages_reject_invalid_and_empty_files(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.txt"
    invalid.write_text("package:bad uid:not-a-number\n", encoding="utf-8")
    with pytest.raises(ParseError, match="invalid package"):
        PackageUidParser(invalid).parse_result()
    empty = tmp_path / "empty.txt"
    empty.write_text("\n", encoding="utf-8")
    with pytest.raises(ParseError, match="no package"):
        PackageUidParser(empty).parse_result()


def test_packages_lenient_mode_and_duplicate_diagnostics(tmp_path: Path) -> None:
    path = tmp_path / "mixed.txt"
    path.write_text(
        "bad\npackage:com.example uid:42\npackage:com.example uid:42\n",
        encoding="utf-8",
    )
    result = PackageUidParser(path, strict=False).parse_result()
    assert len(result.records) == 2
    assert len(result.diagnostics.warnings) == 2
