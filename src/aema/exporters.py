"""Collision-safe, atomic export of parsed AEMA results."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from aema.adapters import CanonicalResult, adapt_pipeline
from aema.catalog import CATALOG_VERSION
from aema.errors import ExportError
from aema.models import CANONICAL_SCHEMA_VERSION, PackageUidRelation, PipelineResult, Source

MANIFEST_FORMAT_VERSION = "2.0"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _validate_canonical_result(result: PipelineResult, canonical: CanonicalResult) -> None:
    expected = {
        Source.CHECKIN: result.input_hashes.get("checkin"),
        Source.POWER: result.input_hashes.get("battery_report"),
        Source.PACKAGES: result.input_hashes.get("packages"),
    }
    for record in canonical.records:
        if record.schema_version != CANONICAL_SCHEMA_VERSION:
            raise ExportError("canonical record schema version mismatch")
        expected_hash = expected.get(record.source)
        if expected_hash is None or record.provenance.source is not record.source:
            raise ExportError("canonical record provenance source mismatch")
        if record.provenance.input_sha256 != expected_hash.lower():
            raise ExportError("canonical record input hash mismatch")
    for relation in canonical.relations:
        if not isinstance(relation, PackageUidRelation):
            raise ExportError("canonical relation type mismatch")
        if relation.provenance.source is not Source.PACKAGES:
            raise ExportError("canonical relation provenance source mismatch")
        expected_hash = expected[Source.PACKAGES]
        if expected_hash is None or relation.provenance.input_sha256 != expected_hash.lower():
            raise ExportError("canonical relation input hash mismatch")


def export_canonical_result(
    result: PipelineResult,
    output_root: str | Path,
    *,
    canonical: CanonicalResult | None = None,
) -> Path:
    """Atomically publish historical exports plus versioned canonical artifacts."""
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final_dir = root / f"parsed_{stamp}_{uuid4().hex[:8]}"
    temp_dir = Path(tempfile.mkdtemp(prefix=".aema-export-", dir=root))
    try:
        for filename, frame in result.frames().items():
            frame.to_csv(temp_dir / filename, index=False, encoding="utf-8")
        canonical = adapt_pipeline(result) if canonical is None else canonical
        _validate_canonical_result(result, canonical)
        _write_jsonl(
            temp_dir / "canonical_records.jsonl", [row.to_dict() for row in canonical.records]
        )
        _write_jsonl(
            temp_dir / "canonical_relations.jsonl", [row.to_dict() for row in canonical.relations]
        )
        diagnostics = {
            "unknown_numeric_fields": canonical.diagnostics.unknown_numeric_fields,
            "unknown_numeric_diagnostics": canonical.diagnostics.unknown_numeric_diagnostics,
            "issues": canonical.diagnostics.issues,
        }
        (temp_dir / "canonical_diagnostics.json").write_text(
            json.dumps(diagnostics, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        artifact_sha256 = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest().upper()
            for path in sorted(temp_dir.iterdir())
            if path.name != "manifest.json"
        }
        files = sorted(artifact_sha256)
        manifest = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "input_sha256": result.input_hashes,
            "records": {
                "checkin": result.checkin.diagnostics.as_dict(),
                "battery_report": result.battery_report.diagnostics.as_dict(),
                "packages": result.packages.diagnostics.as_dict(),
            },
            "manifest_format_version": MANIFEST_FORMAT_VERSION,
            "catalog_version": CATALOG_VERSION,
            "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
            "files": files,
            "artifact_sha256": artifact_sha256,
            "counts": {
                "canonical_records": len(canonical.records),
                "package_uid_relations": len(canonical.relations),
                "diagnostic_issues": len(canonical.diagnostics.issues),
            },
            "canonical_diagnostics": diagnostics,
            "limitations": [
                "mAh estimates are not instantaneous current measurements in mA.",
                "Battery report detail metrics use record-level provenance when exact line is unavailable.",
            ],
        }
        (temp_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temp_dir, final_dir)
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ExportError(f"failed to export canonical results: {exc}") from exc
    return final_dir


def export_pipeline_result(result: PipelineResult, output_root: str | Path) -> Path:
    """Write a complete result into a new directory and atomically publish it."""

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final_dir = root / f"parsed_{stamp}_{uuid4().hex[:8]}"
    temp_dir = Path(tempfile.mkdtemp(prefix=".aema-export-", dir=root))
    try:
        for filename, frame in result.frames().items():
            frame.to_csv(temp_dir / filename, index=False, encoding="utf-8")
        manifest = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "input_sha256": result.input_hashes,
            "records": {
                "checkin": result.checkin.diagnostics.as_dict(),
                "battery_report": result.battery_report.diagnostics.as_dict(),
                "packages": result.packages.diagnostics.as_dict(),
            },
        }
        manifest_path = temp_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temp_dir, final_dir)
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ExportError(f"failed to export parsed results: {exc}") from exc
    return final_dir
