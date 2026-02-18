"""Smoke tests for onetool-dev - verify basic functionality."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.pkg


@pytest.mark.smoke
def test_import_package() -> None:
    """Test that the package can be imported."""
    import otdev

    assert otdev.__version__ == "1.0.0"
    assert otdev.__package_name__ == "onetool-dev"


@pytest.mark.smoke
def test_import_server() -> None:
    """Test that the server module can be imported."""
    pytest.importorskip("otdev.server", reason="otdev.server not present in this project")
    from otdev.server import create_server

    assert callable(create_server)


@pytest.mark.smoke
def test_import_cli() -> None:
    """Test that the CLI module can be imported."""
    pytest.importorskip("otdev.cli", reason="otdev.cli not present in this project")
    from otdev.cli import app, cli

    assert app is not None
    assert callable(cli)


@pytest.mark.smoke
def test_import_tool_modules() -> None:
    """Test that all tool modules can be imported - Phase 2 complete!"""
    from otdev.tools import context7, db, diagram, package, ripgrep, web

    # Check pack names (alphabetical order)
    assert context7.pack == "context7"
    assert db.pack == "db"
    assert diagram.pack == "diagram"
    assert package.pack == "package"
    assert ripgrep.pack == "ripgrep"
    assert web.pack == "web"


@pytest.mark.smoke
def test_server_creation() -> None:
    """Test that a server can be created without config."""
    pytest.importorskip("otdev.server", reason="otdev.server not present in this project")
    from otdev.server import create_server

    # Should work without config (optional)
    server = create_server()

    assert server is not None
    assert server.name == "onetool-dev"


@pytest.mark.smoke
def test_server_creation_with_config(sample_config: dict) -> None:
    """Test that a server can be created (config fixture for future use)."""
    pytest.importorskip("otdev.server", reason="otdev.server not present in this project")
    from otdev.server import create_server

    # TODO: When config loading is implemented, pass config_path
    server = create_server()

    assert server is not None
    assert server.name == "onetool-dev"


@pytest.mark.smoke
def test_cli_version() -> None:
    """Test that CLI version command works."""
    pytest.importorskip("otdev.cli", reason="otdev.cli not present in this project")
    from typer.testing import CliRunner

    from otdev.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "1.0.0" in result.output


@pytest.mark.smoke
def test_cli_serve_accepts_config_and_secrets(tmp_path) -> None:
    """Test that serve command accepts --config and --secrets options."""
    pytest.importorskip("otdev.cli", reason="otdev.cli not present in this project")
    from typer.testing import CliRunner

    from otdev.cli import app

    runner = CliRunner()
    # Use --help to verify options exist without actually starting the server
    result = runner.invoke(app, ["serve", "--help"])

    assert result.exit_code == 0
    assert "--config" in result.output
    assert "--secrets" in result.output
