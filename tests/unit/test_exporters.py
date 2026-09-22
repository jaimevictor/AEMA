from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

import aema.exporters as exporters
from aema.catalog import CATALOG_VERSION
from aema.errors import ExportError
from aema.exporters import export_canonical_result, export_pipeline_result
from aema.models import (
    CANONICAL_SCHEMA_VERSION,
    CanonicalRecord,
    PackageUidRelation,
    ParseDiagnostics,
    ParseResult,
    PipelineInputs,
    PipelineResult,
)
from aema.pipeline import run_pipeline


def test_export_failure_removes_partial_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parsed = ParseResult([{"value": 1}], ParseDiagnostics("test", parsed_records=1))
    result = PipelineResult(parsed, parsed, parsed, {"test": "hash"})

    def fail_export(*args, **kwargs) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(pd.DataFrame, "to_csv", fail_export)
    with pytest.raises(ExportError, match="disk full"):
        export_pipeline_result(result, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_canonical_export_round_trip_manifest_and_artifact_hashes(tmp_path: Path) -> None:
    root = Path("tests/fixtures")
    result = run_pipeline(
        PipelineInputs(root / "checkin_v9.csv", root / "battery_report.txt", root / "packages.txt")
    )
    output = export_canonical_result(result, tmp_path)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_format_version"] == "2.0"
    assert manifest["canonical_schema_version"] == CANONICAL_SCHEMA_VERSION
    assert manifest["catalog_version"] == CATALOG_VERSION
    assert manifest["counts"]["canonical_records"] == 88
    assert manifest["counts"]["package_uid_relations"] == 3
    assert set(manifest["files"]) == set(manifest["artifact_sha256"])
    for filename, digest in manifest["artifact_sha256"].items():
        assert digest == hashlib.sha256((output / filename).read_bytes()).hexdigest().upper()
    rows = [
        json.loads(line)
        for line in (output / "canonical_records.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    restored = [CanonicalRecord.from_dict(row) for row in rows]
    assert len(restored) == manifest["counts"]["canonical_records"]
    assert [item.to_dict() for item in restored] == rows
    relation_rows = [
        json.loads(line)
        for line in (output / "canonical_relations.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    relations = [PackageUidRelation.from_dict(row) for row in relation_rows]
    assert len(relations) == manifest["counts"]["package_uid_relations"]
    assert [item.to_dict() for item in relations] == relation_rows
    assert manifest["limitations"]


def test_canonical_export_preserves_historical_csv_golden(tmp_path: Path) -> None:
    root = Path("tests/fixtures")
    result = run_pipeline(
        PipelineInputs(root / "checkin_v9.csv", root / "battery_report.txt", root / "packages.txt")
    )
    output = export_canonical_result(result, tmp_path)
    golden = root / "golden"
    for filename in (
        "stats_checkin_parsed.csv",
        "stats_power_estimates_parsed.csv",
        "package_uid_parsed.csv",
    ):
        assert (output / filename).read_bytes() == (golden / filename).read_bytes()


def test_canonical_export_rejects_result_from_other_execution(tmp_path: Path) -> None:
    root = Path("tests/fixtures")
    first = run_pipeline(
        PipelineInputs(root / "checkin_v9.csv", root / "battery_report.txt", root / "packages.txt")
    )
    second = run_pipeline(
        PipelineInputs(root / "checkin_v9.csv", root / "battery_report.txt", root / "packages.txt")
    )
    second.input_hashes["checkin"] = "0" * 64
    from aema.adapters import adapt_pipeline

    external = adapt_pipeline(second)
    with pytest.raises(ExportError, match="input hash mismatch"):
        export_canonical_result(first, tmp_path, canonical=external)
    assert list(tmp_path.iterdir()) == []


def test_canonical_export_failure_does_not_publish_partial_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = run_pipeline(
        PipelineInputs(
            Path("tests/fixtures/checkin_v9.csv"),
            Path("tests/fixtures/battery_report.txt"),
            Path("tests/fixtures/packages.txt"),
        )
    )

    def fail_export(*args, **kwargs) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(pd.DataFrame, "to_csv", fail_export)
    with pytest.raises(ExportError, match="disk full"):
        export_canonical_result(result, tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("filename", ["canonical_records.jsonl", "canonical_relations.jsonl"])
def test_jsonl_failure_does_not_publish_partial_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str
) -> None:
    root = Path("tests/fixtures")
    result = run_pipeline(
        PipelineInputs(root / "checkin_v9.csv", root / "battery_report.txt", root / "packages.txt")
    )
    original = exporters._write_jsonl

    def fail_selected(path: Path, rows: list[dict]) -> None:
        if path.name == filename:
            raise OSError(f"cannot write {filename}")
        original(path, rows)

    monkeypatch.setattr(exporters, "_write_jsonl", fail_selected)
    with pytest.raises(ExportError, match=filename):
        export_canonical_result(result, tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("stage", ["manifest", "publish"])
def test_finalization_failure_does_not_publish_partial_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    root = Path("tests/fixtures")
    result = run_pipeline(
        PipelineInputs(root / "checkin_v9.csv", root / "battery_report.txt", root / "packages.txt")
    )
    if stage == "manifest":
        original_write = Path.write_text

        def fail_manifest(path: Path, *args, **kwargs):
            if path.name == "manifest.json":
                raise OSError("manifest write failed")
            return original_write(path, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", fail_manifest)
    else:

        def fail_publish(*args) -> None:
            raise OSError("publish failed")

        monkeypatch.setattr(exporters.os, "replace", fail_publish)
    with pytest.raises(ExportError, match="failed"):
        export_canonical_result(result, tmp_path)
    assert list(tmp_path.iterdir()) == []
