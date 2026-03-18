"""Unit tests for ot.utils.session — session dir lifecycle."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SESSION_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[0-9a-f]{8}$")


def _make_config(tmp_path: Path, retention_days: int = 1, sessions_dir: str = "sessions") -> MagicMock:
    cfg = MagicMock()
    cfg.output.sessions_dir = sessions_dir
    cfg.output.session_retention_days = retention_days
    return cfg


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset the module-level session singleton before and after each test."""
    import ot.utils.session as session_mod

    session_mod._reset_session_dir()
    yield
    session_mod._reset_session_dir()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestGetSessionDir:
    def test_creates_dir_with_correct_name_format(self, tmp_path: Path) -> None:
        from ot.utils.session import get_session_dir

        sessions_base = tmp_path / "sessions"
        with patch("ot.config.get_config", return_value=_make_config(tmp_path)), \
             patch("ot.meta.resolve_ot_path", return_value=sessions_base):
            result = get_session_dir()

        assert result.exists()
        assert result.parent == sessions_base
        assert SESSION_NAME_RE.match(result.name), f"Unexpected name: {result.name}"

    def test_singleton_returns_same_dir_on_second_call(self, tmp_path: Path) -> None:
        from ot.utils.session import get_session_dir

        sessions_base = tmp_path / "sessions"
        with patch("ot.config.get_config", return_value=_make_config(tmp_path)), \
             patch("ot.meta.resolve_ot_path", return_value=sessions_base):
            first = get_session_dir()
            second = get_session_dir()

        assert first == second

    def test_creates_sessions_base_if_missing(self, tmp_path: Path) -> None:
        from ot.utils.session import get_session_dir

        sessions_base = tmp_path / "deep" / "sessions"
        assert not sessions_base.exists()

        with patch("ot.config.get_config", return_value=_make_config(tmp_path)), \
             patch("ot.meta.resolve_ot_path", return_value=sessions_base):
            result = get_session_dir()

        assert result.exists()
        assert result.parent == sessions_base


@pytest.mark.unit
@pytest.mark.core
class TestPurgeOldSessions:
    def test_purges_dirs_older_than_retention(self, tmp_path: Path) -> None:
        from ot.utils.session import _purge_old_sessions

        sessions_base = tmp_path / "sessions"
        sessions_base.mkdir()

        old_dir = sessions_base / "2024-01-01-aabbccdd"
        old_dir.mkdir()
        # Set mtime to 3 days ago
        old_mtime = time.time() - 3 * 86400
        os.utime(old_dir, (old_mtime, old_mtime))

        _purge_old_sessions(sessions_base, retention_days=1)

        assert not old_dir.exists()

    def test_retains_recent_dirs(self, tmp_path: Path) -> None:
        from ot.utils.session import _purge_old_sessions

        sessions_base = tmp_path / "sessions"
        sessions_base.mkdir()

        recent_dir = sessions_base / "2026-03-04-aabbccdd"
        recent_dir.mkdir()
        # mtime is now (default) — well within 1 day

        _purge_old_sessions(sessions_base, retention_days=1)

        assert recent_dir.exists()

    def test_zero_retention_skips_purge(self, tmp_path: Path) -> None:
        from ot.utils.session import _purge_old_sessions

        sessions_base = tmp_path / "sessions"
        sessions_base.mkdir()

        old_dir = sessions_base / "2024-01-01-aabbccdd"
        old_dir.mkdir()
        old_mtime = time.time() - 10 * 86400
        os.utime(old_dir, (old_mtime, old_mtime))

        _purge_old_sessions(sessions_base, retention_days=0)

        assert old_dir.exists()

    def test_ignores_files_in_sessions_base(self, tmp_path: Path) -> None:
        from ot.utils.session import _purge_old_sessions

        sessions_base = tmp_path / "sessions"
        sessions_base.mkdir()

        stray_file = sessions_base / "stray.txt"
        stray_file.write_text("hello")
        old_mtime = time.time() - 10 * 86400
        os.utime(stray_file, (old_mtime, old_mtime))

        # Should not raise, should not delete the file (it's not a dir)
        _purge_old_sessions(sessions_base, retention_days=1)

        assert stray_file.exists()


@pytest.mark.unit
@pytest.mark.core
class TestCtxStorePath:
    def test_get_store_resolves_to_session_dir(self, tmp_path: Path) -> None:
        from ot.ctx.store import _get_store

        session_dir = tmp_path / "2026-03-04-aabbccdd"
        session_dir.mkdir()
        with patch("ot.utils.session.get_session_dir", return_value=session_dir):
            store = _get_store()

        assert store._dir == session_dir / "ctx"


@pytest.mark.unit
@pytest.mark.core
class TestResetSessionDir:
    def test_reset_allows_new_dir_on_next_call(self, tmp_path: Path) -> None:
        from ot.utils import session as session_mod

        sessions_base = tmp_path / "sessions"
        with patch("ot.config.get_config", return_value=_make_config(tmp_path)), \
             patch("ot.meta.resolve_ot_path", return_value=sessions_base):
            first = session_mod.get_session_dir()

        session_mod._reset_session_dir()

        sessions_base2 = tmp_path / "sessions2"
        with patch("ot.config.get_config", return_value=_make_config(tmp_path, sessions_dir="sessions2")), \
             patch("ot.meta.resolve_ot_path", return_value=sessions_base2):
            second = session_mod.get_session_dir()

        assert first != second
