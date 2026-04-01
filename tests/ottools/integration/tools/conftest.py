"""Shared fixtures for integration tests."""

from __future__ import annotations

import pytest

from tests._test_secrets import _secrets, _secrets_module, get_test_secret

__all__ = ["get_test_secret"]


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
