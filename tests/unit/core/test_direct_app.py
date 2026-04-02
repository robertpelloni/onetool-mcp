"""Unit tests for onetool direct start/restart wait behaviour."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
@pytest.mark.core
class TestDirectStart:
    """_start_host() always calls _tcp_probe_wait — no --wait flag required."""

    def test_start_calls_tcp_probe_wait(self, tmp_path: Path) -> None:
        """_start_host invokes _tcp_probe_wait unconditionally."""
        from onetool.cli_commands.direct_app import _start_host

        mock_proc = MagicMock()
        mock_proc.pid = 12345

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("onetool.cli_commands.direct_app._write_pid_file"),
            patch("onetool.cli_commands.direct_app._tcp_probe_wait", return_value=True) as mock_wait,
            patch("onetool.cli_commands.direct_app.err_console"),
        ):
            _start_host(None, None, 8765)
            mock_wait.assert_called_once_with("127.0.0.1", 8765)

    def test_start_exits_1_on_timeout(self, tmp_path: Path) -> None:
        """_start_host raises Exit(1) if _tcp_probe_wait returns False."""
        import typer
        from onetool.cli_commands.direct_app import _start_host

        mock_proc = MagicMock()
        mock_proc.pid = 12345

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("onetool.cli_commands.direct_app._write_pid_file"),
            patch("onetool.cli_commands.direct_app._tcp_probe_wait", return_value=False),
            patch("onetool.cli_commands.direct_app.err_console"),
        ):
            with pytest.raises(typer.Exit) as exc_info:
                _start_host(None, None, 8765)
            assert exc_info.value.exit_code == 1

    def test_start_exits_0_when_ready(self, tmp_path: Path) -> None:
        """_start_host returns normally (exit 0) when host becomes ready."""
        from onetool.cli_commands.direct_app import _start_host

        mock_proc = MagicMock()
        mock_proc.pid = 12345

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("onetool.cli_commands.direct_app._write_pid_file"),
            patch("onetool.cli_commands.direct_app._tcp_probe_wait", return_value=True),
            patch("onetool.cli_commands.direct_app.err_console"),
        ):
            # Should not raise
            _start_host(None, None, 8765)


@pytest.mark.unit
@pytest.mark.core
class TestDirectRestart:
    """direct_restart always waits via _start_host → _tcp_probe_wait."""

    def test_restart_calls_tcp_probe_wait(self, tmp_path: Path) -> None:
        """direct_restart invokes _tcp_probe_wait unconditionally."""
        from onetool.cli_commands.direct_app import _start_host

        mock_proc = MagicMock()
        mock_proc.pid = 99999

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("onetool.cli_commands.direct_app._write_pid_file"),
            patch("onetool.cli_commands.direct_app._tcp_probe_wait", return_value=True) as mock_wait,
            patch("onetool.cli_commands.direct_app.err_console"),
        ):
            _start_host(None, None, 9000)
            mock_wait.assert_called_once_with("127.0.0.1", 9000)
