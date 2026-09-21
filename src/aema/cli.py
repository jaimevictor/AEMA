"""Command-line entry point for AEMA parsing."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aema.errors import AemaError
from aema.exporters import export_pipeline_result
from aema.models import PipelineInputs
from aema.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aema", description="Parse Android batterystats and package UID files."
    )
    parser.add_argument("--checkin", type=Path, required=True, help="batterystats check-in CSV")
    parser.add_argument(
        "--battery-report", type=Path, required=True, help="human-readable batterystats report"
    )
    parser.add_argument("--packages", type=Path, required=True, help="package UID mapping")
    parser.add_argument(
        "--output-root", type=Path, default=Path("outputs"), help="parent for a new output dir"
    )
    parser.add_argument(
        "--lenient", action="store_true", help="skip malformed records and report warnings"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_pipeline(
            PipelineInputs(args.checkin, args.battery_report, args.packages),
            strict=not args.lenient,
        )
        output_dir = export_pipeline_result(result, args.output_root)
    except AemaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    summary = {
        "output_directory": str(output_dir),
        "record_counts": {
            "checkin": result.checkin.diagnostics.parsed_records,
            "battery_report": result.battery_report.diagnostics.parsed_records,
            "packages": result.packages.diagnostics.parsed_records,
        },
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
