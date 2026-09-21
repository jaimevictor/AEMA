"""Parser for Android package-to-UID output."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from aema.errors import ParseError
from aema.files import open_text
from aema.models import ParseDiagnostics, ParseResult
from aema.normalization import parse_int

PACKAGE_RE = re.compile(r"^package:(\S+)\s+uid:(\d+)$")


class PackageUidParser:
    """Parse exact package/UID records while retaining shared UIDs."""

    def __init__(self, file_path: str | Path, *, strict: bool = True) -> None:
        self.file_path = Path(file_path)
        self.strict = strict
        self.diagnostics = ParseDiagnostics(source=str(self.file_path))

    def parse_result(self) -> ParseResult:
        diagnostics = ParseDiagnostics(source=str(self.file_path))
        records = []
        seen: set[tuple[str, int]] = set()
        try:
            with open_text(self.file_path) as stream:
                for line_number, raw_line in enumerate(stream, start=1):
                    diagnostics.total_lines += 1
                    line = raw_line.strip()
                    if not line:
                        diagnostics.skipped_empty_lines += 1
                        continue
                    match = PACKAGE_RE.fullmatch(line)
                    if not match:
                        message = f"{self.file_path}:{line_number}: invalid package/UID record"
                        if self.strict:
                            raise ParseError(message)
                        diagnostics.warnings.append(message)
                        continue
                    package_name, raw_uid = match.groups()
                    uid = parse_int(raw_uid, "uid")
                    pair = (package_name, uid)
                    if pair in seen:
                        diagnostics.warnings.append(
                            f"{self.file_path}:{line_number}: duplicate package/UID record"
                        )
                    seen.add(pair)
                    records.append(
                        {"package_name": package_name, "uid": uid, "line_number": line_number}
                    )
        except UnicodeDecodeError as exc:
            raise ParseError(f"cannot decode {self.file_path}: {exc}") from exc

        if not records:
            raise ParseError(f"{self.file_path}: no package/UID records found")
        diagnostics.parsed_records = len(records)
        self.diagnostics = diagnostics
        return ParseResult(records, diagnostics)

    def parse(self) -> pd.DataFrame:
        """Compatibility convenience returning a DataFrame."""

        return self.parse_result().to_frame()
