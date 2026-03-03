"""Duration string parsing utility.

Parses human-readable duration strings like '30m', '2h', '1d' into seconds.
"""

from __future__ import annotations

import re

__all__ = ["parse_duration"]

_DURATION_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*([smhd])$")
_MULTIPLIERS = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}


def parse_duration(s: str) -> float:
    """Parse a duration string like '30m', '2h', '1d' into seconds.

    Supports float values and optional whitespace between number and unit.

    Args:
        s: Duration string — e.g. ``"30m"``, ``"1.5h"``, ``"2 d"``.

    Returns:
        Duration in seconds as a float.

    Raises:
        ValueError: If the format is not recognised.

    Example:
        parse_duration("30m")   # 1800.0
        parse_duration("1.5h")  # 5400.0
        parse_duration("2d")    # 172800.0
    """
    m = _DURATION_RE.match(s.strip().lower())
    if not m:
        raise ValueError(
            f"Invalid duration: {s!r}. Use format like '30m', '2h', '1d', '1.5h'"
        )
    value = float(m.group(1))
    unit = m.group(2)
    return value * _MULTIPLIERS[unit]
