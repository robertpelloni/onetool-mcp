"""Shared fixtures for integration tests.

Loads API keys directly from project-root secrets.yaml.
Injects them into the runtime secret cache so tools get keys without
depending on the runtime secret resolver path resolution.
Secret loading itself is tested separately in unit tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import ot.config.secrets as _secrets_module

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
_SECRETS_FILE = _PROJECT_ROOT / "secrets.yaml"

_secrets: dict[str, str] = {}
if _SECRETS_FILE.exists():
    with _SECRETS_FILE.open() as f:
        raw = yaml.safe_load(f) or {}
    _secrets = {k: str(v) for k, v in raw.items() if isinstance(k, str) and v is not None}


def get_test_secret(name: str) -> str | None:
    """Get a secret value for test skip checks."""
    return _secrets.get(name)


@pytest.fixture(autouse=True)
def _inject_secrets():
    """Inject test secrets into the runtime cache.

    Sets the module-level _secrets dict directly so all call sites
    (regardless of import style) resolve keys from secrets.yaml.
    """
    old = _secrets_module._secrets
    _secrets_module._secrets = _secrets
    yield
    _secrets_module._secrets = old


__all__ = ["get_test_secret"]
