from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from aema.exporters import export_pipeline_result
from aema.models import PipelineInputs
from aema.pipeline import run_pipeline


def test_input_to_export_flow_is_complete_and_collision_safe(
    fixture_dir: Path, tmp_path: Path
) -> None:
    inputs = PipelineInputs(
        fixture_dir / "checkin_v9.csv",
        fixture_dir / "battery_report.txt",
        fixture_dir / "packages.txt",
    )
    result = run_pipeline(inputs)
    first = export_pipeline_result(result, tmp_path)
    second = export_pipeline_result(result, tmp_path)
    assert first != second
    assert first.is_dir() and second.is_dir()
    assert {path.name for path in first.iterdir()} == {
        "stats_checkin_parsed.csv",
        "stats_power_estimates_parsed.csv",
        "package_uid_parsed.csv",
        "manifest.json",
    }
    assert len(pd.read_csv(first / "stats_checkin_parsed.csv")) == 5
    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["records"]["packages"]["parsed_records"] == 3
    assert len(manifest["input_sha256"]["checkin"]) == 64
