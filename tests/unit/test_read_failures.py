from __future__ import annotations

from pathlib import Path

import pytest

import aema.parsers.battery_report as battery_report_module
import aema.parsers.checkin as checkin_module
import aema.parsers.packages as packages_module
from aema.errors import ParseError
from aema.parsers.battery_report import BatteryReportParser
from aema.parsers.checkin import CheckinParser
from aema.parsers.packages import PackageUidParser


class FailingStream:
    def __init__(self, lines: list[str]) -> None:
        self.lines = iter(lines)

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def __iter__(self):
        return self

    def __next__(self) -> str:
        try:
            return next(self.lines)
        except StopIteration as exc:
            raise OSError("injected read failure") from exc


@pytest.mark.parametrize(
    ("module", "parser", "lines"),
    [
        (checkin_module, CheckinParser, ["9,0,i,vers\n"]),
        (battery_report_module, BatteryReportParser, ["Estimated power use (mAh):\n"]),
        (packages_module, PackageUidParser, ["package:app.one uid:10001\n"]),
    ],
)
def test_midstream_read_failure_is_fatal_and_contextual(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module, parser, lines: list[str]
) -> None:
    path = tmp_path / "input.txt"
    path.write_text("placeholder", encoding="utf-8")
    monkeypatch.setattr(module, "open_text", lambda *args, **kwargs: FailingStream(lines))
    with pytest.raises(ParseError, match=r"cannot read .*input\.txt: injected read failure"):
        parser(path, strict=False).parse_result()


@pytest.mark.parametrize("parser", [CheckinParser, BatteryReportParser, PackageUidParser])
def test_invalid_byte_sequence_is_fatal(tmp_path: Path, parser) -> None:
    path = tmp_path / "invalid.bin"
    path.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(ParseError, match="cannot decode"):
        parser(path, strict=False).parse_result()
