"""Unit tests for _resolve_include_path() with global_templates fallback."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
@pytest.mark.core
def test_resolve_include_user_file_found(tmp_path: Path) -> None:
    """User file in OT_DIR is returned when it exists."""
    from ot.config.loader import _resolve_include_path

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    user_file = ot_dir / "servers.yaml"
    user_file.write_text("servers: {}")

    resolved = _resolve_include_path("servers.yaml", ot_dir)

    assert resolved is not None
    assert resolved == user_file.resolve()


@pytest.mark.unit
@pytest.mark.core
def test_resolve_include_fallback_to_package_default(tmp_path: Path) -> None:
    """Falls back to global_templates when user file is absent."""
    from ot.config.loader import _resolve_include_path
    from ot.paths import get_global_templates_dir

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    # Do NOT create servers.yaml in ot_dir

    resolved = _resolve_include_path("servers.yaml", ot_dir)

    global_templates_dir = get_global_templates_dir()
    expected = (global_templates_dir / "servers.yaml").resolve()
    assert resolved is not None
    assert resolved == expected


@pytest.mark.unit
@pytest.mark.core
def test_resolve_include_absolute_path_exists(tmp_path: Path) -> None:
    """Absolute path is used directly when it exists."""
    from ot.config.loader import _resolve_include_path

    abs_file = tmp_path / "my_config.yaml"
    abs_file.write_text("version: 2")
    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    resolved = _resolve_include_path(str(abs_file), ot_dir)

    assert resolved is not None
    assert resolved == abs_file


@pytest.mark.unit
@pytest.mark.core
def test_resolve_include_absolute_path_missing_no_fallback(tmp_path: Path) -> None:
    """Absolute path that doesn't exist returns None (no fallback to global_templates)."""
    from ot.config.loader import _resolve_include_path

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()
    missing_abs = tmp_path / "does_not_exist.yaml"

    resolved = _resolve_include_path(str(missing_abs), ot_dir)

    assert resolved is None


@pytest.mark.unit
@pytest.mark.core
def test_resolve_include_not_found_anywhere(tmp_path: Path) -> None:
    """Returns None when file is absent from both OT_DIR and global_templates."""
    from ot.config.loader import _resolve_include_path

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    resolved = _resolve_include_path("nonexistent_file_xyz.yaml", ot_dir)

    assert resolved is None


@pytest.mark.unit
@pytest.mark.core
def test_resolve_include_user_takes_precedence(tmp_path: Path) -> None:
    """User file in OT_DIR takes precedence over package default."""
    from ot.config.loader import _resolve_include_path
    from ot.paths import get_global_templates_dir

    ot_dir = tmp_path / ".onetool"
    ot_dir.mkdir()

    # Create user-owned servers.yaml
    user_file = ot_dir / "servers.yaml"
    user_file.write_text("servers: {}")

    # Verify package default also exists
    global_templates_dir = get_global_templates_dir()
    assert (global_templates_dir / "servers.yaml").exists()

    resolved = _resolve_include_path("servers.yaml", ot_dir)

    # User file should win
    assert resolved == user_file.resolve()
