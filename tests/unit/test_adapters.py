from __future__ import annotations

from pathlib import Path

from aema.adapters import adapt_battery_report, adapt_checkin, adapt_packages, adapt_pipeline
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


def test_unknown_numeric_field_is_reported_explicitly() -> None:
    result = pipeline_result()
    result.checkin.records.append({"uid": 10001, "line_number": 99, "future_metric": 1.0})
    adapted = adapt_checkin(result)
    assert adapted.diagnostics.unknown_numeric_fields == ("future_metric",)
