"""Pure adapters from compatibility parser results to canonical records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aema.catalog import CATALOG_BY_FIELD
from aema.models import (
    CanonicalRecord,
    MeasurementKind,
    PackageUidRelation,
    PipelineResult,
    Source,
    Unit,
)


@dataclass(frozen=True, slots=True)
class CanonicalDiagnostics:
    unknown_numeric_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanonicalResult:
    records: tuple[CanonicalRecord, ...] = ()
    relations: tuple[PackageUidRelation, ...] = ()
    diagnostics: CanonicalDiagnostics = CanonicalDiagnostics()

    def to_rows(self) -> list[dict[str, Any]]:
        return [record.to_row() for record in self.records]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _record(
    result: PipelineResult,
    source: Source,
    field: str,
    value: int | float,
    raw: dict[str, Any],
    *,
    uid: int | None,
    payload: dict[str, Any],
) -> CanonicalRecord:
    entry = CATALOG_BY_FIELD[(source.value, field)]
    return CanonicalRecord.from_pipeline_result(
        pipeline_result=result,
        source=source,
        entity=entry.entity,
        metric=entry.metric,
        value=value,
        unit=Unit(entry.unit) if entry.unit is not None else None,
        measurement_kind=MeasurementKind(entry.measurement_kind),
        uid=uid,
        line_number=raw.get("line_number"),
        payload=payload,
    )


def _adapt_numeric_records(
    result: PipelineResult,
    source: Source,
    rows: list[dict[str, Any]],
) -> tuple[tuple[CanonicalRecord, ...], CanonicalDiagnostics]:
    records: list[CanonicalRecord] = []
    unknown: set[str] = set()
    for raw in rows:
        uid = raw.get("uid")
        if source is Source.CHECKIN and uid == 0:
            uid = None
        context = {
            key: value
            for key, value in raw.items()
            if key in {"category", "tag", "process_name", "wakelock_name", "power_item"}
        }
        if raw.get("uid") == 0:
            context["uid_scope"] = "global"
            context["uid_original"] = 0
        for field, value in raw.items():
            if not _is_number(value):
                continue
            entry = CATALOG_BY_FIELD.get((source.value, field))
            if entry is None:
                unknown.add(field)
                continue
            if entry.metric is None:
                continue
            records.append(_record(result, source, field, value, raw, uid=uid, payload=context))
    return tuple(records), CanonicalDiagnostics(tuple(sorted(unknown)))


def adapt_checkin(result: PipelineResult) -> CanonicalResult:
    records, diagnostics = _adapt_numeric_records(result, Source.CHECKIN, result.checkin.records)
    return CanonicalResult(records=records, diagnostics=diagnostics)


def adapt_battery_report(result: PipelineResult) -> CanonicalResult:
    records: list[CanonicalRecord] = []
    unknown: set[str] = set()
    for raw in result.battery_report.records:
        uid = raw.get("uid")
        context = {
            key: raw[key]
            for key in ("record_type", "uid_text", "unit", "measurement_kind")
            if key in raw
        }
        if raw.get("record_type") == "uid":
            context["provenance_granularity"] = "uid_record"
        else:
            context["provenance_granularity"] = "summary_record"
        for field, value in raw.items():
            if not _is_number(value):
                continue
            entry = CATALOG_BY_FIELD.get((Source.POWER.value, field))
            if entry is None:
                unknown.add(field)
                continue
            if entry.metric is None:
                continue
            records.append(
                _record(result, Source.POWER, field, value, raw, uid=uid, payload=context)
            )
    return CanonicalResult(
        records=tuple(records),
        diagnostics=CanonicalDiagnostics(tuple(sorted(unknown))),
    )


def adapt_packages(result: PipelineResult) -> CanonicalResult:
    relations = tuple(
        PackageUidRelation.from_pipeline_result(
            pipeline_result=result,
            package_name=raw["package_name"],
            uid=raw["uid"],
            line_number=raw.get("line_number"),
        )
        for raw in result.packages.records
    )
    return CanonicalResult(relations=relations)


def adapt_pipeline(result: PipelineResult) -> CanonicalResult:
    checkin = adapt_checkin(result)
    power = adapt_battery_report(result)
    packages = adapt_packages(result)
    diagnostics = CanonicalDiagnostics(
        tuple(
            sorted(
                set(checkin.diagnostics.unknown_numeric_fields)
                | set(power.diagnostics.unknown_numeric_fields)
            )
        )
    )
    return CanonicalResult(
        records=checkin.records + power.records,
        relations=packages.relations,
        diagnostics=diagnostics,
    )
