"""Compatibility utilities."""

from pathlib import Path

from aema.exporters import export_pipeline_result
from aema.models import PipelineResult


def persist_result(result: PipelineResult, base_dir: str | Path = "outputs") -> Path:
    """Publish a complete pipeline result in a unique output directory."""

    return export_pipeline_result(result, base_dir)
