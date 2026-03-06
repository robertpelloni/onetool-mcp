"""Unit tests for ot.telemetry module."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
@pytest.mark.core
class TestIsOptedOut:
    """Tests for _is_opted_out()."""

    def test_do_not_track_one_opts_out(self) -> None:
        with patch.dict("os.environ", {"DO_NOT_TRACK": "1"}, clear=False):
            from ot.telemetry import _is_opted_out
            assert _is_opted_out() is True

    def test_zero_value_does_not_opt_out(self) -> None:
        with patch.dict("os.environ", {"DO_NOT_TRACK": "0"}, clear=False):
            from ot.telemetry import _is_opted_out
            assert _is_opted_out() is False

    def test_unset_does_not_opt_out(self) -> None:
        env = {k: v for k, v in __import__("os").environ.items()
               if k not in ("DO_NOT_TRACK",)}
        with patch.dict("os.environ", env, clear=True):
            from ot.telemetry import _is_opted_out
            assert _is_opted_out() is False

    def test_non_zero_string_opts_out(self) -> None:
        with patch.dict("os.environ", {"DO_NOT_TRACK": "true"}, clear=False):
            from ot.telemetry import _is_opted_out
            assert _is_opted_out() is True


@pytest.mark.unit
@pytest.mark.core
class TestMarkerFileLogic:
    """Tests for marker file event determination in ping()."""

    def test_absent_marker_fires_install(self, tmp_path: Path) -> None:
        marker = tmp_path / ".onetool_telemetry"

        with (
            patch("ot.telemetry.resolve_ot_path", return_value=marker),
            patch("ot.telemetry.get_version", return_value="1.0.0"),
            patch("ot.telemetry._is_opted_out", return_value=False),
        ):
            from ot.telemetry import ping
            with patch("threading.Thread") as mock_thread:
                mock_thread.return_value = MagicMock()
                ping()
                call_kwargs = mock_thread.call_args
                event = call_kwargs[1]["args"][0]
                properties = call_kwargs[1]["args"][1]

        assert event == "server-installed"
        assert properties["version"] == "1.0.0"

    def test_same_version_fires_start(self, tmp_path: Path) -> None:
        marker = tmp_path / ".onetool_telemetry"
        test_uuid = str(uuid.uuid4())
        marker.write_text(f"1.0.0\n{test_uuid}")

        with (
            patch("ot.telemetry.resolve_ot_path", return_value=marker),
            patch("ot.telemetry.get_version", return_value="1.0.0"),
            patch("ot.telemetry._is_opted_out", return_value=False),
        ):
            from ot.telemetry import ping
            with patch("threading.Thread") as mock_thread:
                mock_thread.return_value = MagicMock()
                ping()
                event = mock_thread.call_args[1]["args"][0]
                properties = mock_thread.call_args[1]["args"][1]

        assert event == "server-started"
        assert "version_from" not in properties

    def test_different_version_fires_upgrade(self, tmp_path: Path) -> None:
        marker = tmp_path / ".onetool_telemetry"
        test_uuid = str(uuid.uuid4())
        marker.write_text(f"0.9.0\n{test_uuid}")

        with (
            patch("ot.telemetry.resolve_ot_path", return_value=marker),
            patch("ot.telemetry.get_version", return_value="1.0.0"),
            patch("ot.telemetry._is_opted_out", return_value=False),
        ):
            from ot.telemetry import ping
            with patch("threading.Thread") as mock_thread:
                mock_thread.return_value = MagicMock()
                ping()
                event = mock_thread.call_args[1]["args"][0]
                properties = mock_thread.call_args[1]["args"][1]

        assert event == "server-upgraded"
        assert properties["version_from"] == "0.9.0"
        assert properties["version_to"] == "1.0.0"


@pytest.mark.unit
@pytest.mark.core
class TestUUIDLogic:
    """Tests for UUID generation and persistence."""

    def test_uuid_generated_on_install(self, tmp_path: Path) -> None:
        marker = tmp_path / ".onetool_telemetry"

        with (
            patch("ot.telemetry.resolve_ot_path", return_value=marker),
            patch("ot.telemetry.get_version", return_value="1.0.0"),
            patch("ot.telemetry._is_opted_out", return_value=False),
        ):
            from ot.telemetry import ping
            with patch("threading.Thread") as mock_thread:
                mock_thread.return_value = MagicMock()
                ping()

        lines = marker.read_text().splitlines()
        assert len(lines) == 2
        assert lines[0] == "1.0.0"
        # Must be a valid UUID4
        parsed = uuid.UUID(lines[1], version=4)
        assert str(parsed) == lines[1]

    def test_uuid_reused_on_subsequent_start(self, tmp_path: Path) -> None:
        marker = tmp_path / ".onetool_telemetry"

        with (
            patch("ot.telemetry.resolve_ot_path", return_value=marker),
            patch("ot.telemetry.get_version", return_value="1.0.0"),
            patch("ot.telemetry._is_opted_out", return_value=False),
        ):
            from ot.telemetry import ping
            # First call — generates UUID
            with patch("threading.Thread") as mock_thread:
                mock_thread.return_value = MagicMock()
                ping()
                machine_uuid_first = mock_thread.call_args[1]["args"][2]
            # Second call — should reuse same UUID
            with patch("threading.Thread") as mock_thread:
                mock_thread.return_value = MagicMock()
                ping()
                machine_uuid_second = mock_thread.call_args[1]["args"][2]

        assert machine_uuid_first == machine_uuid_second

    def test_old_format_marker_gets_uuid_appended(self, tmp_path: Path) -> None:
        """Existing single-line marker (version only) migrates transparently."""
        marker = tmp_path / ".onetool_telemetry"
        marker.write_text("1.0.0")

        with (
            patch("ot.telemetry.resolve_ot_path", return_value=marker),
            patch("ot.telemetry.get_version", return_value="1.0.0"),
            patch("ot.telemetry._is_opted_out", return_value=False),
        ):
            from ot.telemetry import ping
            with patch("threading.Thread") as mock_thread:
                mock_thread.return_value = MagicMock()
                ping()
                event = mock_thread.call_args[1]["args"][0]

        # Should be start event (same version), and marker now has UUID on line 2
        assert event == "server-started"
        lines = marker.read_text().splitlines()
        assert len(lines) == 2
        uuid.UUID(lines[1], version=4)  # valid UUID4


@pytest.mark.unit
@pytest.mark.core
class TestConfigDisabled:
    """Test that ping() respects telemetry.enabled = False in config."""

    def test_config_disabled_skips_ping(self, tmp_path: Path) -> None:
        mock_config = MagicMock()
        mock_config.telemetry.enabled = False

        with (
            patch("ot.telemetry._is_opted_out", return_value=False),
            patch("ot.telemetry.get_config", return_value=mock_config),
            patch("threading.Thread") as mock_thread,
        ):
            from ot.telemetry import ping
            ping()
            mock_thread.assert_not_called()


@pytest.mark.unit
@pytest.mark.core
class TestFireSwallowsExceptions:
    """Test that _fire() silently swallows all exceptions."""

    def test_network_error_is_swallowed(self) -> None:
        with patch("httpx.post", side_effect=Exception("network down")):
            from ot.telemetry import _fire
            # Should not raise
            _fire("server-started", {"version": "1.0.0", "os": "Linux", "python_version": "3.11"}, "test-uuid")

    def test_import_error_is_swallowed(self) -> None:
        import builtins
        real_import = builtins.__import__

        def mock_import(name: str, *args, **kwargs):  # type: ignore[no-untyped-def]
            if name == "httpx":
                raise ImportError("no module named httpx")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            from ot.telemetry import _fire
            # Should not raise
            _fire("server-started", {"version": "1.0.0", "os": "Linux", "python_version": "3.11"}, "test-uuid")
