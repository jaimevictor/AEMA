from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from aema.errors import ExportError
from aema.exporters import export_pipeline_result
from aema.models import ParseDiagnostics, ParseResult, PipelineResult


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
