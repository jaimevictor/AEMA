"""Domain exceptions exposed by AEMA."""


class AemaError(Exception):
    """Base class for expected AEMA failures."""


class InputFileError(AemaError):
    """An input file is missing, unreadable, or uses an unsupported encoding."""


class ParseError(AemaError):
    """An input record violates a supported schema."""


class UnsupportedVersionError(ParseError):
    """The BatteryStats check-in version is not supported."""


class ExportError(AemaError):
    """A complete result set could not be published safely."""
