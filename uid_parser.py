"""Backward-compatible import for the package-to-UID parser."""

from aema.parsers.packages import PackageUidParser


class UidParser(PackageUidParser):
    """Deprecated alias; use :class:`aema.parsers.packages.PackageUidParser`."""
