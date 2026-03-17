"""Path resolution utilities for OneTool packs.

Provides standalone path helpers that work with or without onetool installed.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["expand_path", "get_effective_cwd", "resolve_cwd_path"]


def get_effective_cwd() -> Path:
    """Get the effective working directory.

    Returns OT_CWD if set, else Path.cwd(). This provides a single point
    of control for working directory resolution across all CLIs.

    Returns:
        Resolved Path for working directory
    """
    env_cwd = os.getenv("OT_CWD")
    if env_cwd:
        return Path(env_cwd).resolve()
    return Path.cwd()


def expand_path(path: str) -> Path:
    """Expand ~ in a path.

    Only expands ~ to home directory. Does NOT expand ${VAR} patterns.

    Args:
        path: Path string potentially containing ~

    Returns:
        Expanded absolute Path
    """
    return Path(path).expanduser().resolve()


def resolve_cwd_path(path: str) -> Path:
    """Resolve a path relative to the project working directory (OT_CWD).

    Args:
        path: Path string (relative, absolute, or with ~)

    Returns:
        Resolved absolute Path

    Behaviour:
        - ~ paths: expanded to home directory
        - Absolute paths: returned unchanged
        - Relative paths: resolved relative to get_effective_cwd()
    """
    p = Path(path).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (get_effective_cwd() / p).resolve()
