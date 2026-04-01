"""Shared test secrets helpers for integration test conftest files.

Loads and decrypts API keys from tests/.onetool/secrets.yaml.
Import this module in conftest.py files to avoid duplicating secrets logic.

IMPORTANT: use load_secrets() — NOT raw yaml.safe_load().
Values are age-encrypted; load_secrets() decrypts via pyrage.
"""

from __future__ import annotations

from pathlib import Path

import ot.config.secrets as _secrets_module
from ot.config.secrets import load_secrets


def _find_project_root() -> Path:
    """Walk up from this file until pyproject.toml is found."""
    p = Path(__file__).resolve().parent
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    raise RuntimeError(f"Could not locate project root from {__file__}")


_PROJECT_ROOT: Path = _find_project_root()
_SECRETS_FILE: Path = _PROJECT_ROOT / "tests" / ".onetool" / "secrets.yaml"

_secrets: dict[str, str] = load_secrets(_SECRETS_FILE) if _SECRETS_FILE.exists() else {}


def get_test_secret(name: str) -> str | None:
    """Return a (decrypted) secret value for test skip/fail checks.

    Args:
        name: Secret name (e.g., "BRAVE_API_KEY", "TAVILY_API_KEY")

    Returns:
        Secret value or None if not configured.
    """
    return _secrets.get(name)


__all__ = ["_PROJECT_ROOT", "_SECRETS_FILE", "_secrets", "_secrets_module", "get_test_secret"]
