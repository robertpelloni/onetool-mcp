"""Path security utilities for file operations.

Provides shared path validation and security checking for tools that
perform file I/O. Enforces directory sandboxing and exclude patterns.

Usage:
    from ot.utils.pathsec import validate_path, DEFAULT_EXCLUDE_PATTERNS

    resolved, error = validate_path("some/file.txt", must_exist=True)
    if error:
        return f"Access denied: {error}"
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from ot.paths import resolve_cwd_path

DEFAULT_EXCLUDE_PATTERNS: list[str] = [
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
]


def is_path_excluded(path: Path, exclude_patterns: list[str]) -> bool:
    """Check if path matches any exclude pattern.

    Uses fnmatch for shell-style pattern matching against both the full
    path string and individual path components.

    Args:
        path: Resolved path to check.
        exclude_patterns: List of fnmatch patterns.

    Returns:
        True if path matches any exclude pattern.
    """
    path_str = str(path)
    path_parts = path.parts

    for pattern in exclude_patterns:
        if fnmatch.fnmatch(path_str, f"*{pattern}*"):
            return True
        for part in path_parts:
            if fnmatch.fnmatch(part, pattern):
                return True

    return False


def validate_path(
    path: str,
    *,
    must_exist: bool = True,
    allowed_dirs: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> tuple[Path | None, str | None]:
    """Validate and resolve a path against security constraints.

    Resolves the path relative to the project working directory (OT_CWD),
    then checks it against allowed directories and exclude patterns.

    Args:
        path: User-provided path string.
        must_exist: If True, path must exist on disk.
        allowed_dirs: Allowed directory paths. None means cwd only.
        exclude_patterns: fnmatch patterns to exclude. None uses defaults.

    Returns:
        Tuple of (user_path, error_message).
        On error, user_path is None.
        user_path preserves symlinks for type detection; security is
        validated against the fully resolved (symlink-followed) path.
    """
    if exclude_patterns is None:
        exclude_patterns = DEFAULT_EXCLUDE_PATTERNS

    try:
        cwd = resolve_cwd_path(".")
        p = Path(path).expanduser()
        user_path = p if p.is_absolute() else cwd / p
        # Resolve for security validation (follows symlinks)
        real_path = user_path.resolve()
    except (OSError, ValueError) as e:
        return None, f"Invalid path: {e}"

    if must_exist and not user_path.exists():
        return None, f"Path not found: {path}"

    # Build allowed directory list
    resolved_allowed: list[Path] = []

    if allowed_dirs:
        for dir_str in allowed_dirs:
            resolved_allowed.append(resolve_cwd_path(dir_str))
    else:
        resolved_allowed = [cwd]

    # Verify path is under an allowed directory
    is_allowed = False
    for allowed in resolved_allowed:
        try:
            real_path.relative_to(allowed)
            is_allowed = True
            break
        except ValueError:
            continue

    if not is_allowed:
        return None, "Access denied: path outside allowed directories"

    if is_path_excluded(real_path, exclude_patterns):
        return None, "Access denied: path matches exclude pattern"

    return user_path, None
