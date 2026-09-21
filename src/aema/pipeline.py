"""Application orchestration for the three supported AEMA inputs."""

from __future__ import annotations

from aema.files import sha256_file
from aema.models import PipelineInputs, PipelineResult
from aema.parsers.battery_report import BatteryReportParser
from aema.parsers.checkin import CheckinParser
from aema.parsers.packages import PackageUidParser


def run_pipeline(inputs: PipelineInputs, *, strict: bool = True) -> PipelineResult:
    """Validate and parse every input, returning data without writing files."""

    checkin = CheckinParser(inputs.checkin, strict=strict).parse_result()
    battery_report = BatteryReportParser(inputs.battery_report, strict=strict).parse_result()
    packages = PackageUidParser(inputs.packages, strict=strict).parse_result()
    hashes = {
        "checkin": sha256_file(inputs.checkin),
        "battery_report": sha256_file(inputs.battery_report),
        "packages": sha256_file(inputs.packages),
    }
    return PipelineResult(checkin, battery_report, packages, hashes)


parse_inputs = run_pipeline
