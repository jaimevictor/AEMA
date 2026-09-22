"""Small, explicit normalization functions with no persistence side effects."""

from __future__ import annotations

import math
import re

from aema.errors import ParseError

PER_USER_RANGE = 100_000
FIRST_APPLICATION_UID = 10_000
NUMBER_PATTERN = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_NUMBER_RE = re.compile(rf"^{NUMBER_PATTERN}$")
_ANDROID_APP_UID_RE = re.compile(r"^u(?P<user>\d+)a(?P<app_index>\d+)$")

_STATE_NAMES = {
    "fg": "foreground",
    "bg": "background",
    "fgs": "foreground_service",
    "cached": "cached",
}


def parse_int(value: str, field: str, line_number: int | None = None) -> int:
    """Parse an integer or raise a location-rich domain error."""
    try:
        return int(value)
    except ValueError as exc:
        location = f"line {line_number}: " if line_number is not None else ""
        raise ParseError(f"{location}invalid integer for {field}: {value!r}") from exc


def parse_float(value: str, field: str, line_number: int | None = None) -> float:
    """Parse a signed decimal or scientific-notation number."""
    if not _NUMBER_RE.fullmatch(value):
        location = f"line {line_number}: " if line_number is not None else ""
        raise ParseError(f"{location}invalid number for {field}: {value!r}")
    parsed = float(value)
    if not math.isfinite(parsed):
        location = f"line {line_number}: " if line_number is not None else ""
        raise ParseError(f"{location}non-finite number for {field}: {value!r}")
    return parsed


def normalize_android_uid(value: str, *, line_number: int = 0) -> int:
    """Convert numeric or Android `u<user>a<app-index>` UIDs to integer UIDs."""
    if value.isdigit():
        return int(value)
    match = _ANDROID_APP_UID_RE.fullmatch(value)
    if not match:
        raise ParseError(f"line {line_number}: unsupported UID format: {value!r}")
    user_id = int(match.group("user"))
    app_id = FIRST_APPLICATION_UID + int(match.group("app_index"))
    return user_id * PER_USER_RANGE + app_id


def normalize_power_key(raw_key: str) -> str:
    """Create a descriptive mAh column name from a BatteryStats power key."""
    component, separator, state = raw_key.partition(":")
    component = re.sub(r"[^a-z0-9]+", "_", component.lower()).strip("_")
    if separator:
        state_name = _STATE_NAMES.get(state, re.sub(r"[^a-z0-9]+", "_", state.lower()))
        return f"{component}_{state_name}_estimated_charge_mah"
    return f"{component}_estimated_charge_mah"


def normalize_process_state_key(raw_key: str) -> str:
    """Name UID-level process-state attribution in mAh."""
    state_name = _STATE_NAMES.get(raw_key, raw_key)
    return f"{state_name}_estimated_charge_mah"
