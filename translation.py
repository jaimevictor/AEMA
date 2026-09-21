"""Compatibility facade for the former translation helper."""

from aema.normalization import normalize_power_key


class Translation:
    """Keep the historical methods while delegating TXT names to normalization."""

    @staticmethod
    def translate_csv(raw_name: str) -> str:
        return raw_name.strip()

    @staticmethod
    def translate_txt(raw_key: str) -> str:
        return normalize_power_key(raw_key.strip())
