"""Generic duration parsing for reminders and timers (no upper cap)."""

from __future__ import annotations

import re
from datetime import timedelta

_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
_TOKEN = re.compile(r"(\d+)\s*([smhdw])", re.IGNORECASE)
# The whole string must be one or more duration tokens — reject trailing garbage.
_DURATION = re.compile(r"(?:\d+\s*[smhdw]\s*)+", re.IGNORECASE)


def parse_duration(text: str) -> timedelta:
    """Parse '10m', '2h30m', '1d', '1w' into a timedelta.

    Raises ValueError if empty or if the string isn't entirely duration tokens.
    """
    if not _DURATION.fullmatch(text.strip()):
        raise ValueError("Duration must look like `10m`, `2h30m`, or `1d`.")
    seconds = 0
    for amount, unit in _TOKEN.findall(text):
        seconds += int(amount) * _UNITS[unit.lower()]
    if seconds <= 0:
        raise ValueError("Duration must look like `10m`, `2h30m`, or `1d`.")
    return timedelta(seconds=seconds)
