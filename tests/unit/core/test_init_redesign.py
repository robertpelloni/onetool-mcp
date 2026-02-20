"""Unit tests for redesigned onetool init command."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.mark.unit
@pytest.mark.core
def test_write_onetool_yaml_minimal(tmp_path: Path) -> None:
    """Minimal onetool.yaml contains only version: 2 when no includes."""
    from onetool.cli import _write_onetool_yaml

    config_path = tmp_path / "onetool.yaml"
    _write_onetool_yaml(config_path, [])

    data = yaml.safe_load(config_path.read_text())
    assert data["version"] == 2
    assert "include" not in data


@pytest.mark.unit
@pytest.mark.core
def test_write_onetool_yaml_with_includes(tmp_path: Path) -> None:
    """onetool.yaml written with include list."""
    from onetool.cli import _write_onetool_yaml

    config_path = tmp_path / "onetool.yaml"
    _write_onetool_yaml(config_path, ["security.yaml", "servers.yaml"])

    data = yaml.safe_load(config_path.read_text())
    assert data["version"] == 2
    assert data["include"] == ["security.yaml", "servers.yaml"]


@pytest.mark.unit
@pytest.mark.core
def test_materialise_file_security(tmp_path: Path) -> None:
    """--file security.yaml copies security.yaml from package templates."""
    from onetool.cli import _materialise_file

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    result = _materialise_file(ot_dir, "security.yaml")

    assert result is True
    assert (ot_dir / "security.yaml").exists()


@pytest.mark.unit
@pytest.mark.core
def test_materialise_file_unknown(tmp_path: Path) -> None:
    """Unknown file returns False (not a fatal error)."""
    from onetool.cli import _materialise_file

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    result = _materialise_file(ot_dir, "nonexistent_xyz.yaml")

    assert result is False
    assert not (ot_dir / "nonexistent_xyz.yaml").exists()


@pytest.mark.unit
@pytest.mark.core
def test_materialise_servers_yaml_subset(tmp_path: Path) -> None:
    """--servers devtools,playwright creates servers.yaml with only those blocks."""
    from onetool.cli import _materialise_servers_yaml

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    _materialise_servers_yaml(ot_dir, ["devtools", "playwright"])

    servers_yaml = ot_dir / "servers.yaml"
    assert servers_yaml.exists()

    data = yaml.safe_load(servers_yaml.read_text())
    servers = data.get("servers", {})
    assert "devtools" in servers
    assert "playwright" in servers
    assert "github" not in servers


@pytest.mark.unit
@pytest.mark.core
def test_materialise_servers_yaml_all(tmp_path: Path) -> None:
    """All servers materialised when all known names requested."""
    from onetool.cli import _materialise_servers_yaml

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    _materialise_servers_yaml(ot_dir, ["devtools", "playwright", "github"])

    data = yaml.safe_load((ot_dir / "servers.yaml").read_text())
    servers = data.get("servers", {})
    assert len(servers) == 3


@pytest.mark.unit
@pytest.mark.core
def test_materialise_servers_yaml_unknown_skipped(tmp_path: Path) -> None:
    """Unknown server names are skipped without raising."""
    from onetool.cli import _materialise_servers_yaml

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    # Should not raise
    _materialise_servers_yaml(ot_dir, ["devtools", "unknown-server"])

    data = yaml.safe_load((ot_dir / "servers.yaml").read_text())
    servers = data.get("servers", {})
    assert "devtools" in servers
    assert "unknown-server" not in servers


@pytest.mark.unit
@pytest.mark.core
def test_init_validate_include_source_reporting(tmp_path: Path) -> None:
    """init validate shows [user] vs [default] source for each include."""
    from typer.testing import CliRunner

    from onetool.cli import app

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    config_path = ot_dir / "onetool.yaml"

    # Create user-owned security.yaml
    (ot_dir / "security.yaml").write_text("security:\n  validate_code: true\n")
    # Leave servers.yaml absent (will use package default)
    config_path.write_text("version: 2\ninclude:\n  - security.yaml\n  - servers.yaml\n")

    runner = CliRunner()
    result = runner.invoke(app, ["init", "validate", "--config", str(config_path)])

    assert "[user]" in result.output
    assert "[default]" in result.output


@pytest.mark.unit
@pytest.mark.core
def test_init_with_security_flag(tmp_path: Path) -> None:
    """--security materialises security.yaml and writes onetool.yaml with include."""
    from typer.testing import CliRunner

    from onetool.cli import app

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    config_path = ot_dir / "onetool.yaml"

    runner = CliRunner()
    result = runner.invoke(
        app, ["init", "--config", str(config_path), "--security"]
    )

    assert result.exit_code == 0
    assert (ot_dir / "security.yaml").exists()
    data = yaml.safe_load(config_path.read_text())
    assert "security.yaml" in data.get("include", [])


@pytest.mark.unit
@pytest.mark.core
def test_init_with_full_flag(tmp_path: Path) -> None:
    """--full materialises all template YAML files."""
    from typer.testing import CliRunner

    from onetool.cli import app

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    config_path = ot_dir / "onetool.yaml"

    runner = CliRunner()
    result = runner.invoke(
        app, ["init", "--config", str(config_path), "--full"]
    )

    assert result.exit_code == 0
    assert (ot_dir / "security.yaml").exists()
    assert (ot_dir / "servers.yaml").exists()
    assert (ot_dir / "prompts.yaml").exists()


@pytest.mark.unit
@pytest.mark.core
def test_init_with_servers_flag(tmp_path: Path) -> None:
    """--servers devtools,playwright materialises servers.yaml with only those blocks."""
    from typer.testing import CliRunner

    from onetool.cli import app

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    config_path = ot_dir / "onetool.yaml"

    runner = CliRunner()
    result = runner.invoke(
        app, ["init", "--config", str(config_path), "--servers", "devtools,playwright"]
    )

    assert result.exit_code == 0
    assert (ot_dir / "servers.yaml").exists()
    servers_data = yaml.safe_load((ot_dir / "servers.yaml").read_text())
    servers = servers_data.get("servers", {})
    assert "devtools" in servers
    assert "playwright" in servers
    assert "github" not in servers
    data = yaml.safe_load(config_path.read_text())
    assert "servers.yaml" in data.get("include", [])


# =============================================================================
# First-Run No-Config Serve Tests (W5)
# =============================================================================


@pytest.mark.unit
@pytest.mark.core
def test_serve_missing_config_non_interactive_exits(tmp_path: Path) -> None:
    """onetool serve with missing config and non-TTY stdin prints message and exits 1."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from onetool.cli import app

    runner = CliRunner()
    config_path = tmp_path / ".onetool" / "onetool.yaml"

    with patch("onetool.cli._stdin_is_tty", return_value=False):
        result = runner.invoke(app, ["--config", str(config_path)])

    assert result.exit_code == 1
    assert "onetool init" in result.output or "not initialized" in result.output.lower()


@pytest.mark.unit
@pytest.mark.core
def test_serve_missing_config_interactive_declined_exits(tmp_path: Path) -> None:
    """onetool serve with missing config in TTY mode, user declines init — exits 1."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from onetool.cli import app

    runner = CliRunner()
    config_path = tmp_path / ".onetool" / "onetool.yaml"

    with patch("onetool.cli._stdin_is_tty", return_value=True):
        result = runner.invoke(app, ["--config", str(config_path)], input="n\n")

    assert result.exit_code == 1
    assert "onetool init" in result.output or "when ready" in result.output


@pytest.mark.unit
@pytest.mark.core
def test_serve_missing_config_interactive_accepted_calls_ensure_ot_dir(tmp_path: Path) -> None:
    """onetool serve with missing config in TTY mode, user accepts — ensure_ot_dir is called."""
    from unittest.mock import MagicMock, patch

    from typer.testing import CliRunner

    from onetool.cli import app

    runner = CliRunner()
    ot_dir = tmp_path / ".onetool"
    config_path = ot_dir / "onetool.yaml"

    mock_ensure = MagicMock()

    # Mock ot.server at sys.modules level to prevent its module-level configure_logging call
    import sys
    import types

    fake_server = types.ModuleType("ot.server")
    fake_server.main = MagicMock()

    with (
        patch("onetool.cli._stdin_is_tty", return_value=True),
        patch("ot.paths.ensure_ot_dir", mock_ensure),
        patch("ot.config.loader.get_config"),
        patch("onetool.cli._setup_signal_handlers"),
        patch("onetool.cli._print_startup_banner"),
        patch.dict(sys.modules, {"ot.server": fake_server}),
    ):
        result = runner.invoke(app, ["--config", str(config_path)], input="y\n")

    assert mock_ensure.call_count == 1
    assert "Initialized" in result.output
