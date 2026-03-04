"""Unit tests for ot.telemetry module."""

from __future__ import annotations

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

    def test_scarf_no_analytics_one_opts_out(self) -> None:
        with patch.dict("os.environ", {"SCARF_NO_ANALYTICS": "1"}, clear=False):
            from ot.telemetry import _is_opted_out
            assert _is_opted_out() is True

    def test_zero_value_does_not_opt_out(self) -> None:
        with patch.dict("os.environ", {"DO_NOT_TRACK": "0", "SCARF_NO_ANALYTICS": "0"}, clear=False):
            from ot.telemetry import _is_opted_out
            assert _is_opted_out() is False

    def test_unset_does_not_opt_out(self) -> None:
        env = {k: v for k, v in __import__("os").environ.items()
               if k not in ("DO_NOT_TRACK", "SCARF_NO_ANALYTICS")}
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
        fired: list[dict] = []

        with (
            patch("ot.telemetry._MARKER_FILE", marker),
            patch("ot.telemetry.get_version", return_value="1.0.0"),
            patch("ot.telemetry._fire", side_effect=fired.append),
            patch("ot.telemetry._is_opted_out", return_value=False),
        ):
            from ot.telemetry import ping
            # Run synchronously by patching thread
            with patch("threading.Thread") as mock_thread:
                mock_thread.return_value = MagicMock()
                ping()
                call_kwargs = mock_thread.call_args
                params = call_kwargs[1]["args"][0]

        assert params["e"] == "install"
        assert marker.read_text() == "1.0.0"

    def test_same_version_fires_start(self, tmp_path: Path) -> None:
        marker = tmp_path / ".onetool_telemetry"
        marker.write_text("1.0.0")

        with (
            patch("ot.telemetry._MARKER_FILE", marker),
            patch("ot.telemetry.get_version", return_value="1.0.0"),
            patch("ot.telemetry._is_opted_out", return_value=False),
        ):
            from ot.telemetry import ping
            with patch("threading.Thread") as mock_thread:
                mock_thread.return_value = MagicMock()
                ping()
                params = mock_thread.call_args[1]["args"][0]

        assert params["e"] == "start"
        assert "v_from" not in params

    def test_different_version_fires_upgrade(self, tmp_path: Path) -> None:
        marker = tmp_path / ".onetool_telemetry"
        marker.write_text("0.9.0")

        with (
            patch("ot.telemetry._MARKER_FILE", marker),
            patch("ot.telemetry.get_version", return_value="1.0.0"),
            patch("ot.telemetry._is_opted_out", return_value=False),
        ):
            from ot.telemetry import ping
            with patch("threading.Thread") as mock_thread:
                mock_thread.return_value = MagicMock()
                ping()
                params = mock_thread.call_args[1]["args"][0]

        assert params["e"] == "upgrade"
        assert params["v_from"] == "0.9.0"
        assert params["v_to"] == "1.0.0"
        assert marker.read_text() == "1.0.0"


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
        with patch("httpx.get", side_effect=Exception("network down")):
            from ot.telemetry import _fire
            # Should not raise
            _fire({"e": "start", "v": "1.0.0", "os": "Linux", "py": "3.11"})

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
            _fire({"e": "start", "v": "1.0.0", "os": "Linux", "py": "3.11"})
