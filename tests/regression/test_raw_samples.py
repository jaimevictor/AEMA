from __future__ import annotations

from pathlib import Path

from aema.files import sha256_file
from aema.models import PipelineInputs
from aema.pipeline import run_pipeline


def test_published_fixture_regression(fixture_dir: Path) -> None:
    inputs = PipelineInputs(
        fixture_dir / "checkin_v9.csv",
        fixture_dir / "battery_report.txt",
        fixture_dir / "packages.txt",
    )
    result = run_pipeline(inputs)
    assert sha256_file(inputs.checkin) == (
        "46ACB42DCB10EE84E37E8BACE2DB01EE3430C2782018437C9EBC699CFE82CC43"
    )
    assert sha256_file(inputs.battery_report) == (
        "24C78BDC3F0B95B235750B49AAEDE5990747BC8A1A5CBE28579626696AAF0872"
    )
    assert sha256_file(inputs.packages) == (
        "2CAAEED585AFF775F5FFA6FFF72DC962FA1B839969183E3A13671977FD6F16B9"
    )
    counts = result.checkin.to_frame().groupby("tag").size().to_dict()
    assert counts == {"m": 1, "nt": 1, "pr": 1, "pwi": 1, "wl": 1}
    assert result.battery_report.diagnostics.parsed_records == 3
    assert result.packages.diagnostics.parsed_records == 3
