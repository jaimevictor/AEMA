"""Supported BatteryStats check-in version 9 schemas."""

SUPPORTED_CHECKIN_VERSION = 9

PROCESS_FIELDS = (
    "process_name",
    "user_time_ms",
    "system_time_ms",
    "foreground_time_ms",
    "start_count",
    "anr_count",
    "crash_count",
)

NETWORK_FIELDS = (
    "mobile_rx_bytes",
    "mobile_tx_bytes",
    "wifi_rx_bytes",
    "wifi_tx_bytes",
    "mobile_rx_packets",
    "mobile_tx_packets",
    "wifi_rx_packets",
    "wifi_tx_packets",
    "mobile_active_time_us",
    "mobile_active_count",
    "bluetooth_rx_bytes",
    "bluetooth_tx_bytes",
    "mobile_wakeup_count",
    "wifi_wakeup_count",
    "mobile_background_rx_bytes",
    "mobile_background_tx_bytes",
    "wifi_background_rx_bytes",
    "wifi_background_tx_bytes",
    "mobile_background_rx_packets",
    "mobile_background_tx_packets",
    "wifi_background_rx_packets",
    "wifi_background_tx_packets",
)

MISC_FIELDS = (
    "screen_on_time_ms",
    "phone_on_time_ms",
    "full_wakelock_time_ms",
    "partial_wakelock_time_ms",
    "mobile_radio_active_time_ms",
    "mobile_radio_active_adjusted_time_ms",
    "interactive_time_ms",
    "power_save_enabled_time_ms",
    "connectivity_change_count",
    "deep_idle_mode_time_ms",
    "deep_idle_mode_count",
    "deep_idling_time_ms",
    "deep_idling_count",
    "mobile_radio_active_count",
    "mobile_radio_active_unknown_time_ms",
    "light_idle_mode_time_ms",
    "light_idle_mode_count",
    "light_idling_time_ms",
    "light_idling_count",
    "longest_light_idle_time_ms",
    "longest_deep_idle_time_ms",
)

WAKELOCK_TYPES = {
    "f": "full",
    "p": "partial",
    "bp": "background_partial",
    "w": "window",
}

SUPPORTED_TAGS = frozenset({"pr", "wl", "nt", "m", "pwi"})
