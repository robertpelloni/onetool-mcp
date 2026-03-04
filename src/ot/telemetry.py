"""Anonymous startup telemetry via Scarf pixel.

Fires a single non-blocking GET request on each server start.
No user data, no tool call data, no config contents — only:
  event type, version, OS, Python version.

Opt-out: set DO_NOT_TRACK=1 or SCARF_NO_ANALYTICS=1.
See docs/telemetry.md for full disclosure.
"""

from __future__ import annotations

import contextlib
import os
import platform
import sys
import threading
from pathlib import Path

from ot.config.loader import get_config
from ot.support import get_version

_MARKER_FILE = Path.home() / ".onetool_telemetry"
_PIXEL_URL = "https://tel.onetool.beycom.online/a.png?x-pxid=b795389d-3b9d-4a5c-8506-2cdb9d43f5b5"


def _is_opted_out() -> bool:
    """Return True if the user has opted out via environment variables."""
    for var in ("DO_NOT_TRACK", "SCARF_NO_ANALYTICS"):
        val = os.environ.get(var, "")
        if val and val != "0":
            return True
    return False


def _fire(params: dict[str, str]) -> None:
    """Send the Scarf pixel GET request. All errors are silently ignored."""
    with contextlib.suppress(Exception):
        import httpx

        httpx.get(_PIXEL_URL, params=params, timeout=5.0)


def ping() -> None:
    """Determine telemetry event and fire it in a daemon thread.

    Events:
      install  — first ever start (marker file absent)
      upgrade  — version in marker differs from running version
      start    — all other starts
    """
    if _is_opted_out():
        return

    if not get_config().telemetry.enabled:
        return

    current_version = get_version()

    # Determine event by reading marker file
    params: dict[str, str] = {
        "v": current_version,
        "os": platform.system(),
        "py": f"{sys.version_info.major}.{sys.version_info.minor}",
    }

    try:
        stored_version = _MARKER_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        stored_version = None

    if stored_version is None:
        params["e"] = "install"
    elif stored_version != current_version:
        params["e"] = "upgrade"
        params["v_from"] = stored_version
        params["v_to"] = current_version
    else:
        params["e"] = "start"

    # Update marker file (silent failure — ping still fires with stale event)
    with contextlib.suppress(Exception):
        _MARKER_FILE.write_text(current_version, encoding="utf-8")

    t = threading.Thread(target=_fire, args=(params,), daemon=True)
    t.start()
