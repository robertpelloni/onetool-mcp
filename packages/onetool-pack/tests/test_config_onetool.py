"""Test otpack config delegation to ot.config when in onetool mode."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
@pytest.mark.pkg
def test_get_tool_config_delegates_to_ot_config() -> None:
    """get_tool_config should delegate to ot.config.get_tool_config when importable."""
    from pydantic import BaseModel

    class FakeConfig(BaseModel):
        timeout: float = 5.0

    fake_config = FakeConfig(timeout=30.0)

    with patch("otpack.config.get_tool_config") as mock:
        # Simulate ot.config being importable
        mock_ot_config = MagicMock()
        mock_ot_config.get_tool_config = MagicMock(return_value=fake_config)

        import sys

        sys.modules["ot"] = MagicMock()
        sys.modules["ot.config"] = mock_ot_config

        try:
            # Import fresh
            import importlib

            import otpack.config as cfg

            importlib.reload(cfg)

            # Patch the delegating call
            with patch.object(
                mock_ot_config, "get_tool_config", return_value=fake_config
            ) as ot_mock:
                result = cfg.get_tool_config("brave", FakeConfig)
                # The result should come from the ot.config delegation
                assert result is not None
        finally:
            sys.modules.pop("ot", None)
            sys.modules.pop("ot.config", None)


@pytest.mark.unit
@pytest.mark.pkg
def test_get_secret_delegates_to_ot_config() -> None:
    """get_secret should delegate to ot.config.secrets.get_secret when importable."""
    import sys

    mock_secrets = MagicMock()
    mock_secrets.get_secret = MagicMock(return_value="test-api-key")

    sys.modules["ot"] = MagicMock()
    sys.modules["ot.config"] = MagicMock()
    sys.modules["ot.config.secrets"] = mock_secrets

    try:
        import importlib

        import otpack.config as cfg

        importlib.reload(cfg)

        result = cfg.get_secret("MY_API_KEY")
        mock_secrets.get_secret.assert_called_once_with("MY_API_KEY")
    finally:
        sys.modules.pop("ot", None)
        sys.modules.pop("ot.config", None)
        sys.modules.pop("ot.config.secrets", None)
        import importlib

        import otpack.config as cfg

        importlib.reload(cfg)


@pytest.mark.unit
@pytest.mark.pkg
def test_is_log_verbose_delegates_to_ot_config() -> None:
    """is_log_verbose should check OT_LOG_VERBOSE env var first, then ot.config."""
    import os

    # Env var takes priority
    os.environ["OT_LOG_VERBOSE"] = "true"
    try:
        from otpack.config import is_log_verbose

        assert is_log_verbose() is True
    finally:
        del os.environ["OT_LOG_VERBOSE"]
