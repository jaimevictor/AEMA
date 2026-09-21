from __future__ import annotations

from pathlib import Path

from aema.catalog import CATALOG, CATALOG_VERSION, assert_catalog_covers
from aema.models import PipelineInputs
from aema.pipeline import run_pipeline


def test_catalog_covers_all_current_export_columns() -> None:
    root = Path("tests/fixtures")
    result = run_pipeline(
        PipelineInputs(root / "checkin_v9.csv", root / "battery_report.txt", root / "packages.txt")
    )
    assert CATALOG_VERSION == "1.0"
    assert len(CATALOG) == len({(entry.source, entry.field) for entry in CATALOG})
    assert_catalog_covers(result.frames())


def test_catalog_rejects_new_column() -> None:
    root = Path("tests/fixtures")
    result = run_pipeline(
        PipelineInputs(root / "checkin_v9.csv", root / "battery_report.txt", root / "packages.txt")
    )
    frames = result.frames()
    frames["package_uid_parsed.csv"]["new_field"] = 1
    try:
        assert_catalog_covers(frames)
    except AssertionError as exc:
        assert "new_field" in str(exc)
    else:
        raise AssertionError("catalog accepted an uncatalogued column")
