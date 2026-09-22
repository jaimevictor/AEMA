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
    unknown_numeric_diagnostics: tuple[tuple[str, str, int | None], ...] = ()
    issues: tuple[str, ...] = ()


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
    unknown_details: set[tuple[str, str, int | None]] = set()
    for raw in rows:
        uid = raw.get("uid")
        context = {
            key: value
            for key, value in raw.items()
            if key
            in {
                "category",
                "tag",
                "checkin_version",
                "process_name",
                "wakelock_name",
                "power_item",
                "is_hidden_or_system_consumer",
            }
        }
        if raw.get("uid") == 0:
            context["uid_original"] = 0
            if raw.get("category") == "l" and raw.get("tag") == "m":
                uid = None
                context["uid_scope"] = "global"
            else:
                context["uid_scope"] = "ambiguous"
        for field, value in raw.items():
            if not _is_number(value):
                continue
            entry = CATALOG_BY_FIELD.get((source.value, field))
            if entry is None:
                unknown.add(field)
                unknown_details.add((source.value, field, raw.get("line_number")))
                continue
            if entry.metric is None:
                continue
            records.append(_record(result, source, field, value, raw, uid=uid, payload=context))
    return tuple(records), CanonicalDiagnostics(
        tuple(sorted(unknown)),
        tuple(
            sorted(
                unknown_details,
                key=lambda item: (item[0], item[1], item[2] is not None, item[2] or 0),
            )
        ),
    )


def adapt_checkin(result: PipelineResult) -> CanonicalResult:
    records, diagnostics = _adapt_numeric_records(result, Source.CHECKIN, result.checkin.records)
    return CanonicalResult(records=records, diagnostics=diagnostics)


def adapt_battery_report(result: PipelineResult) -> CanonicalResult:
    records: list[CanonicalRecord] = []
    unknown: set[str] = set()
    unknown_details: set[tuple[str, str, int | None]] = set()
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
                unknown_details.add((Source.POWER.value, field, raw.get("line_number")))
                continue
            if entry.metric is None:
                continue
            records.append(
                _record(result, Source.POWER, field, value, raw, uid=uid, payload=context)
            )
    return CanonicalResult(
        records=tuple(records),
        diagnostics=CanonicalDiagnostics(
            tuple(sorted(unknown)),
            tuple(
                sorted(
                    unknown_details,
                    key=lambda item: (item[0], item[1], item[2] is not None, item[2] or 0),
                )
            ),
        ),
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
    package_uids = {relation.uid for relation in packages.relations}
    estimate_uids = {
        record.uid
        for record in power.records
        if record.uid is not None and record.metric == "total_estimated_charge_mah"
    }
    package_pairs = [(relation.package_name, relation.uid) for relation in packages.relations]
    duplicate_pairs = sorted({pair for pair in package_pairs if package_pairs.count(pair) > 1})
    uid_counts = {
        uid: sum(pair_uid == uid for _, pair_uid in package_pairs) for uid in package_uids
    }
    shared_uids = sorted(uid for uid, count in uid_counts.items() if count > 1)
    issues = [
        f"duplicate package/UID relation: {package}:{uid}" for package, uid in duplicate_pairs
    ]
    issues.extend(f"UID {uid} has multiple packages" for uid in shared_uids)
    issues.extend(
        f"UID {uid} has estimate but no package" for uid in sorted(estimate_uids - package_uids)
    )
    issues.extend(
        f"UID {uid} has package but no estimate" for uid in sorted(package_uids - estimate_uids)
    )
    diagnostics = CanonicalDiagnostics(
        tuple(
            sorted(
                set(checkin.diagnostics.unknown_numeric_fields)
                | set(power.diagnostics.unknown_numeric_fields)
            )
        ),
        tuple(
            sorted(
                set(checkin.diagnostics.unknown_numeric_diagnostics)
                | set(power.diagnostics.unknown_numeric_diagnostics)
            )
        ),
        tuple(dict.fromkeys(issues)),
    )
    return CanonicalResult(
        records=checkin.records + power.records,
        relations=packages.relations,
        diagnostics=diagnostics,
    )
