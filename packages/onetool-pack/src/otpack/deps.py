"""Dependency validation utilities for OneTool packs.

Provides decorators and functions for declaring and checking tool dependencies.
Supports both CLI tools (external binaries) and Python libraries.

Example:
    # Decorator usage
    from otpack import requires_cli, requires_lib

    @requires_cli("rg", install="brew install ripgrep")
    @requires_lib("sqlalchemy", install="pip install sqlalchemy")
    def query(sql: str) -> str:
        ...
"""

from __future__ import annotations

import importlib.util
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

__all__ = [
    "Dependency",
    "DepsCheckResult",
    "check_cli",
    "check_lib",
    "check_secret",
    "ensure_cli",
    "ensure_lib",
    "requires_cli",
    "requires_lib",
]

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class Dependency:
    """Represents a single dependency."""

    name: str
    kind: str  # "cli" or "lib"
    install: str = ""
    version: str = ""
    available: bool = False
    error: str = ""


@dataclass
class DepsCheckResult:
    """Result of checking dependencies for a tool or pack."""

    tool: str
    dependencies: list[Dependency] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Check if all dependencies are available."""
        return all(dep.available for dep in self.dependencies)

    @property
    def missing(self) -> list[Dependency]:
        """Get list of missing dependencies."""
        return [dep for dep in self.dependencies if not dep.available]


def requires_cli(
    name: str,
    *,
    install: str = "",
    version_flag: str = "--version",
) -> Callable[[F], F]:
    """Decorator to declare a CLI tool dependency.

    Adds dependency metadata to the function for discovery.
    Does NOT perform runtime checking - use check_cli() for that.

    Args:
        name: CLI command name (e.g., "rg", "ffmpeg", "pandoc")
        install: Installation instructions shown when missing
        version_flag: Flag to check version (default: "--version")

    Returns:
        Decorator that adds dependency metadata to the function
    """

    def decorator(func: F) -> F:
        if not hasattr(func, "__ot_requires__"):
            func.__ot_requires__ = {"cli": [], "lib": []}  # type: ignore[attr-defined]

        func.__ot_requires__["cli"].append(  # type: ignore[attr-defined]
            {"name": name, "install": install, "version_flag": version_flag}
        )
        return func

    return decorator


def requires_lib(
    name: str,
    *,
    install: str = "",
    import_name: str = "",
) -> Callable[[F], F]:
    """Decorator to declare a Python library dependency.

    Adds dependency metadata to the function for discovery.
    Does NOT perform runtime checking - use check_lib() for that.

    Args:
        name: Package name (e.g., "sqlalchemy", "openai")
        install: Installation instructions (default: "pip install {name}")
        import_name: Import name if different from package name

    Returns:
        Decorator that adds dependency metadata to the function
    """

    def decorator(func: F) -> F:
        if not hasattr(func, "__ot_requires__"):
            func.__ot_requires__ = {"cli": [], "lib": []}  # type: ignore[attr-defined]

        func.__ot_requires__["lib"].append(  # type: ignore[attr-defined]
            {
                "name": name,
                "install": install or f"pip install {name}",
                "import_name": import_name or name,
            }
        )
        return func

    return decorator


def check_cli(name: str) -> Dependency:
    """Check if a CLI tool is available in PATH.

    Args:
        name: CLI command name to check

    Returns:
        Dependency object with availability status
    """
    dep = Dependency(name=name, kind="cli")
    path = shutil.which(name)
    if path:
        dep.available = True
    else:
        dep.error = f"'{name}' not found in PATH"
    return dep


def check_lib(name: str, import_name: str = "") -> Dependency:
    """Check if a Python library is importable.

    Args:
        name: Package name
        import_name: Import name if different from package name

    Returns:
        Dependency object with availability status
    """
    dep = Dependency(name=name, kind="lib")
    module_name = import_name or name

    spec = importlib.util.find_spec(module_name)
    if spec is not None:
        dep.available = True
    else:
        dep.error = f"Module '{module_name}' not importable"

    return dep


def check_secret(name: str) -> Dependency:
    """Check if a secret is configured.

    Args:
        name: Secret name (e.g., "BRAVE_API_KEY")

    Returns:
        Dependency object with availability status
    """
    from otpack.config import get_secret

    dep = Dependency(name=name, kind="secret")
    value = get_secret(name)
    if value:
        dep.available = True
    else:
        dep.error = f"Secret '{name}' not configured"
    return dep


def ensure_cli(
    name: str,
    *,
    install: str = "",
) -> str | None:
    """Check CLI availability at runtime, returning error message if missing.

    Args:
        name: CLI command name
        install: Installation instructions

    Returns:
        None if available, error message string if missing
    """
    dep = check_cli(name)
    if dep.available:
        return None
    msg = f"Error: '{name}' CLI tool not found"
    if install:
        msg += f". Install with: {install}"
    return msg


def ensure_lib(
    name: str,
    *,
    import_name: str = "",
    install: str = "",
) -> str | None:
    """Check library availability at runtime, returning error message if missing.

    Args:
        name: Package name
        import_name: Import name if different from package name
        install: Installation instructions

    Returns:
        None if available, error message string if missing
    """
    dep = check_lib(name, import_name)
    if dep.available:
        return None
    install = install or f"pip install {name}"
    return f"Error: '{name}' library not available. Install with: {install}"
