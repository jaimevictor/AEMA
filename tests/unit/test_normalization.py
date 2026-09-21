from __future__ import annotations

import pytest

from aema.errors import ParseError
from aema.normalization import (
    normalize_android_uid,
    normalize_power_key,
    normalize_process_state_key,
    parse_float,
    parse_int,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1000", 1000), ("u0a42", 10042), ("u10a42", 1_010_042)],
)
def test_normalize_android_uid(raw: str, expected: int) -> None:
    assert normalize_android_uid(raw) == expected


def test_normalize_android_uid_rejects_unknown_form() -> None:
    with pytest.raises(ParseError, match="unsupported UID"):
        normalize_android_uid("system")


def test_numeric_parsers_preserve_sign_and_scientific_notation() -> None:
    assert parse_int("-12", "count") == -12
    assert parse_float("+1.25e-3", "charge") == pytest.approx(0.00125)
    with pytest.raises(ParseError, match="invalid integer"):
        parse_int("1.2", "count", 7)
    with pytest.raises(ParseError, match="invalid number"):
        parse_float("12mAh", "charge", 8)


def test_descriptive_power_keys_include_unit_and_state() -> None:
    assert normalize_power_key("mobile_radio:fg") == (
        "mobile_radio_foreground_estimated_charge_mah"
    )
    assert normalize_process_state_key("fgs") == ("foreground_service_estimated_charge_mah")
