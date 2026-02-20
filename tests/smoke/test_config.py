"""Smoke tests for config loading."""

from __future__ import annotations

import pytest


@pytest.mark.smoke
@pytest.mark.core
def test_config_imports() -> None:
    """Verify config module imports successfully."""
    from ot.config import OneToolConfig, get_config, load_config

    # These should all be importable
    assert OneToolConfig is not None
    assert get_config is not None
    assert load_config is not None


@pytest.mark.smoke
@pytest.mark.core
def test_config_has_logging_settings() -> None:
    """Verify OneToolConfig has logging settings with defaults."""
    from ot.config import OneToolConfig

    config = OneToolConfig()
    assert config is not None
    # Check logging settings exist (migrated from Settings)
    assert hasattr(config, "log_level")
    assert hasattr(config, "log_dir")
    assert hasattr(config, "compact_max_length")


@pytest.mark.smoke
@pytest.mark.core
def test_load_config_default(tmp_path: pytest.TempPath) -> None:
    """Verify config loading works when a config file is provided."""
    from ot.config import load_config

    config_path = tmp_path / "onetool.yaml"
    config_path.write_text("version: 2\n")

    config = load_config(config_path)
    assert config is not None
