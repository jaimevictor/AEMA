"""Parser for Android batterystats check-in CSV records."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from aema.errors import ParseError, UnsupportedVersionError
from aema.files import open_text
from aema.models import ParseDiagnostics, ParseResult, Record
from aema.normalization import parse_float, parse_int
from aema.schemas import (
    MISC_FIELDS,
    NETWORK_FIELDS,
    PROCESS_FIELDS,
    SUPPORTED_CHECKIN_VERSION,
    SUPPORTED_TAGS,
    WAKELOCK_TYPES,
)


class CheckinParser:
    """Parse the supported records emitted by ``dumpsys batterystats --checkin``."""

    def __init__(self, file_path: str | Path, *, strict: bool = True) -> None:
        self.file_path = Path(file_path)
        self.strict = strict
        self.diagnostics = ParseDiagnostics(source=str(self.file_path))

    def parse_result(self) -> ParseResult:
        records: list[Record] = []
        version: int | None = None
        diagnostics = ParseDiagnostics(source=str(self.file_path))

        try:
            with open_text(self.file_path, newline="") as stream:
                for line_number, row in enumerate(csv.reader(stream), start=1):
                    diagnostics.total_lines += 1
                    if not row or all(not field.strip() for field in row):
                        diagnostics.skipped_empty_lines += 1
                        continue
                    try:
                        if len(row) < 4:
                            raise ParseError("record has fewer than four base fields")
                        row_version = parse_int(row[0], "checkin_version")
                        if row_version != SUPPORTED_CHECKIN_VERSION:
                            raise UnsupportedVersionError(
                                f"unsupported check-in version {row_version}; "
                                f"expected {SUPPORTED_CHECKIN_VERSION}"
                            )
                        tag = row[3].strip()
                        if tag == "vers":
                            version = row_version
                            continue
                        if tag not in SUPPORTED_TAGS:
                            diagnostics.add_unsupported_tag(tag or "<empty>")
                            continue
                        records.append(self._parse_supported(row, line_number))
                    except (ParseError, ValueError) as exc:
                        message = f"{self.file_path}:{line_number}: {exc}"
                        if self.strict:
                            if isinstance(exc, UnsupportedVersionError):
                                raise UnsupportedVersionError(message) from exc
                            raise ParseError(message) from exc
                        diagnostics.warnings.append(message)
        except UnicodeDecodeError as exc:
            raise ParseError(f"cannot decode {self.file_path}: {exc}") from exc

        if version is None:
            raise ParseError(f"{self.file_path}: missing version record")
        diagnostics.parsed_records = len(records)
        self.diagnostics = diagnostics
        return ParseResult(records, diagnostics)

    def parse(self) -> pd.DataFrame:
        """Compatibility convenience returning a DataFrame."""

        return self.parse_result().to_frame()

    @staticmethod
    def _base(row: list[str], line_number: int) -> Record:
        return {
            "checkin_version": parse_int(row[0], "checkin_version"),
            "uid": parse_int(row[1], "uid"),
            "category": row[2].strip(),
            "tag": row[3].strip(),
            "line_number": line_number,
        }

    def _parse_supported(self, row: list[str], line_number: int) -> Record:
        tag = row[3].strip()
        record = self._base(row, line_number)
        values = row[4:]
        if tag == "pr":
            self._require_count(values, len(PROCESS_FIELDS), tag)
            record["process_name"] = values[0]
            record.update(
                {
                    name: parse_int(value, name)
                    for name, value in zip(PROCESS_FIELDS[1:], values[1:], strict=True)
                }
            )
        elif tag == "nt":
            self._require_count(values, len(NETWORK_FIELDS), tag)
            record.update(
                {
                    name: parse_int(value, name)
                    for name, value in zip(NETWORK_FIELDS, values, strict=True)
                }
            )
        elif tag == "m":
            self._require_count(values, len(MISC_FIELDS), tag)
            record.update(
                {
                    name: parse_int(value, name)
                    for name, value in zip(MISC_FIELDS, values, strict=True)
                }
            )
        elif tag == "pwi":
            self._require_count(values, 5, tag)
            record.update(
                {
                    "power_item": values[0],
                    "estimated_charge_mah": parse_float(values[1], "estimated_charge_mah"),
                    "is_hidden_or_system_consumer": bool(
                        parse_int(values[2], "is_hidden_or_system_consumer")
                    ),
                    "screen_estimated_charge_mah": parse_float(
                        values[3], "screen_estimated_charge_mah"
                    ),
                    "proportional_estimated_charge_mah": parse_float(
                        values[4], "proportional_estimated_charge_mah"
                    ),
                }
            )
        elif tag == "wl":
            self._parse_wakelock(values, record)
        return record

    @staticmethod
    def _require_count(values: list[str], expected: int, tag: str) -> None:
        if len(values) != expected:
            raise ParseError(f"tag {tag!r} has {len(values)} data fields; expected {expected}")

    @staticmethod
    def _parse_wakelock(values: list[str], record: Record) -> None:
        if len(values) < 7 or (len(values) - 1) % 6:
            raise ParseError("tag 'wl' must contain a name followed by six-field groups")
        record["wakelock_name"] = values[0]
        seen: set[str] = set()
        for offset in range(1, len(values), 6):
            total_time, type_code, count, current, maximum, total_duration = values[
                offset : offset + 6
            ]
            if type_code not in WAKELOCK_TYPES:
                raise ParseError(f"unknown wakelock type {type_code!r}")
            if type_code in seen:
                raise ParseError(f"duplicate wakelock type {type_code!r}")
            seen.add(type_code)
            prefix = WAKELOCK_TYPES[type_code]
            record.update(
                {
                    f"{prefix}_time_ms": parse_int(total_time, f"{prefix}_time_ms"),
                    f"{prefix}_count": parse_int(count, f"{prefix}_count"),
                    f"{prefix}_current_duration_ms": parse_int(
                        current, f"{prefix}_current_duration_ms"
                    ),
                    f"{prefix}_max_duration_ms": parse_int(maximum, f"{prefix}_max_duration_ms"),
                    f"{prefix}_total_duration_ms": parse_int(
                        total_duration, f"{prefix}_total_duration_ms"
                    ),
                }
            )
