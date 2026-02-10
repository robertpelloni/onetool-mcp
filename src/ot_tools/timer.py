"""Timer tools for measuring elapsed time across tool calls.

Provides named stopwatch timers that persist across multiple tool calls,
useful for profiling workflows, benchmarking API responses, or capturing
lap times during multi-step operations.

Example:
    timer.start(name="api_bench")
    # ... do work across multiple tool calls ...
    timer.elapsed(name="api_bench", store_as="api_total")
    timer.list()
"""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from ot.logging import LogSpan

pack = "timer"

__all__ = ["clear", "elapsed", "list", "start"]

# Module-level state: active timers and stored results
_timers: dict[str, tuple[float, datetime]] = {}
_results: dict[str, dict[str, Any]] = {}


def start(*, name: str = "_default") -> dict[str, Any]:
    """Start or restart a named timer.

    Args:
        name: Timer name. Defaults to "_default".

    Returns:
        Confirmation with timer name and wall-clock start time.
    """
    with LogSpan(span="timer.start", name=name):
        now_perf = perf_counter()
        now_wall = datetime.now(UTC)
        _timers[name] = (now_perf, now_wall)
        return {"status": "started", "name": name, "started_at": now_wall.isoformat()}


def elapsed(*, name: str = "_default", store_as: str | None = None) -> dict[str, Any] | str:
    """Get elapsed time for a named timer.

    The timer keeps running after this call (lap behaviour).

    Args:
        name: Timer name to check. Defaults to "_default".
        store_as: If provided, store the result under this key for later retrieval via list().

    Returns:
        Dict with elapsed seconds and formatted duration, or error string if timer not found.
    """
    with LogSpan(span="timer.elapsed", name=name):
        if name not in _timers:
            return f"No timer named '{name}' is running. Call timer.start(name='{name}') first."

        start_perf, start_wall = _timers[name]
        elapsed_secs = perf_counter() - start_perf
        result = {
            "name": name,
            "elapsed_seconds": round(elapsed_secs, 6),
            "elapsed_formatted": _format_duration(elapsed_secs),
            "started_at": start_wall.isoformat(),
        }

        if store_as is not None:
            _results[store_as] = result

        return result


def list() -> dict[str, Any]:
    """Return all stored timer results and currently running timers.

    Returns:
        Dict with stored results and active timer names.
    """
    with LogSpan(span="timer.list"):
        active = {
            name: {"started_at": wall.isoformat()}
            for name, (_perf, wall) in _timers.items()
        }
        return {"stored": dict(_results), "active": active}


def clear() -> dict[str, Any]:
    """Clear all running timers. Stored results are preserved.

    Returns:
        Confirmation with count of timers cleared.
    """
    with LogSpan(span="timer.clear"):
        count = len(_timers)
        _timers.clear()
        return {"status": "cleared", "timers_removed": count}


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    if seconds < 60:
        return f"{seconds:.3f}s"
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes)}m {secs:.3f}s"
