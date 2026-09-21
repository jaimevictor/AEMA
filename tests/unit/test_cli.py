from __future__ import annotations

import json
from pathlib import Path

from aema.cli import main


def test_cli_runs_complete_flow(fixture_dir: Path, tmp_path: Path, capsys) -> None:
    exit_code = main(
        [
            "--checkin",
            str(fixture_dir / "checkin_v9.csv"),
            "--battery-report",
            str(fixture_dir / "battery_report.txt"),
            "--packages",
            str(fixture_dir / "packages.txt"),
            "--output-root",
            str(tmp_path),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["record_counts"] == {
        "battery_report": 3,
        "checkin": 5,
        "packages": 3,
    }
    assert Path(payload["output_directory"]).is_dir()


def test_cli_reports_required_input_failure(tmp_path: Path, capsys) -> None:
    exit_code = main(
        [
            "--checkin",
            str(tmp_path / "missing.csv"),
            "--battery-report",
            str(tmp_path / "missing.txt"),
            "--packages",
            str(tmp_path / "missing-packages.txt"),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "does not exist" in captured.err
