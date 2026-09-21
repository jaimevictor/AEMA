"""Typed models shared by parsers, pipeline, and exporter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

Record = dict[str, Any]


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
