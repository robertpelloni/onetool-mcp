"""Integration test for graceful cold start with bare onetool.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
@pytest.mark.core
def test_cold_start_bare_config(tmp_path: Path) -> None:
    """Server starts with only 'version: 2' in onetool.yaml (no onetool init needed)."""
    from ot.config.loader import load_config

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    config_path = ot_dir / "onetool.yaml"
    config_path.write_text("version: 2\n")

    # Should load without error
    config = load_config(config_path)
    assert config.version == 2
    assert config.servers is None or config.servers == {}


@pytest.mark.unit
@pytest.mark.core
def test_cold_start_with_include_fallback(tmp_path: Path) -> None:
    """Config with include: [servers.yaml] uses package default when user file absent."""
    from ot.config.loader import load_config

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    config_path = ot_dir / "onetool.yaml"
    config_path.write_text("version: 2\ninclude:\n  - servers.yaml\n")

    # Should load without error using package default servers.yaml
    config = load_config(config_path)
    assert config.version == 2
    # servers.yaml from package default should be loaded
    assert config.servers is not None


@pytest.mark.unit
@pytest.mark.core
def test_cold_start_no_files_in_config_dir(tmp_path: Path) -> None:
    """Only onetool.yaml exists in config dir — server starts using package defaults."""
    from ot.config.loader import load_config

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    config_path = ot_dir / "onetool.yaml"
    # Include security.yaml and servers.yaml — both should fall back to package defaults
    config_path.write_text(
        "version: 2\ninclude:\n  - security.yaml\n  - servers.yaml\n"
    )

    config = load_config(config_path)
    assert config.version == 2
    # Security config from package default
    assert config.security is not None
