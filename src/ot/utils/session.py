"""Session directory lifecycle for OneTool.

One session directory is created per process on first use, named
``<YYYY-MM-DD>-<8hexchars>`` under the configured sessions base dir.
Old session directories are purged at creation time based on the retention policy.
"""

from __future__ import annotations

import contextlib
import secrets
import shutil
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_session_dir: Path | None = None
_lock = threading.Lock()


def get_session_dir() -> Path:
    """Return the session directory for this process, creating it on first call.

    Thread-safe double-checked locking: after the singleton is set, subsequent
    calls return it immediately without acquiring the lock.

    On first call:
    1. Purges session dirs older than ``output.session_retention_days``
    2. Creates ``<sessions_base>/<YYYY-MM-DD>-<8hexchars>/``
    3. Caches the result as a module-level singleton

    Returns:
        Absolute Path to the session directory (already created).
    """
    global _session_dir

    if _session_dir is not None:
        return _session_dir

    with _lock:
        if _session_dir is not None:
            return _session_dir

        from ot.config import get_config
        from ot.meta import resolve_ot_path

        cfg = get_config()
        sessions_base = resolve_ot_path(cfg.output.sessions_dir)
        retention_days = cfg.output.session_retention_days

        sessions_base.mkdir(parents=True, exist_ok=True)
        _purge_old_sessions(sessions_base, retention_days)

        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        hex_id = secrets.token_hex(4)  # 8 hex chars
        session_path = sessions_base / f"{date_str}-{hex_id}"
        session_path.mkdir(parents=True, exist_ok=True)

        _session_dir = session_path

    return _session_dir


def _reset_session_dir() -> None:
    """Reset the singleton (for tests only).

    Call this in fixture teardown to ensure each test gets a fresh session dir.
    """
    global _session_dir
    _session_dir = None


def _purge_old_sessions(sessions_base: Path, retention_days: int) -> None:
    """Delete session directories older than ``retention_days``.

    Uses directory mtime for age comparison. Non-matching entries (files,
    dirs that don't look like session dirs) are skipped silently.

    Args:
        sessions_base: Parent directory containing session subdirs.
        retention_days: Sessions older than this many days are deleted.
    """
    if retention_days <= 0:
        return

    cutoff = time.time() - retention_days * 86400

    for entry in sessions_base.iterdir():
        if not entry.is_dir():
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            with contextlib.suppress(OSError):
                shutil.rmtree(entry)


__all__ = ["_reset_session_dir", "get_session_dir"]
