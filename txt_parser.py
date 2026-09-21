"""Backward-compatible import for the human BatteryStats parser."""

from aema.parsers.battery_report import BatteryReportParser


class TxtParser(BatteryReportParser):
    """Deprecated alias; use :class:`aema.parsers.battery_report.BatteryReportParser`."""
