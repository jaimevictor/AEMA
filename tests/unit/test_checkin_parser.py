from __future__ import annotations

import json
from pathlib import Path

import pytest

from aema.errors import ParseError, UnsupportedVersionError
from aema.parsers.checkin import CheckinParser


def test_checkin_golden_records_and_diagnostics(fixture_dir: Path) -> None:
    result = CheckinParser(fixture_dir / "checkin_v9.csv").parse_result()
    expected = json.loads((fixture_dir / "checkin_expected.json").read_text(encoding="utf-8"))
    assert result.records[:2] == expected
    assert [record["tag"] for record in result.records] == ["pr", "wl", "nt", "m", "pwi"]
    assert result.diagnostics.unsupported_tags == {"cpu": 1}
    assert result.records[-1]["estimated_charge_mah"] == pytest.approx(-0.0012)


def test_checkin_preserves_base_fields_and_variable_wakelock_groups(
    fixture_dir: Path,
) -> None:
    frame = CheckinParser(fixture_dir / "checkin_v9.csv").parse()
    partial = frame.loc[frame["tag"] == "wl"].iloc[0]
    assert partial["uid"] == 10001
    assert partial["category"] == "l"
    assert partial["background_partial_total_duration_ms"] == 6


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("10,0,i,vers\n", UnsupportedVersionError),
        ("9,0,l,pr,truncated,1\n9,0,i,vers\n", ParseError),
        ("9,0,l,wl,name,1,x,2,3,4,5\n9,0,i,vers\n", ParseError),
        ("", ParseError),
    ],
)
def test_checkin_rejects_incompatible_inputs(
    tmp_path: Path, text: str, error: type[Exception]
) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(error):
        CheckinParser(path).parse_result()


def test_checkin_lenient_mode_reports_bad_records(tmp_path: Path) -> None:
    path = tmp_path / "mixed.csv"
    path.write_text(
        "9,0,i,vers\n9,1,l,pr,broken\n9,1,l,pwi,cpu,1,0,0,0\n",
        encoding="utf-8",
    )
    result = CheckinParser(path, strict=False).parse_result()
    assert len(result.records) == 1
    assert len(result.diagnostics.warnings) == 1


def test_checkin_detects_utf16_bom(tmp_path: Path) -> None:
    path = tmp_path / "utf16.csv"
    path.write_text("9,0,i,vers\n9,1,l,pwi,cpu,1,0,0,0\n", encoding="utf-16")
    assert CheckinParser(path).parse_result().records[0]["power_item"] == "cpu"
