"""Versioned inventory of the three compatibility exports (R-204.1)."""

from __future__ import annotations

from dataclasses import dataclass

CATALOG_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    field: str
    entity: str
    metric: str | None
    value: str
    unit: str | None
    measurement_kind: str | None
    source: str
    method: str | None
    uid: str | None
    package_name: str | None
    line_number: str | None
    input_sha256: str
    classification: str
    note: str | None = None


def _entry(
    field: str,
    frame: str,
    classification: str,
    *,
    metric: str | None = None,
    unit: str | None = None,
    kind: str | None = None,
    note: str | None = None,
) -> CatalogEntry:
    entity = {"checkin": "checkin_record", "power": "power_record", "packages": "package_uid"}[
        frame
    ]
    return CatalogEntry(
        field,
        entity,
        metric,
        field,
        unit,
        kind,
        frame,
        None,
        "uid" if field == "uid" else None,
        "package_name" if field == "package_name" else None,
        "line_number" if field == "line_number" else None,
        "manifest.input_sha256",
        classification,
        note,
    )


_CHECKIN = """anr_count background_partial_count background_partial_current_duration_ms background_partial_max_duration_ms background_partial_time_ms background_partial_total_duration_ms bluetooth_rx_bytes bluetooth_tx_bytes category checkin_version connectivity_change_count crash_count deep_idle_mode_count deep_idle_mode_time_ms deep_idling_count deep_idling_time_ms estimated_charge_mah foreground_time_ms full_count full_current_duration_ms full_max_duration_ms full_time_ms full_total_duration_ms full_wakelock_time_ms interactive_time_ms is_hidden_or_system_consumer light_idle_mode_count light_idle_mode_time_ms light_idling_count light_idling_time_ms line_number longest_deep_idle_time_ms longest_light_idle_time_ms mobile_active_count mobile_active_time_us mobile_background_rx_bytes mobile_background_rx_packets mobile_background_tx_bytes mobile_background_tx_packets mobile_radio_active_adjusted_time_ms mobile_radio_active_count mobile_radio_active_time_ms mobile_radio_active_unknown_time_ms mobile_rx_bytes mobile_rx_packets mobile_tx_bytes mobile_tx_packets mobile_wakeup_count partial_count partial_current_duration_ms partial_max_duration_ms partial_time_ms partial_total_duration_ms partial_wakelock_time_ms phone_on_time_ms power_item power_save_enabled_time_ms process_name proportional_estimated_charge_mah screen_estimated_charge_mah screen_on_time_ms start_count system_time_ms tag uid user_time_ms wakelock_name wifi_background_rx_bytes wifi_background_rx_packets wifi_background_tx_bytes wifi_background_tx_packets wifi_rx_bytes wifi_rx_packets wifi_tx_bytes wifi_tx_packets wifi_wakeup_count window_count window_current_duration_ms window_max_duration_ms window_time_ms window_total_duration_ms""".split()
_POWER = """actual_drain_max_mah actual_drain_min_mah background_estimated_charge_mah battery_capacity_mah computed_drain_mah cpu_estimated_charge_mah cpu_foreground_estimated_charge_mah foreground_estimated_charge_mah line_number measurement_kind rated_capacity_mah record_type screen_apps_estimated_charge_mah screen_estimated_charge_mah total_estimated_charge_mah typical_capacity_mah uid uid_text unit wakelock_estimated_charge_mah wifi_estimated_charge_mah""".split()
_PACKAGES = ["line_number", "package_name", "uid"]

_TIME_MS = {"ms"}
_COUNT = {"count"}
_BYTES = {"bytes"}
_PACKET = {"packets"}


def _unit(field: str) -> str | None:
    if field.endswith("_time_ms") or field.endswith("_duration_ms"):
        return "ms"
    if field.endswith("_time_us"):
        return "us"
    if field.endswith("_bytes"):
        return "bytes"
    if field.endswith("_packets"):
        return "packets"
    if field.endswith("_mah"):
        return "mAh"
    return None


def _classification(field: str) -> str:
    if field in {"uid", "uid_text", "package_name", "process_name", "wakelock_name", "power_item"}:
        return "identification"
    if field in {
        "category",
        "tag",
        "record_type",
        "unit",
        "measurement_kind",
        "checkin_version",
        "line_number",
    }:
        return "metadata"
    if field in {"is_hidden_or_system_consumer"}:
        return "metadata"
    return "numeric_metric"


CATALOG: tuple[CatalogEntry, ...] = tuple(
    [
        _entry(
            f,
            "checkin",
            _classification(f),
            unit=_unit(f),
            note="unit not present in source"
            if _unit(f) is None and _classification(f) == "numeric_metric"
            else None,
        )
        for f in _CHECKIN
    ]
    + [
        _entry(
            f,
            "power",
            _classification(f),
            unit=_unit(f),
            kind="estimated_or_attributed"
            if f
            not in {"line_number", "record_type", "uid", "uid_text", "unit", "measurement_kind"}
            and _classification(f) == "numeric_metric"
            else None,
            note="source exposes field name but no independent unit" if f == "uid_text" else None,
        )
        for f in _POWER
    ]
    + [
        _entry(
            f,
            "packages",
            _classification(f),
            note="package UID source has no measurement" if f == "package_name" else None,
        )
        for f in _PACKAGES
    ]
)

CATALOG_BY_FIELD = {(entry.source, entry.field): entry for entry in CATALOG}


def assert_catalog_covers(frames: dict[str, object]) -> None:
    """Raise when any current export column lacks an explicit catalog entry."""
    aliases = {
        "stats_checkin_parsed.csv": "checkin",
        "stats_power_estimates_parsed.csv": "power",
        "package_uid_parsed.csv": "packages",
    }
    missing = [
        (name, column)
        for name, frame in frames.items()
        for column in frame.columns
        if (aliases[name], column) not in CATALOG_BY_FIELD
    ]
    if missing:
        raise AssertionError(f"uncatalogued export columns: {missing}")
