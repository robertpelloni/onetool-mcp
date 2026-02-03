"""Smoke tests for the onetool CLI."""

from __future__ import annotations

import subprocess

import pytest


@pytest.mark.smoke
@pytest.mark.serve
def test_onetool_help() -> None:
    """Verify onetool --help runs successfully."""
    result = subprocess.run(
        ["uv", "run", "onetool", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "OneTool MCP server" in result.stdout


@pytest.mark.smoke
@pytest.mark.serve
def test_onetool_version() -> None:
    """Verify onetool --version runs successfully."""
    result = subprocess.run(
        ["uv", "run", "onetool", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "onetool" in result.stdout


# ==================== Init Subcommand Tests ====================


@pytest.mark.smoke
@pytest.mark.serve
def test_onetool_init_help() -> None:
    """Verify onetool init --help runs successfully."""
    result = subprocess.run(
        ["uv", "run", "onetool", "init", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "reset" in result.stdout
    assert "validate" in result.stdout


@pytest.mark.smoke
@pytest.mark.serve
def test_onetool_init_creates_directory(tmp_path: pytest.TempPathFactory) -> None:
    """Verify onetool init creates ~/.onetool/ with subdirs on fresh system."""
    import tempfile
    from pathlib import Path

    # Use a temp dir as the global dir
    with tempfile.TemporaryDirectory() as tmpdir:
        global_dir = Path(tmpdir) / ".onetool"

        result = subprocess.run(
            ["uv", "run", "onetool", "init"],
            capture_output=True,
            text=True,
            timeout=30,
            env={**__import__("os").environ, "OT_GLOBAL_DIR": str(global_dir)},
        )

        assert result.returncode == 0
        assert global_dir.exists()
        assert (global_dir / "config").exists()
        assert (global_dir / "logs").exists()
        assert (global_dir / "stats").exists()
        assert (global_dir / "tools").exists()
        # sessions should NOT exist (removed)
        assert not (global_dir / "sessions").exists()
