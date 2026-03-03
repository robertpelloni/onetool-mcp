"""Shared fixtures for integration tests.

Loads and decrypts API keys from project-root secrets.yaml.
Injects them into the runtime secret cache so tools get keys without
depending on the runtime secret resolver path resolution.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import ot.config.secrets as _secrets_module
from ot.config.secrets import load_secrets

# tests/integration/tools/conftest.py → 4 parents to reach project root
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_SECRETS_FILE = (
    _PROJECT_ROOT / "secrets.yaml"
    if (_PROJECT_ROOT / "secrets.yaml").exists()
    else _PROJECT_ROOT / ".onetool" / "secrets.yaml"
)

# IMPORTANT: use load_secrets() — NOT raw yaml.safe_load().
# Secrets in .onetool/secrets.yaml are age-encrypted (values prefixed with
# "age1enc:..."). yaml.safe_load returns the ciphertext, which is useless as
# an API key. load_secrets() decrypts each value transparently via pyrage
# using the age X25519 identity stored in the OS keychain.
_secrets: dict[str, str] = load_secrets(_SECRETS_FILE) if _SECRETS_FILE.exists() else {}


def get_test_secret(name: str) -> str | None:
    """Get a (decrypted) secret value for test skip/fail checks.

    Args:
        name: Secret name (e.g., "BRAVE_API_KEY", "GEMINI_API_KEY")

    Returns:
        Secret value or None if not found
    """
    return _secrets.get(name)


@pytest.fixture(autouse=True)
def _inject_secrets():
    """Inject decrypted test secrets into the runtime cache.

    Sets the module-level _secrets dict directly so all call sites
    (regardless of import style) resolve keys from secrets.yaml.
    """
    old = _secrets_module._secrets
    _secrets_module._secrets = _secrets
    yield
    _secrets_module._secrets = old


__all__ = ["get_test_secret"]
