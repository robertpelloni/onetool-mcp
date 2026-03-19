"""Test otpack config in standalone mode (no ot.* available).

Tests the standalone fallback paths directly by calling the internal
standalone functions and the public API.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def standalone_config(tmp_path: Path) -> Path:
    """Create a minimal standalone config YAML file."""
    config = {
        "tools": {
            "test_pack": {
                "timeout": 42.0,
                "debug": True,
            }
        }
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))
    return config_path


@pytest.fixture(autouse=True)
def reset_standalone_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset standalone config state before each test."""
    import otpack.config as cfg

    monkeypatch.setattr(cfg, "_standalone_config", None)
    monkeypatch.setattr(cfg, "_standalone_secrets", None)


@pytest.mark.unit
@pytest.mark.pkg
def test_import_succeeds() -> None:
    """otpack should be fully importable."""
    import otpack

    assert hasattr(otpack, "LogSpan")
    assert hasattr(otpack, "get_tool_config")
    assert hasattr(otpack, "configure_standalone")


@pytest.mark.unit
@pytest.mark.pkg
def test_configure_standalone_loads_yaml(standalone_config: Path) -> None:
    """configure_standalone() loads the YAML into standalone config."""
    import otpack.config as cfg
    from otpack import configure_standalone

    configure_standalone(standalone_config)
    assert cfg._standalone_config is not None
    assert "tools" in cfg._standalone_config


@pytest.mark.unit
@pytest.mark.pkg
def test_get_tool_config_reads_from_yaml_standalone(standalone_config: Path) -> None:
    """get_tool_config reads from YAML when ot.config is not available."""
    from pydantic import BaseModel

    from otpack import configure_standalone
    from otpack.config import _get_standalone_tool_config, get_tool_config

    configure_standalone(standalone_config)

    # Test via internal function (guaranteed standalone)
    raw = _get_standalone_tool_config("test_pack")
    assert raw.get("timeout") == 42.0
    assert raw.get("debug") is True

    # Validate config via schema
    class TestConfig(BaseModel):
        timeout: float = 10.0
        debug: bool = False

    config = TestConfig.model_validate(raw)
    assert config.timeout == 42.0
    assert config.debug is True


@pytest.mark.unit
@pytest.mark.pkg
def test_get_tool_config_standalone_returns_defaults_for_missing_pack(
    standalone_config: Path,
) -> None:
    """_get_standalone_tool_config returns empty dict for unknown packs."""
    from otpack import configure_standalone
    from otpack.config import _get_standalone_tool_config

    configure_standalone(standalone_config)
    raw = _get_standalone_tool_config("nonexistent_pack")
    assert raw == {}


@pytest.mark.unit
@pytest.mark.pkg
def test_get_standalone_secret_returns_none_when_not_configured(
    standalone_config: Path,
) -> None:
    """_get_standalone_secret returns None when secret is not configured."""
    from otpack import configure_standalone
    from otpack.config import _get_standalone_secret

    configure_standalone(standalone_config)
    assert _get_standalone_secret("NONEXISTENT_KEY") is None


@pytest.mark.unit
@pytest.mark.pkg
def test_is_log_verbose_defaults_false() -> None:
    """is_log_verbose should default to False when OT_LOG_VERBOSE not set."""
    import os

    env_val = os.environ.pop("OT_LOG_VERBOSE", None)
    try:
        from otpack.config import is_log_verbose

        assert is_log_verbose() is False
    finally:
        if env_val is not None:
            os.environ["OT_LOG_VERBOSE"] = env_val


@pytest.mark.unit
@pytest.mark.pkg
def test_configure_standalone_raises_on_missing_file(tmp_path: Path) -> None:
    """configure_standalone raises FileNotFoundError for missing config."""
    from otpack import configure_standalone

    with pytest.raises(FileNotFoundError):
        configure_standalone(tmp_path / "nonexistent.yaml")


@pytest.mark.unit
@pytest.mark.pkg
def test_configure_standalone_explicit_secrets_path(tmp_path: Path) -> None:
    """configure_standalone() loads secrets from explicit secrets_path."""
    from otpack import configure_standalone
    from otpack.config import _get_standalone_secret

    config_path = tmp_path / "config.yaml"
    config_path.write_text("tools: {}")
    secrets_path = tmp_path / "custom-secrets.yaml"
    secrets_path.write_text("MY_KEY: secret_value\n")

    configure_standalone(config_path, secrets_path=secrets_path)
    assert _get_standalone_secret("MY_KEY") == "secret_value"


@pytest.mark.unit
@pytest.mark.pkg
def test_configure_standalone_explicit_secrets_path_missing(tmp_path: Path) -> None:
    """configure_standalone() raises FileNotFoundError for missing explicit secrets_path."""
    from otpack import configure_standalone

    config_path = tmp_path / "config.yaml"
    config_path.write_text("tools: {}")

    with pytest.raises(FileNotFoundError, match="Secrets file not found"):
        configure_standalone(config_path, secrets_path=tmp_path / "nonexistent.yaml")


@pytest.mark.unit
@pytest.mark.pkg
def test_configure_standalone_explicit_secrets_path_overrides_adjacent(tmp_path: Path) -> None:
    """Explicit secrets_path takes precedence over adjacent secrets.yaml."""
    from otpack import configure_standalone
    from otpack.config import _get_standalone_secret

    config_path = tmp_path / "config.yaml"
    config_path.write_text("tools: {}")
    # Adjacent secrets.yaml with different value
    (tmp_path / "secrets.yaml").write_text("MY_KEY: adjacent_value\n")
    # Explicit secrets file
    explicit = tmp_path / "explicit.yaml"
    explicit.write_text("MY_KEY: explicit_value\n")

    configure_standalone(config_path, secrets_path=explicit)
    assert _get_standalone_secret("MY_KEY") == "explicit_value"


@pytest.mark.unit
@pytest.mark.pkg
def test_configure_standalone_raises_on_encrypted_secrets(tmp_path: Path) -> None:
    """configure_standalone raises ValueError when secrets.yaml contains age1enc: values."""
    from otpack import configure_standalone

    config_path = tmp_path / "config.yaml"
    config_path.write_text("tools: {}")
    secrets_path = tmp_path / "secrets.yaml"
    secrets_path.write_text("MY_API_KEY: 'age1enc:YWJjZGVmZ2g='\n")

    with pytest.raises(ValueError, match="Encrypted secrets are not supported"):
        configure_standalone(config_path)
