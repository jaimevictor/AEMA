from __future__ import annotations

from pathlib import Path

import pytest

from aema.errors import ParseError
from aema.parsers.battery_report import BatteryReportParser


def test_battery_report_golden_meaning_units_and_multiuser_uid(fixture_dir: Path) -> None:
    result = BatteryReportParser(fixture_dir / "battery_report.txt").parse_result()
    summary, app, system = result.records
    assert summary["battery_capacity_mah"] == 4700
    assert summary["computed_drain_mah"] == 12
    assert summary["actual_drain_min_mah"] == 10
    assert summary["screen_apps_estimated_charge_mah"] == 630
    assert app["uid"] == 1_010_042
    assert app["total_estimated_charge_mah"] == pytest.approx(-0.0012)
    assert app["cpu_estimated_charge_mah"] == pytest.approx(-4.5e-5)
    assert app["cpu_foreground_estimated_charge_mah"] == pytest.approx(2e-5)
    assert system["wakelock_estimated_charge_mah"] == 1.5
    assert {record["unit"] for record in result.records} == {"mAh"}
    assert {record["measurement_kind"] for record in result.records} == {"estimated_or_attributed"}


@pytest.mark.parametrize(
    "text",
    [
        "nothing here\n",
        "Estimated power use (mAh):\nCapacity: 1, Rated: 1, Typical: 1, "
        "Computed drain: 1, actual drain: 1-1\n",
        "Estimated power use (mAh):\nCapacity: broken\nUID 1: 2\n",
        "Estimated power use (mAh):\nCapacity: 1, Rated: 1, Typical: 1, "
        "Computed drain: 1, actual drain: 1-1\nUID invalid: 2\n",
    ],
)
def test_battery_report_rejects_missing_or_invalid_required_data(tmp_path: Path, text: str) -> None:
    path = tmp_path / "bad.txt"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ParseError):
        BatteryReportParser(path).parse_result()


def test_battery_report_leniently_reports_duplicate_detail(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.txt"
    path.write_text(
        "Estimated power use (mAh):\n"
        "Capacity: 1, Rated: 1, Typical: 1, Computed drain: 1, actual drain: 1-1\n"
        "UID 1: 1\n    cpu=1 cpu=2\n\n",
        encoding="utf-8",
    )
    result = BatteryReportParser(path, strict=False).parse_result()
    assert result.records[1]["cpu_estimated_charge_mah"] == 1
    assert len(result.diagnostics.warnings) == 1


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("invalid_value", ["NaN", "inf", "1e309"])
def test_uid_detail_numeric_error_is_contextual_and_atomic(
    tmp_path: Path, strict: bool, invalid_value: str
) -> None:
    path = tmp_path / "invalid-detail.txt"
    path.write_text(
        "Estimated power use (mAh):\n"
        "Capacity: 1, Rated: 1, Typical: 1, Computed drain: 1, actual drain: 1-1\n"
        f"UID 1: 1\n    cpu=1 wifi={invalid_value}\n\n",
        encoding="utf-8",
    )
    if strict:
        with pytest.raises(ParseError, match=r"invalid-detail\.txt:4:.*(?:invalid|non-finite)"):
            BatteryReportParser(path).parse_result()
        return
    result = BatteryReportParser(path, strict=False).parse_result()
    uid = result.records[1]
    assert "cpu_estimated_charge_mah" not in uid
    assert "wifi_estimated_charge_mah" not in uid
    assert len(result.diagnostics.warnings) == 1
    assert f"{path}:4:" in result.diagnostics.warnings[0]


@pytest.mark.parametrize("strict", [True, False])
def test_global_detail_numeric_error_is_contextual_and_atomic(tmp_path: Path, strict: bool) -> None:
    path = tmp_path / "invalid-global.txt"
    path.write_text(
        "Estimated power use (mAh):\n"
        "Capacity: 1, Rated: 1, Typical: 1, Computed drain: 1, actual drain: 1-1\n"
        "screen: 1 apps: 1e309\nUID 1: 1\n\n",
        encoding="utf-8",
    )
    if strict:
        with pytest.raises(ParseError, match=r"invalid-global\.txt:3:.*non-finite"):
            BatteryReportParser(path).parse_result()
        return
    result = BatteryReportParser(path, strict=False).parse_result()
    summary = result.records[0]
    assert "screen_estimated_charge_mah" not in summary
    assert "screen_apps_estimated_charge_mah" not in summary
    assert len(result.diagnostics.warnings) == 1
