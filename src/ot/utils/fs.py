"""File system utilities for OneTool."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["unlink_tracking_bytes"]


def unlink_tracking_bytes(path: Path) -> int:
    """Unlink a file and return bytes freed.

    Returns 0 if the file does not exist or cannot be removed.

    Args:
        path: Path to the file to remove.

    Returns:
        Bytes freed (file size before removal), or 0 if the file was absent
        or an OS error occurred.
    """
    try:
        size = path.stat().st_size
        path.unlink()
        return size
    except FileNotFoundError:
        return 0
    except OSError:
        return 0
