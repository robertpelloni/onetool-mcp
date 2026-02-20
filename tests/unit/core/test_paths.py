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
class TestEnsureOtDir:
    """Tests for ensure_ot_dir()."""

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Creates ot dir at config_path.parent."""
        from ot.paths import ensure_ot_dir

        config_path = tmp_path / ".onetool" / "onetool.yaml"
        result = ensure_ot_dir(config_path, quiet=True)

        assert result == tmp_path / ".onetool"
        assert result.exists()

    def test_creates_subdirectories(self, tmp_path: Path) -> None:
        """Creates logs/, stats/, tools/ subdirectories."""
        from ot.paths import ensure_ot_dir

        config_path = tmp_path / ".onetool" / "onetool.yaml"
        ensure_ot_dir(config_path, quiet=True)

        ot_dir = tmp_path / ".onetool"
        assert (ot_dir / "logs").exists()
        assert (ot_dir / "stats").exists()
        assert (ot_dir / "tools").exists()

    def test_copies_yaml_files(self, tmp_path: Path) -> None:
        """Copies YAML template files flat into ot dir."""
        from ot.paths import ensure_ot_dir

        config_path = tmp_path / ".onetool" / "onetool.yaml"
        ensure_ot_dir(config_path, quiet=True)

        ot_dir = tmp_path / ".onetool"
        assert (ot_dir / "onetool.yaml").exists()

    def test_existing_dir_not_recreated(self, tmp_path: Path) -> None:
        """Existing directory is not recreated when force=False."""
        from ot.paths import ensure_ot_dir

        ot_dir = tmp_path / ".onetool"
        ot_dir.mkdir()
        marker = ot_dir / "marker.txt"
        marker.write_text("existing")

        config_path = ot_dir / "onetool.yaml"
        ensure_ot_dir(config_path, quiet=True, force=False)

        assert marker.exists()
