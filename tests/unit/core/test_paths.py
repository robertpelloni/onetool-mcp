"""Unit tests for paths module."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
@pytest.mark.core
class TestGetTemplateFiles:
    """Tests for get_template_files()."""

    def test_returns_list_of_tuples(self) -> None:
        """Returns list of (source_path, dest_name) tuples."""
        from ot.paths import get_template_files

        result = get_template_files()

        assert isinstance(result, list)
        if result:  # May be empty in some test environments
            for item in result:
                assert isinstance(item, tuple)
                assert len(item) == 2
                assert isinstance(item[0], Path)
                assert isinstance(item[1], str)

    def test_strips_template_suffix(self) -> None:
        """Dest names have -template suffix stripped."""
        from ot.paths import get_template_files

        result = get_template_files()

        for source_path, dest_name in result:
            # If source has -template, dest should not
            if "-template.yaml" in source_path.name:
                assert "-template" not in dest_name
                assert dest_name.endswith(".yaml")


@pytest.mark.unit
@pytest.mark.core
class TestCreateBackup:
    """Tests for create_backup()."""

    def test_creates_bak_file(self, tmp_path: Path) -> None:
        """First backup creates file.bak."""
        from ot.paths import create_backup

        original = tmp_path / "test.yaml"
        original.write_text("content")

        backup = create_backup(original)

        assert backup.name == "test.yaml.bak"
        assert backup.exists()
        assert backup.read_text() == "content"

    def test_creates_numbered_backup(self, tmp_path: Path) -> None:
        """Subsequent backup creates file.bak.1."""
        from ot.paths import create_backup

        original = tmp_path / "test.yaml"
        original.write_text("content1")

        # Create first backup manually
        first_backup = tmp_path / "test.yaml.bak"
        first_backup.write_text("old content")

        # Create numbered backup
        backup = create_backup(original)

        assert backup.name == "test.yaml.bak.1"
        assert backup.exists()
        assert backup.read_text() == "content1"

    def test_increments_backup_number(self, tmp_path: Path) -> None:
        """Backups increment: .bak, .bak.1, .bak.2, etc."""
        from ot.paths import create_backup

        original = tmp_path / "test.yaml"
        original.write_text("content")

        # Create .bak and .bak.1 manually
        (tmp_path / "test.yaml.bak").write_text("v1")
        (tmp_path / "test.yaml.bak.1").write_text("v2")

        backup = create_backup(original)

        assert backup.name == "test.yaml.bak.2"


@pytest.mark.unit
@pytest.mark.core
class TestGetGlobalDir:
    """Tests for get_global_dir()."""

    def test_returns_home_onetool_by_default(self) -> None:
        """Returns ~/.onetool/ when no env var set."""
        from ot.paths import get_global_dir

        result = get_global_dir()

        assert result == Path.home() / ".onetool"

    def test_respects_ot_global_dir_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns OT_GLOBAL_DIR path when env var is set."""
        from ot.paths import get_global_dir

        custom_dir = tmp_path / "custom-onetool"
        monkeypatch.setenv("OT_GLOBAL_DIR", str(custom_dir))

        result = get_global_dir()

        assert result == custom_dir.resolve()


@pytest.mark.unit
@pytest.mark.core
class TestEnsureGlobalDir:
    """Tests for ensure_global_dir()."""

    def test_copies_yaml_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """YAML files are copied to config/ subdirectory."""
        from ot.paths import ensure_global_dir

        # Use a non-existent subdirectory so ensure_global_dir creates it
        onetool_dir = tmp_path / ".onetool"
        monkeypatch.setenv("OT_GLOBAL_DIR", str(onetool_dir))

        ensure_global_dir(quiet=True)

        config_dir = onetool_dir / "config"
        assert config_dir.exists()
        # At minimum, onetool.yaml should exist
        assert (config_dir / "onetool.yaml").exists()

    def test_copies_resource_subdirectories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Resource subdirectories like diagram-templates/ are copied."""
        from ot.paths import ensure_global_dir

        onetool_dir = tmp_path / ".onetool"
        monkeypatch.setenv("OT_GLOBAL_DIR", str(onetool_dir))

        ensure_global_dir(quiet=True)

        config_dir = onetool_dir / "config"
        diagram_templates = config_dir / "diagram-templates"
        # Should exist and contain template files
        assert diagram_templates.exists()
        assert diagram_templates.is_dir()
        # Should have at least some .mmd files
        mmd_files = list(diagram_templates.glob("*.mmd"))
        assert len(mmd_files) > 0

    def test_excludes_tool_templates_subdirectory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """tool_templates/ subdirectory is NOT copied (accessed via package)."""
        from ot.paths import ensure_global_dir

        onetool_dir = tmp_path / ".onetool"
        monkeypatch.setenv("OT_GLOBAL_DIR", str(onetool_dir))

        ensure_global_dir(quiet=True)

        config_dir = onetool_dir / "config"
        tool_templates = config_dir / "tool_templates"
        # Should NOT exist - tool_templates accessed via get_global_templates_dir()
        assert not tool_templates.exists()

    def test_creates_subdirectories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Creates config/, logs/, stats/, tools/ subdirectories."""
        from ot.paths import ensure_global_dir

        onetool_dir = tmp_path / ".onetool"
        monkeypatch.setenv("OT_GLOBAL_DIR", str(onetool_dir))

        ensure_global_dir(quiet=True)

        assert (onetool_dir / "config").exists()
        assert (onetool_dir / "logs").exists()
        assert (onetool_dir / "stats").exists()
        assert (onetool_dir / "tools").exists()
