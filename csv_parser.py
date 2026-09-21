"""Backward-compatible import for the check-in parser."""

from aema.parsers.checkin import CheckinParser


class CsvParser(CheckinParser):
    """Deprecated alias; use :class:`aema.parsers.checkin.CheckinParser`."""
