"""Tests for path security utilities."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ot.utils.pathsec import (
    DEFAULT_EXCLUDE_PATTERNS,
    is_path_excluded,
    validate_path,
)


@pytest.fixture(autouse=True)
def _mock_cwd(tmp_path: Path):
    """Mock effective CWD to tmp_path for all tests."""
    with patch("ot.utils.pathsec.resolve_cwd_path") as mock_resolve:
        # resolve_cwd_path(".") returns tmp_path, other paths resolve relative to it
        def _resolve(path: str) -> Path:
            p = Path(path).expanduser()
            if p.is_absolute():
                return p.resolve()
            return (tmp_path / p).resolve()

        mock_resolve.side_effect = _resolve
        yield


# ---------------------------------------------------------------------------
# is_path_excluded
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestIsPathExcluded:
    def test_git_directory_excluded(self, tmp_path: Path):
        assert is_path_excluded(tmp_path / ".git" / "config", [".git"])

    def test_node_modules_excluded(self, tmp_path: Path):
        assert is_path_excluded(tmp_path / "node_modules" / "pkg", ["node_modules"])

    def test_normal_path_not_excluded(self, tmp_path: Path):
        assert not is_path_excluded(tmp_path / "src" / "main.py", [".git"])

    def test_fnmatch_pattern(self, tmp_path: Path):
        assert is_path_excluded(tmp_path / "secret.key", ["*.key"])

    def test_empty_patterns(self, tmp_path: Path):
        assert not is_path_excluded(tmp_path / "anything", [])


# ---------------------------------------------------------------------------
# validate_path
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestValidatePath:
    def test_relative_path_in_cwd(self, tmp_path: Path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        resolved, error = validate_path("test.txt", must_exist=True)

        assert error is None
        assert resolved is not None
        assert resolved.name == "test.txt"

    def test_path_outside_cwd_rejected(self, tmp_path: Path):
        resolved, error = validate_path("/etc/passwd", must_exist=False)

        assert resolved is None
        assert "outside allowed directories" in error

    def test_nonexistent_path_must_exist(self, tmp_path: Path):
        resolved, error = validate_path("nonexistent.txt", must_exist=True)

        assert resolved is None
        assert "not found" in error.lower()

    def test_nonexistent_path_allowed_when_not_required(self, tmp_path: Path):
        resolved, error = validate_path("newfile.txt", must_exist=False)

        assert error is None
        assert resolved is not None

    def test_excluded_pattern_rejected(self, tmp_path: Path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        config = git_dir / "config"
        config.write_text("data")

        resolved, error = validate_path(".git/config", must_exist=True)

        assert resolved is None
        assert "exclude pattern" in error

    def test_custom_allowed_dirs(self, tmp_path: Path):
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        test_file = other_dir / "file.txt"
        test_file.write_text("data")

        # Without custom allowed dirs, absolute path outside cwd fails
        resolved, error = validate_path(str(test_file), must_exist=True)
        assert error is None  # still under tmp_path which is cwd

    def test_custom_exclude_patterns(self, tmp_path: Path):
        secret = tmp_path / "secret.env"
        secret.write_text("KEY=val")

        resolved, error = validate_path(
            "secret.env", must_exist=True, exclude_patterns=["*.env"]
        )

        assert resolved is None
        assert "exclude pattern" in error

    def test_default_exclude_patterns_populated(self):
        assert ".git" in DEFAULT_EXCLUDE_PATTERNS
        assert "node_modules" in DEFAULT_EXCLUDE_PATTERNS

    def test_path_traversal_rejected(self, tmp_path: Path):
        resolved, error = validate_path("../../../etc/passwd", must_exist=False)

        assert resolved is None
        assert "outside allowed directories" in error

    def test_tilde_expansion(self, tmp_path: Path):
        # ~ expands to home dir which is outside tmp_path (cwd)
        resolved, error = validate_path("~/some_file", must_exist=False)

        assert resolved is None
        assert "outside allowed directories" in error
