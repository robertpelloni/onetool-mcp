"""Tests for secrets loading."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from ot.config.secrets import expand_vars, get_secret, get_secrets, load_secrets


@pytest.mark.unit
@pytest.mark.core
class TestLoadSecrets:
    """Tests for load_secrets function."""

    def test_loads_secrets_from_yaml_file(self, tmp_path: Path) -> None:
        """Should load secrets from a YAML file."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("""
BRAVE_API_KEY: "test-brave-key"
OPENAI_API_KEY: "sk-test-key"
""")

        result = load_secrets(secrets_file)

        assert result["BRAVE_API_KEY"] == "test-brave-key"
        assert result["OPENAI_API_KEY"] == "sk-test-key"

    def test_returns_empty_dict_for_missing_file(self, tmp_path: Path) -> None:
        """Should return empty dict when file doesn't exist."""
        result = load_secrets(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_returns_empty_dict_for_empty_file(self, tmp_path: Path) -> None:
        """Should return empty dict for empty YAML file."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("")

        result = load_secrets(secrets_file)
        assert result == {}

    def test_values_are_literal_no_env_expansion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should NOT expand ${VAR_NAME} - values are literal."""
        monkeypatch.setenv("MY_SECRET_VALUE", "secret-from-env")

        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("""
API_KEY: "${MY_SECRET_VALUE}"
""")

        result = load_secrets(secrets_file)
        # Value is stored literally, no expansion
        assert result["API_KEY"] == "${MY_SECRET_VALUE}"

    def test_env_var_syntax_is_literal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should store ${VAR} syntax as literal string."""
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)

        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("""
API_KEY: "${NONEXISTENT_VAR}"
""")

        result = load_secrets(secrets_file)
        # Value is stored literally
        assert result["API_KEY"] == "${NONEXISTENT_VAR}"

    def test_raises_for_invalid_yaml(self, tmp_path: Path) -> None:
        """Should raise ValueError for invalid YAML."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("""
invalid: yaml: content:
  - [broken
""")

        with pytest.raises(ValueError, match="Invalid YAML"):
            load_secrets(secrets_file)

    def test_raises_for_non_mapping_yaml(self, tmp_path: Path) -> None:
        """Should raise ValueError when YAML is not a mapping."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("""
- item1
- item2
""")

        with pytest.raises(ValueError, match="must be a YAML mapping"):
            load_secrets(secrets_file)

    def test_skips_none_values(self, tmp_path: Path) -> None:
        """Should skip keys with None values."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("""
API_KEY: "valid-key"
EMPTY_KEY:
""")

        result = load_secrets(secrets_file)
        assert "API_KEY" in result
        assert "EMPTY_KEY" not in result

    def test_converts_non_string_values(self, tmp_path: Path) -> None:
        """Should convert non-string values to strings."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text("""
PORT: 8080
DEBUG: true
""")

        result = load_secrets(secrets_file)
        assert result["PORT"] == "8080"
        assert result["DEBUG"] == "True"


@pytest.mark.unit
@pytest.mark.core
class TestGetSecrets:
    """Tests for get_secrets caching function."""

    def test_caches_secrets(self, tmp_path: Path) -> None:
        """Should cache secrets after first load."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text('API_KEY: "cached-key"')

        import ot.config.secrets as secrets_module

        secrets_module._secrets = None

        # First call loads with explicit path
        result1 = get_secrets(secrets_file)
        # Second call uses cache (no path needed)
        result2 = get_secrets()

        assert result1 is result2
        assert result1["API_KEY"] == "cached-key"

        # Cleanup
        secrets_module._secrets = None

    def test_reload_forces_fresh_load(self, tmp_path: Path) -> None:
        """Should reload when reload=True."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text('API_KEY: "original-key"')

        import ot.config.secrets as secrets_module

        secrets_module._secrets = None

        result1 = get_secrets(secrets_file)
        assert result1["API_KEY"] == "original-key"

        # Modify the file
        secrets_file.write_text('API_KEY: "updated-key"')

        # Without reload, should still have old value
        result2 = get_secrets()
        assert result2["API_KEY"] == "original-key"

        # With reload and explicit path, should get new value
        result3 = get_secrets(secrets_file, reload=True)
        assert result3["API_KEY"] == "updated-key"

        # Cleanup
        secrets_module._secrets = None

    def test_none_path_returns_empty(self) -> None:
        """get_secrets(None) returns empty dict when no cache."""
        import ot.config.secrets as secrets_module

        secrets_module._secrets = None

        result = get_secrets(None)
        assert result == {}

        secrets_module._secrets = None


@pytest.mark.unit
@pytest.mark.core
class TestGetSecret:
    """Tests for get_secret convenience function."""

    def test_returns_secret_value(self, tmp_path: Path) -> None:
        """Should return secret value by name."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text('MY_SECRET: "secret-value"')

        import ot.config.secrets as secrets_module

        secrets_module._secrets = None
        get_secrets(secrets_file)

        result = get_secret("MY_SECRET")
        assert result == "secret-value"

        # Cleanup
        secrets_module._secrets = None

    def test_returns_none_for_missing_secret(self, tmp_path: Path) -> None:
        """Should return None for non-existent secret."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text('OTHER_KEY: "value"')

        import ot.config.secrets as secrets_module

        secrets_module._secrets = None
        get_secrets(secrets_file)

        result = get_secret("NONEXISTENT")
        assert result is None

        # Cleanup
        secrets_module._secrets = None


@pytest.mark.unit
@pytest.mark.core
class TestExpandVars:
    """Tests for expand_vars function (secrets + env expansion)."""

    def test_expands_from_secrets_first(self, tmp_path: Path) -> None:
        """Should expand ${VAR} from secrets.yaml first."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text('API_KEY: "secret-key-123"')

        import ot.config.secrets as secrets_module

        secrets_module._secrets = None
        get_secrets(secrets_file)

        result = expand_vars("${API_KEY}")
        assert result == "secret-key-123"

        # Cleanup
        secrets_module._secrets = None

    def test_expands_from_config_env_second(self, tmp_path: Path) -> None:
        """Should expand ${VAR} from config env: section if not in secrets."""
        import ot.config.loader as loader_module
        import ot.config.secrets as secrets_module

        secrets_module._secrets = {}  # Empty secrets - won't find DATA_DIR here
        loader_module._config = None

        # Create a config with env section
        config_dir = tmp_path / ".onetool"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "onetool.yaml"
        config_path.write_text(
            """
version: 2
env:
  DATA_DIR: /data/onetool
  CACHE_DIR: /tmp/cache
"""
        )

        # Load and cache config using get_config()
        from ot.config.loader import get_config

        get_config(config_path)

        # Now expand_vars should use config env
        result = expand_vars("${DATA_DIR}/files")
        assert result == "/data/onetool/files"

        # Cleanup
        secrets_module._secrets = None
        loader_module._config = None

    def test_secrets_take_precedence_over_env(
        self, tmp_path: Path
    ) -> None:
        """Should use secrets.yaml value when variable exists in both."""
        import ot.config.loader as loader_module
        import ot.config.secrets as secrets_module

        secrets_module._secrets = None
        loader_module._config = None

        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text('API_KEY: "from-secrets"')

        config_path = tmp_path / "onetool.yaml"
        config_path.write_text(
            """
version: 2
env:
  API_KEY: from-env
"""
        )

        from ot.config.loader import get_config

        get_config(config_path)
        get_secrets(secrets_file, reload=True)  # force-reload: load_config cleared secrets

        # Should use secrets value (higher precedence)
        result = expand_vars("${API_KEY}")
        assert result == "from-secrets"

        # Cleanup
        secrets_module._secrets = None
        loader_module._config = None

    def test_uses_default_when_not_found(self) -> None:
        """Should use default value when variable not in secrets or env."""
        import ot.config.secrets as secrets_module

        secrets_module._secrets = {}

        result = expand_vars("${UNKNOWN:-default-value}")
        assert result == "default-value"

        # Cleanup
        secrets_module._secrets = None

    def test_raises_when_not_found_and_no_default(self) -> None:
        """Should raise error when variable not found and no default."""
        import ot.config.secrets as secrets_module

        secrets_module._secrets = {}

        with pytest.raises(ValueError, match="Missing variables: UNKNOWN"):
            expand_vars("${UNKNOWN}")

        # Cleanup
        secrets_module._secrets = None

    def test_expands_multiple_vars(self, tmp_path: Path) -> None:
        """Should expand multiple ${VAR} patterns in one string."""
        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.write_text(
            """
API_KEY: "key123"
API_SECRET: "secret456"
"""
        )

        import ot.config.secrets as secrets_module

        secrets_module._secrets = None
        get_secrets(secrets_file)

        result = expand_vars("key=${API_KEY}&secret=${API_SECRET}")
        assert result == "key=key123&secret=secret456"

        # Cleanup
        secrets_module._secrets = None
