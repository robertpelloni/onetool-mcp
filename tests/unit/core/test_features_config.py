"""Unit tests for configuration features.

Tests configuration integration with the execution system:
- Config loading produces usable configuration
- Config validation catches errors early
- Variable expansion works in config values

Note: Comprehensive config loading tests are in test_config_loader.py.
These tests focus on config's impact on execution features.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.mark.unit
@pytest.mark.core
class TestConfigLoading:
    """Test config loading produces usable configuration."""

    def test_load_default_config(self) -> None:
        """Default config loads with expected structure."""
        from ot.config.loader import OneToolConfig

        config = OneToolConfig()

        # Essential fields exist
        assert config.version == 1
        assert config.log_level in ["INFO", "DEBUG", "WARNING", "ERROR"]
        assert isinstance(config.tools_dir, list)
        assert isinstance(config.alias, dict)  # Note: singular 'alias'
        assert isinstance(config.snippets, dict)

    def test_load_custom_config(self) -> None:
        """Custom config values override defaults."""
        from ot.config.loader import load_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test-config.yaml"
            config_path.write_text(
                yaml.dump(
                    {
                        "version": 1,
                        "log_level": "DEBUG",
                        "alias": {"test_alias": "demo.foo"},  # Note: singular 'alias'
                    }
                )
            )

            config = load_config(config_path)

            assert config.log_level == "DEBUG"
            assert "test_alias" in config.alias
            assert config.alias["test_alias"] == "demo.foo"


@pytest.mark.unit
@pytest.mark.core
class TestConfigValidation:
    """Test config validation catches invalid configurations."""

    def test_invalid_version_rejected(self) -> None:
        """Future versions are rejected with helpful error."""
        from ot.config.loader import load_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test-config.yaml"
            config_path.write_text(yaml.dump({"version": 999}))

            with pytest.raises(ValueError, match="version 999 is not supported"):
                load_config(config_path)

    def test_invalid_yaml_rejected(self) -> None:
        """Malformed YAML produces clear error."""
        from ot.config.loader import load_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test-config.yaml"
            config_path.write_text("invalid: yaml: content: ::::")

            with pytest.raises(ValueError, match="Invalid YAML"):
                load_config(config_path)

    def test_invalid_tool_config_loads_but_validates_at_runtime(self) -> None:
        """Tool config loads (validation happens at runtime via get_tool_config)."""
        from ot.config.loader import load_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test-config.yaml"
            config_path.write_text(
                yaml.dump(
                    {
                        "version": 1,
                        "tools": {
                            "brave": {"timeout": 0.5},  # Below minimum
                        },
                    }
                )
            )

            # Now loads without error - validation happens at get_tool_config() time
            config = load_config(config_path)
            # Config is stored as dict, accessible via model_extra
            assert config.tools.model_extra.get("brave", {}).get("timeout") == 0.5


@pytest.mark.unit
@pytest.mark.core
class TestConfigVariableExpansion:
    """Test variable expansion in config values."""

    def test_variable_with_default(self) -> None:
        """${VAR:-default} not expanded during load - happens at runtime."""
        from ot.config.loader import load_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".onetool" / "config"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "onetool.yaml"
            config_path.write_text(
                yaml.dump(
                    {
                        "version": 1,
                        "secrets_file": "${NONEXISTENT_VAR:-/default}/secrets.yaml",
                    }
                )
            )

            # Config loads successfully - no expansion during load
            config = load_config(config_path)
            # Raw value still has ${VAR}
            assert "${NONEXISTENT_VAR" in config.secrets_file

    def test_missing_variable_error(self) -> None:
        """${VAR} without default is stored as-is during load."""
        from ot.config.loader import load_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".onetool" / "config"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "onetool.yaml"
            config_path.write_text(
                yaml.dump(
                    {
                        "version": 1,
                        "secrets_file": "${MISSING_VAR}/secrets.yaml",
                    }
                )
            )

            # Config loads successfully - expansion happens at runtime, not load time
            config = load_config(config_path)
            # Raw value still has ${VAR}
            assert "${MISSING_VAR}" in config.secrets_file
