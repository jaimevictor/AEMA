from __future__ import annotations

import math

import pytest

from aema.models import (
    CANONICAL_SCHEMA_VERSION,
    CanonicalRecord,
    MeasurementKind,
    PackageUidRelation,
    Provenance,
    Source,
    Unit,
)

HASH = "a" * 64


def record(**overrides: object) -> CanonicalRecord:
    data: dict[str, object] = {
        "entity": "power_record",
        "metric": "battery_capacity_mah",
        "value": 123.4,
        "unit": Unit.MAH,
        "measurement_kind": MeasurementKind.REPORTED_CAPACITY,
        "source": Source.POWER,
        "method": None,
        "uid": None,
        "package_name": None,
        "provenance": Provenance(Source.POWER, HASH, 3),
    }
    data.update(overrides)
    return CanonicalRecord(**data)


def test_valid_global_uid_and_round_trip_json() -> None:
    original = record(uid=10001, payload={"tag": "pwi"})
    restored = CanonicalRecord.from_json(original.to_json())
    assert restored == original
    assert restored.to_row()["input_sha256"] == HASH
    assert restored.schema_version == CANONICAL_SCHEMA_VERSION


@pytest.mark.parametrize("uid", [-1, True, 1.5])
def test_rejects_invalid_uid(uid: object) -> None:
    with pytest.raises(ValueError):
        record(uid=uid)


@pytest.mark.parametrize("value", [True, math.nan, math.inf, -math.inf])
def test_rejects_boolean_and_non_finite_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        record(value=value)


def test_accepts_negative_and_scientific_numeric_values() -> None:
    assert record(value=-1.2e3).value == -1200


def test_rejects_invalid_metric_unit_origin_line_and_hash() -> None:
    with pytest.raises(ValueError):
        record(metric="Not valid")
    with pytest.raises(ValueError):
        record(unit=Unit.MS)
    with pytest.raises(ValueError):
        record(provenance=Provenance(Source.POWER, HASH, 0))
    with pytest.raises(ValueError):
        Provenance(Source.POWER, "manifest.input_sha256", 1)


def test_preserves_shared_uid_package_relations_without_consumption_value() -> None:
    first = PackageUidRelation("app.one", 10001, Provenance(Source.PACKAGES, HASH, 1))
    second = PackageUidRelation("app.two", 10001, Provenance(Source.PACKAGES, HASH, 2))
    assert first.uid == second.uid == 10001
    assert first.package_name != second.package_name


def test_payload_and_absent_identity_remain_explicit() -> None:
    item = record()
    assert item.uid is None and item.package_name is None
    assert item.method is None
