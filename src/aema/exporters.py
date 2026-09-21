"""Collision-safe, atomic export of parsed AEMA results."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from aema.errors import ExportError
from aema.models import PipelineResult


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
