"""Smoke tests for onetool-util - verify basic functionality."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.pkg


@pytest.mark.smoke
def test_import_package():
    """Test that the package can be imported."""
    import otutil

    assert otutil.__version__ == "1.0.0"
    assert otutil.__package_name__ == "onetool-util"


@pytest.mark.smoke
def test_import_server():
    """Test that the server module can be imported."""
    pytest.importorskip("otutil.server", reason="otutil.server not present in this project")
    from otutil.server import create_server

    assert callable(create_server)


@pytest.mark.smoke
def test_import_cli():
    """Test that the CLI module can be imported."""
    pytest.importorskip("otutil.cli", reason="otutil.cli not present in this project")
    from otutil.cli import app, cli

    assert app is not None
    assert callable(cli)


@pytest.mark.smoke
def test_import_tool_modules():
    """Test that all tool modules can be imported."""
    pytest.importorskip("otutil.tools.convert", reason="convert requires pymupdf", exc_type=ImportError)
    from otutil.tools import brave, convert, excel, file, ground

    # Check pack names
    assert file.pack == "file"
    assert excel.pack == "excel"
    assert convert.pack == "convert"
    assert brave.pack == "brave"
    assert ground.pack == "ground"


@pytest.mark.smoke
def test_server_creation():
    """Test that a server can be created without config."""
    pytest.importorskip("otutil.server", reason="otutil.server not present in this project")
    from otutil.server import create_server

    # Should work without config (optional)
    server = create_server()

    assert server is not None
    assert server.name == "onetool-util"


@pytest.mark.smoke
def test_server_creation_with_config(tmp_config: Path):
    """Test that a server can be created (config fixture for future use)."""
    pytest.importorskip("otutil.server", reason="otutil.server not present in this project")
    from otutil.server import create_server

    # TODO: When config loading is implemented, pass config_path
    server = create_server()

    assert server is not None
    assert server.name == "onetool-util"


@pytest.mark.smoke
def test_cli_version():
    """Test that CLI version command works."""
    pytest.importorskip("otutil.cli", reason="otutil.cli not present in this project")
    from typer.testing import CliRunner

    from otutil.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "1.0.0" in result.output


@pytest.mark.smoke
def test_cli_serve_accepts_config_and_secrets(tmp_path: Path):
    """Test that serve command accepts --config and --secrets options."""
    pytest.importorskip("otutil.cli", reason="otutil.cli not present in this project")
    from typer.testing import CliRunner

    from otutil.cli import app

    config_file = tmp_path / "util.yaml"
    config_file.write_text("version: 1\nlog_level: INFO\n")

    runner = CliRunner()
    # Use --help to verify options exist without actually starting the server
    result = runner.invoke(app, ["serve", "--help"])

    assert result.exit_code == 0
    assert "--config" in result.output
    assert "--secrets" in result.output
