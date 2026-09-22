"""Parser for the estimated-power section of a human batterystats report."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from aema.errors import ParseError
from aema.files import open_text
from aema.models import ParseDiagnostics, ParseResult, Record
from aema.normalization import (
    NUMBER_PATTERN,
    normalize_android_uid,
    normalize_power_key,
    normalize_process_state_key,
    parse_float,
)

SECTION_HEADER = "Estimated power use (mAh):"
CAPACITY_RE = re.compile(
    rf"^\s*Capacity:\s*({NUMBER_PATTERN}),\s*Rated:\s*({NUMBER_PATTERN}),\s*"
    rf"Typical:\s*({NUMBER_PATTERN}),\s*Computed drain:\s*({NUMBER_PATTERN}),\s*"
    rf"actual drain:\s*({NUMBER_PATTERN})-({NUMBER_PATTERN})\s*$",
    re.IGNORECASE,
)
UID_RE = re.compile(rf"^\s*UID\s+([^:]+):\s*({NUMBER_PATTERN})(.*)$", re.IGNORECASE)
STATE_RE = re.compile(r"\b(fg|bg|fgs|cached):\s*([^\s,)]+)", re.IGNORECASE)
DETAIL_RE = re.compile(r"\b([A-Za-z_]+(?::[A-Za-z_]+)?)=([^\s,)]+)")
GLOBAL_DETAIL_RE = re.compile(
    rf"^\s*([A-Za-z_]+):\s*({NUMBER_PATTERN})\s+apps:\s*({NUMBER_PATTERN})"
)
GLOBAL_DETAIL_CANDIDATE_RE = re.compile(r"^\s*[A-Za-z_]+:\s*\S+\s+apps:\s*\S+")


class BatteryReportParser:
    """Extract summary and UID power estimates without interpreting duration text."""

    def __init__(self, file_path: str | Path, *, strict: bool = True) -> None:
        self.file_path = Path(file_path)
        self.strict = strict
        self.diagnostics = ParseDiagnostics(source=str(self.file_path))

    def parse_result(self) -> ParseResult:
        diagnostics = ParseDiagnostics(source=str(self.file_path))
        records: list[Record] = []
        in_section = False
        found_summary = False
        current_uid: Record | None = None
        try:
            with open_text(self.file_path) as stream:
                for line_number, raw_line in enumerate(stream, start=1):
                    diagnostics.total_lines += 1
                    line = raw_line.rstrip("\r\n")
                    if not in_section:
                        if line.strip() == SECTION_HEADER:
                            in_section = True
                        continue
                    if not line.strip():
                        if records and any(record["record_type"] == "uid" for record in records):
                            break
                        diagnostics.skipped_empty_lines += 1
                        continue
                    if not found_summary:
                        match = CAPACITY_RE.match(line)
                        if match:
                            records.append(self._summary_record(match, line_number))
                            found_summary = True
                            continue
                    uid_match = UID_RE.match(line)
                    if uid_match:
                        current_uid = None
                        try:
                            current_uid = self._uid_record(uid_match, line_number)
                            records.append(current_uid)
                        except (ParseError, ValueError) as exc:
                            message = f"{self.file_path}:{line_number}: {exc}"
                            if self.strict:
                                raise ParseError(message) from exc
                            diagnostics.warnings.append(message)
                        continue
                    if line.lstrip().lower().startswith("uid "):
                        current_uid = None
                        message = f"{self.file_path}:{line_number}: malformed UID power record"
                        if self.strict:
                            raise ParseError(message)
                        diagnostics.warnings.append(message)
                        continue
                    if current_uid is not None:
                        self._add_uid_details(current_uid, line, line_number, diagnostics)
                        continue
                    global_match = GLOBAL_DETAIL_RE.match(line)
                    if global_match and records:
                        component, total, apps = global_match.groups()
                        try:
                            values = {
                                normalize_power_key(component): parse_float(total, component),
                                f"{component.lower()}_apps_estimated_charge_mah": parse_float(
                                    apps, f"{component}_apps"
                                ),
                            }
                        except (ParseError, ValueError) as exc:
                            message = f"{self.file_path}:{line_number}: {exc}"
                            if self.strict:
                                raise ParseError(message) from exc
                            diagnostics.warnings.append(message)
                            continue
                        records[0].update(values)
                        continue
                    if GLOBAL_DETAIL_CANDIDATE_RE.match(line):
                        message = f"{self.file_path}:{line_number}: malformed global power record"
                        if self.strict:
                            raise ParseError(message)
                        diagnostics.warnings.append(message)
        except UnicodeDecodeError as exc:
            raise ParseError(f"cannot decode {self.file_path}: {exc}") from exc
        except OSError as exc:
            raise ParseError(f"cannot read {self.file_path}: {exc}") from exc

        if not in_section:
            raise ParseError(f"{self.file_path}: missing {SECTION_HEADER!r} section")
        if not found_summary:
            raise ParseError(f"{self.file_path}: missing capacity summary")
        if not any(record["record_type"] == "uid" for record in records):
            raise ParseError(f"{self.file_path}: no UID estimates found")
        diagnostics.parsed_records = len(records)
        self.diagnostics = diagnostics
        return ParseResult(records, diagnostics)

    def parse(self) -> pd.DataFrame:
        """Compatibility convenience returning a DataFrame."""

        return self.parse_result().to_frame()

    @staticmethod
    def _common(record_type: str, uid_text: str, line_number: int) -> Record:
        return {
            "record_type": record_type,
            "uid_text": uid_text,
            "unit": "mAh",
            "measurement_kind": "estimated_or_attributed",
            "line_number": line_number,
        }

    def _summary_record(self, match: re.Match[str], line_number: int) -> Record:
        record = self._common("summary", "global", line_number)
        record["uid"] = None
        names = (
            "battery_capacity_mah",
            "rated_capacity_mah",
            "typical_capacity_mah",
            "computed_drain_mah",
            "actual_drain_min_mah",
            "actual_drain_max_mah",
        )
        record.update(
            {
                name: parse_float(value, name)
                for name, value in zip(names, match.groups(), strict=True)
            }
        )
        return record

    def _uid_record(self, match: re.Match[str], line_number: int) -> Record:
        uid_text, total, remainder = match.groups()
        record = self._common("uid", uid_text.strip(), line_number)
        record["uid"] = normalize_android_uid(uid_text)
        record["total_estimated_charge_mah"] = parse_float(total, "total_estimated_charge_mah")
        for state, value in STATE_RE.findall(remainder):
            record[normalize_process_state_key(state)] = parse_float(value, state)
        for key, value in DETAIL_RE.findall(remainder):
            normalized = normalize_power_key(key)
            if normalized in record:
                raise ParseError(f"duplicate detail key {key!r}")
            record[normalized] = parse_float(value, key)
        return record

    def _add_uid_details(
        self,
        record: Record,
        line: str,
        line_number: int,
        diagnostics: ParseDiagnostics,
    ) -> None:
        pending: Record = {}
        for key, value in DETAIL_RE.findall(line):
            normalized = normalize_power_key(key)
            if normalized in record or normalized in pending:
                message = f"{self.file_path}:{line_number}: duplicate detail key {key!r}"
                if self.strict:
                    raise ParseError(message)
                diagnostics.warnings.append(message)
                continue
            try:
                pending[normalized] = parse_float(value, key)
            except (ParseError, ValueError) as exc:
                message = f"{self.file_path}:{line_number}: {exc}"
                if self.strict:
                    raise ParseError(message) from exc
                diagnostics.warnings.append(message)
                return
        record.update(pending)
