from __future__ import annotations

from pathlib import Path

from aema.adapters import adapt_battery_report, adapt_checkin, adapt_packages, adapt_pipeline
from aema.exporters import export_pipeline_result
from aema.models import MeasurementKind, PipelineInputs, Source, Unit
from aema.pipeline import run_pipeline


def pipeline_result():
    root = Path("tests/fixtures")
    return run_pipeline(
        PipelineInputs(root / "checkin_v9.csv", root / "battery_report.txt", root / "packages.txt")
    )


def test_adapters_convert_all_fixture_sources_without_mutating_historical_frames() -> None:
    result = pipeline_result()
    before = {name: frame.copy(deep=True) for name, frame in result.frames().items()}
    checkin = adapt_checkin(result)
    power = adapt_battery_report(result)
    packages = adapt_packages(result)
    after = result.frames()
    assert all(before[name].equals(after[name]) for name in before)
    assert len(checkin.records) == 72
    assert len(power.records) == 16
    assert len(packages.relations) == 3
    assert not checkin.diagnostics.unknown_numeric_fields
    assert not power.diagnostics.unknown_numeric_fields


def test_checkin_preserves_context_and_catalog_semantics() -> None:
    result = pipeline_result()
    records = adapt_checkin(result).records
    process = next(item for item in records if item.metric == "user_time_ms")
    power = next(item for item in records if item.metric == "estimated_charge_mah")
    global_item = next(item for item in records if item.metric == "screen_on_time_ms")
    assert process.uid == 10001
    assert process.payload["process_name"] == "com.example.worker"
    assert process.unit is Unit.MS
    assert process.measurement_kind is MeasurementKind.REPORTED_DURATION
    assert power.unit is Unit.MAH
    assert power.payload["tag"] == "pwi"
    assert power.payload["checkin_version"] == 9
    assert power.payload["is_hidden_or_system_consumer"] is True
    assert global_item.uid is None
    assert global_item.payload["uid_scope"] == "global"


def test_power_summary_uid_and_uid_text_are_separate() -> None:
    records = adapt_battery_report(pipeline_result()).records
    summary = next(item for item in records if item.metric == "battery_capacity_mah")
    uid_charge = next(item for item in records if item.metric == "total_estimated_charge_mah")
    assert summary.uid is None
    assert summary.measurement_kind is MeasurementKind.REPORTED_CAPACITY
    assert uid_charge.uid == 1010042
    assert uid_charge.payload["uid_text"] == "u10a42"
    assert uid_charge.unit is Unit.MAH


def test_packages_preserve_shared_uid_without_energy_records() -> None:
    result = pipeline_result()
    adapted = adapt_packages(result)
    assert [(item.package_name, item.uid) for item in adapted.relations] == [
        ("com.example.one", 10001),
        ("com.example.two", 10001),
        ("com.example.owner", 1010042),
    ]
    assert adapted.records == ()


def test_adaptation_is_deterministic_and_combined() -> None:
    result = pipeline_result()
    first = adapt_pipeline(result)
    second = adapt_pipeline(result)
    assert first == second
    assert [record.to_json() for record in first.records] == [
        record.to_json() for record in second.records
    ]
    assert all(
        record.provenance.source in {Source.CHECKIN, Source.POWER} for record in first.records
    )
    assert "UID 10001 has package but no estimate" in first.diagnostics.issues
    assert "UID 1000 has estimate but no package" in first.diagnostics.issues
    assert "UID 10001 has multiple packages" in first.diagnostics.issues


def test_unknown_numeric_field_is_reported_explicitly() -> None:
    result = pipeline_result()
    result.checkin.records.append({"uid": 10001, "line_number": 99, "future_metric": 1.0})
    adapted = adapt_checkin(result)
    assert adapted.diagnostics.unknown_numeric_fields == ("future_metric",)
    assert adapted.diagnostics.unknown_numeric_diagnostics == (("checkin", "future_metric", 99),)


def test_unknown_diagnostic_sort_accepts_missing_and_present_lines() -> None:
    result = pipeline_result()
    result.checkin.records.extend(
        [{"future_metric": 1.0}, {"future_metric": 2.0, "line_number": 7}]
    )
    diagnostics = adapt_checkin(result).diagnostics
    assert diagnostics.unknown_numeric_diagnostics == (
        ("checkin", "future_metric", None),
        ("checkin", "future_metric", 7),
    )


def test_uid_zero_keeps_ambiguous_context() -> None:
    result = pipeline_result()
    result.checkin.records.append(
        {
            "checkin_version": 9,
            "uid": 0,
            "category": "l",
            "tag": "pr",
            "line_number": 100,
            "process_name": "system",
            "user_time_ms": 1,
        }
    )
    record = next(
        item for item in adapt_checkin(result).records if item.provenance.line_number == 100
    )
    assert record.uid == 0
    assert record.payload["uid_scope"] == "ambiguous"
    assert record.payload["uid_original"] == 0


def test_duplicate_pair_does_not_count_as_shared_uid() -> None:
    result = pipeline_result()
    result.packages.records[:] = [
        {"package_name": "app.one", "uid": 10001, "line_number": 1},
        {"package_name": "app.one", "uid": 10001, "line_number": 2},
    ]
    issues = adapt_pipeline(result).diagnostics.issues
    assert "duplicate package/UID relation: app.one:10001" in issues
    assert "UID 10001 has multiple packages" not in issues


def test_distinct_packages_count_as_shared_uid() -> None:
    result = pipeline_result()
    result.packages.records[:] = [
        {"package_name": "app.one", "uid": 10001, "line_number": 1},
        {"package_name": "app.two", "uid": 10001, "line_number": 2},
    ]
    issues = adapt_pipeline(result).diagnostics.issues
    assert "UID 10001 has multiple packages" in issues
    assert not any(issue.startswith("duplicate package/UID relation:") for issue in issues)


def test_historical_csv_golden_bytes_remain_unchanged(tmp_path: Path) -> None:
    output = export_pipeline_result(pipeline_result(), tmp_path)
    golden = Path("tests/fixtures/golden")
    for name in (
        "stats_checkin_parsed.csv",
        "stats_power_estimates_parsed.csv",
        "package_uid_parsed.csv",
    ):
        assert (output / name).read_bytes() == (golden / name).read_bytes()
