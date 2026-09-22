"""Typed models shared by parsers, pipeline, and exporter."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

Record = dict[str, Any]
CANONICAL_SCHEMA_VERSION = "1.0"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_METRIC_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class Unit(str, Enum):
    COUNT = "count"
    MS = "ms"
    US = "us"
    BYTES = "bytes"
    PACKETS = "packets"
    MAH = "mAh"


class MeasurementKind(str, Enum):
    REPORTED_VALUE = "reported_value"
    REPORTED_COUNT = "reported_count"
    REPORTED_DURATION = "reported_duration"
    REPORTED_QUANTITY = "reported_quantity"
    REPORTED_CAPACITY = "reported_capacity"
    REPORTED_DRAIN_RANGE = "reported_drain_range"
    ESTIMATED_OR_ATTRIBUTED_CHARGE = "estimated_or_attributed_charge"
    UID_ATTRIBUTED_CHARGE_ESTIMATE = "uid_attributed_charge_estimate"


class Source(str, Enum):
    CHECKIN = "checkin"
    POWER = "power"
    PACKAGES = "packages"


@dataclass(frozen=True, slots=True)
class Provenance:
    """Actual input provenance; hash must come from the pipeline manifest."""

    source: Source
    input_sha256: str
    line_number: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, Source):
            raise TypeError("source must be a Source")
        if not isinstance(self.input_sha256, str) or not _SHA256_RE.fullmatch(self.input_sha256):
            raise ValueError("input_sha256 must be a SHA-256 digest")
        object.__setattr__(self, "input_sha256", self.input_sha256.lower())
        if self.line_number is not None and (
            isinstance(self.line_number, bool)
            or not isinstance(self.line_number, int)
            or self.line_number < 1
        ):
            raise ValueError("line_number must be a positive integer")


def _validate_value(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("value must be numeric and must not be boolean")
    if not math.isfinite(value):
        raise ValueError("value must be finite")


@dataclass(frozen=True, slots=True)
class CanonicalRecord:
    """Versioned, one-metric canonical record. Parsers remain compatibility layers."""

    entity: str
    metric: str
    value: int | float
    unit: Unit | None
    measurement_kind: MeasurementKind
    source: Source
    method: str | None
    uid: int | None
    package_name: str | None
    provenance: Provenance
    payload: dict[str, Any] = field(default_factory=dict)
    schema_version: str = CANONICAL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CANONICAL_SCHEMA_VERSION:
            raise ValueError("unsupported canonical schema version")
        if not isinstance(self.source, Source):
            raise TypeError("source must be a Source")
        if not isinstance(self.entity, str) or not self.entity.strip():
            raise ValueError("entity must be non-empty")
        if not isinstance(self.metric, str) or not _METRIC_RE.fullmatch(self.metric):
            raise ValueError("metric must be a lowercase identifier")
        _validate_value(self.value)
        if self.unit is not None and not isinstance(self.unit, Unit):
            raise ValueError("unit must be a supported Unit or None")
        if not isinstance(self.measurement_kind, MeasurementKind):
            raise ValueError("measurement_kind must be supported")
        if self.method is not None and not isinstance(self.method, str):
            raise TypeError("method must be a string or None")
        if self.uid is not None and (
            isinstance(self.uid, bool) or not isinstance(self.uid, int) or self.uid < 0
        ):
            raise ValueError("uid must be a non-negative integer or None")
        if self.package_name is not None:
            if not isinstance(self.package_name, str):
                raise TypeError("package_name must be a string or None")
            if not self.package_name.strip():
                raise ValueError("package_name must be non-empty when present")
        if not isinstance(self.provenance, Provenance) or self.provenance.source != self.source:
            raise ValueError("provenance source must match record source")
        if not isinstance(self.payload, dict):
            raise TypeError("payload must be a dict")
        try:
            json.dumps(self.payload, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("payload must be JSON-serializable") from exc
        if self.source == Source.PACKAGES and self.uid is None:
            raise ValueError("package relation requires uid")
        self._validate_catalog_contract()

    def _validate_catalog_contract(self) -> None:
        from aema.catalog import CATALOG_BY_FIELD

        entry = CATALOG_BY_FIELD.get((self.source.value, self.metric))
        if entry is None:
            raise ValueError(f"unknown catalog metric {self.source.value}:{self.metric}")
        if self.entity != entry.entity:
            raise ValueError(f"entity incompatible with catalog metric {self.metric}")
        expected_unit = Unit(entry.unit) if entry.unit is not None else None
        if self.unit != expected_unit:
            raise ValueError(f"unit incompatible with catalog metric {self.metric}")
        if self.measurement_kind.value != entry.measurement_kind:
            raise ValueError(f"measurement kind incompatible with catalog metric {self.metric}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "entity": self.entity,
            "metric": self.metric,
            "value": self.value,
            "unit": self.unit.value if self.unit else None,
            "measurement_kind": self.measurement_kind.value,
            "source": self.source.value,
            "method": self.method,
            "uid": self.uid,
            "package_name": self.package_name,
            "input_sha256": self.provenance.input_sha256,
            "line_number": self.provenance.line_number,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CanonicalRecord:
        provenance = Provenance(
            Source(data["source"]), data["input_sha256"], data.get("line_number")
        )
        return cls(
            data["entity"],
            data["metric"],
            data["value"],
            Unit(data["unit"]) if data.get("unit") is not None else None,
            MeasurementKind(data["measurement_kind"]),
            provenance.source,
            data.get("method"),
            data.get("uid"),
            data.get("package_name"),
            provenance,
            data.get("payload", {}),
            data.get("schema_version", CANONICAL_SCHEMA_VERSION),
        )

    @classmethod
    def from_json(cls, text: str) -> CanonicalRecord:
        return cls.from_dict(json.loads(text))

    def to_row(self) -> dict[str, Any]:
        row = self.to_dict()
        row["payload"] = json.dumps(
            self.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return row

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> CanonicalRecord:
        data = dict(row)
        payload = data.get("payload", "{}")
        if isinstance(payload, str):
            payload = json.loads(payload)
        data["payload"] = payload
        return cls.from_dict(data)

    @classmethod
    def from_pipeline_result(
        cls,
        *,
        pipeline_result: PipelineResult,
        source: Source,
        entity: str,
        metric: str,
        value: int | float,
        unit: Unit | None,
        measurement_kind: MeasurementKind,
        method: str | None = None,
        uid: int | None = None,
        package_name: str | None = None,
        line_number: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> CanonicalRecord:
        hash_key = {
            Source.CHECKIN: "checkin",
            Source.POWER: "battery_report",
            Source.PACKAGES: "packages",
        }[source]
        try:
            input_sha256 = pipeline_result.input_hashes[hash_key]
        except KeyError as exc:
            raise ValueError(f"missing pipeline hash for source {source.value}") from exc
        return cls(
            entity,
            metric,
            value,
            unit,
            measurement_kind,
            source,
            method,
            uid,
            package_name,
            Provenance(source, input_sha256, line_number),
            {} if payload is None else payload,
        )


@dataclass(frozen=True, slots=True)
class PackageUidRelation:
    """Many-to-many package/UID edge; it carries no consumption value."""

    package_name: str
    uid: int
    provenance: Provenance

    def __post_init__(self) -> None:
        if not isinstance(self.package_name, str):
            raise TypeError("package_name must be a string")
        if not self.package_name.strip():
            raise ValueError("package_name must be non-empty")
        if isinstance(self.uid, bool) or not isinstance(self.uid, int) or self.uid < 0:
            raise ValueError("uid must be a non-negative integer")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be Provenance")
        if self.provenance.source != Source.PACKAGES:
            raise ValueError("package relation provenance must use packages source")

    @classmethod
    def from_pipeline_result(
        cls,
        *,
        pipeline_result: PipelineResult,
        package_name: str,
        uid: int,
        line_number: int | None = None,
    ) -> PackageUidRelation:
        try:
            input_sha256 = pipeline_result.input_hashes["packages"]
        except KeyError as exc:
            raise ValueError("missing pipeline hash for source packages") from exc
        return cls(package_name, uid, Provenance(Source.PACKAGES, input_sha256, line_number))

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_name": self.package_name,
            "uid": self.uid,
            "source": self.provenance.source.value,
            "input_sha256": self.provenance.input_sha256,
            "line_number": self.provenance.line_number,
        }


@dataclass(slots=True)
class ParseDiagnostics:
    """Counts and explicit non-fatal diagnostics for one input."""

    source: str
    total_lines: int = 0
    parsed_records: int = 0
    skipped_empty_lines: int = 0
    unsupported_tags: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def add_unsupported_tag(self, tag: str) -> None:
        """Count a valid check-in tag that this package does not claim to support."""
        self.unsupported_tags[tag] = self.unsupported_tags.get(tag, 0) + 1

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "source": self.source,
            "total_lines": self.total_lines,
            "parsed_records": self.parsed_records,
            "skipped_empty_lines": self.skipped_empty_lines,
            "unsupported_tags": dict(sorted(self.unsupported_tags.items())),
            "warnings": self.warnings.copy(),
        }


@dataclass(slots=True)
class ParseResult:
    """Parsed records plus diagnostics, before persistence."""

    records: list[Record]
    diagnostics: ParseDiagnostics

    def to_frame(self) -> pd.DataFrame:
        """Create a DataFrame without changing domain values."""
        return pd.DataFrame.from_records(self.records)


@dataclass(frozen=True, slots=True)
class PipelineInputs:
    """All files required by one processing run."""

    checkin: Path
    battery_report: Path
    packages: Path


@dataclass(slots=True)
class PipelineResult:
    """Complete in-memory result set for one run."""

    checkin: ParseResult
    battery_report: ParseResult
    packages: ParseResult
    input_hashes: dict[str, str]

    def frames(self) -> dict[str, pd.DataFrame]:
        """Return stable output names and their DataFrames."""
        return {
            "stats_checkin_parsed.csv": self.checkin.to_frame(),
            "stats_power_estimates_parsed.csv": self.battery_report.to_frame(),
            "package_uid_parsed.csv": self.packages.to_frame(),
        }
