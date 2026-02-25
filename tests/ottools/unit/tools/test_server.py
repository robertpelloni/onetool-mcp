"""Unit tests for ot.server() — runtime proxy server management."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_server_cfg(enabled: bool = True) -> MagicMock:
    cfg = MagicMock()
    cfg.enabled = enabled
    return cfg


def _make_mock_env(servers: dict, connected: list[str] | None = None, tool_counts: dict | None = None):
    """Create a mock environment with config and proxy manager."""
    connected = connected or []
    tool_counts = tool_counts or {}

    mock_cfg = MagicMock()
    mock_cfg.servers = servers

    mock_proxy = MagicMock()

    def get_connection(name: str):
        return MagicMock() if name in connected else None

    def list_tools(server: str | None = None):
        if server:
            return [MagicMock()] * tool_counts.get(server, 0)
        return []

    mock_proxy.get_connection = get_connection
    mock_proxy.list_tools = list_tools
    mock_proxy.get_error = MagicMock(return_value=None)
    mock_proxy.reconnect_sync = MagicMock()
    mock_proxy.connect_additional_sync = MagicMock()
    mock_proxy.disconnect_server_sync = MagicMock()

    return mock_cfg, mock_proxy


def _patch_env(mock_cfg, mock_proxy):
    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(patch("ottools.server.get_config", return_value=mock_cfg))
    stack.enter_context(patch("ottools.server.get_proxy_manager", return_value=mock_proxy))
    return stack


# =============================================================================
# List Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_server_list_all() -> None:
    """server() lists all configured servers."""
    from ottools.server import server

    servers = {
        "devtools": _make_server_cfg(enabled=True),
        "playwright": _make_server_cfg(enabled=False),
    }
    mock_cfg, mock_proxy = _make_mock_env(servers, connected=["devtools"], tool_counts={"devtools": 26})

    with _patch_env(mock_cfg, mock_proxy):
        result = server()

    assert "devtools" in result
    assert "playwright" in result
    assert "enabled" in result
    assert "disabled" in result


@pytest.mark.unit
@pytest.mark.tools
def test_server_list_shows_tool_count() -> None:
    """server() shows tool count for connected servers."""
    from ottools.server import server

    servers = {"devtools": _make_server_cfg(enabled=True)}
    mock_cfg, mock_proxy = _make_mock_env(servers, connected=["devtools"], tool_counts={"devtools": 26})

    with _patch_env(mock_cfg, mock_proxy):
        result = server()

    assert "26" in result


@pytest.mark.unit
@pytest.mark.tools
def test_server_no_servers_configured() -> None:
    """server() with no servers configured returns helpful message."""
    from ottools.server import server

    mock_cfg = MagicMock()
    mock_cfg.servers = None
    mock_proxy = MagicMock()

    with patch("ottools.server.get_config", return_value=mock_cfg), \
         patch("ottools.server.get_proxy_manager", return_value=mock_proxy):
        result = server()

    assert "No servers configured" in result


# =============================================================================
# Status Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_server_status_connected() -> None:
    """server(status=...) shows connection status and tool count."""
    from ottools.server import server

    servers = {"devtools": _make_server_cfg(enabled=True)}
    mock_cfg, mock_proxy = _make_mock_env(servers, connected=["devtools"], tool_counts={"devtools": 26})

    with _patch_env(mock_cfg, mock_proxy):
        result = server(status="devtools")

    assert "devtools" in result
    assert "connected" in result
    assert "26" in result


@pytest.mark.unit
@pytest.mark.tools
def test_server_status_unknown() -> None:
    """server(status='unknown') returns error with configured server names."""
    from ottools.server import server

    servers = {"devtools": _make_server_cfg()}
    mock_cfg, mock_proxy = _make_mock_env(servers)

    with _patch_env(mock_cfg, mock_proxy):
        result = server(status="nonexistent-server")

    assert "Error" in result or "Unknown" in result
    assert "devtools" in result


# =============================================================================
# Enable Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_server_enable_disabled_server() -> None:
    """server(enable=...) enables a disabled server."""
    from ottools.server import server

    srv_cfg = _make_server_cfg(enabled=False)
    servers = {"devtools-auto": srv_cfg}
    mock_cfg, mock_proxy = _make_mock_env(servers, connected=["devtools-auto"], tool_counts={"devtools-auto": 10})

    with _patch_env(mock_cfg, mock_proxy):
        result = server(enable="devtools-auto")

    assert mock_proxy.connect_additional_sync.called
    assert not mock_proxy.reconnect_sync.called
    assert srv_cfg.enabled is True
    assert "enabled" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_server_enable_already_enabled() -> None:
    """server(enable=...) when already enabled and connected — no reconnect."""
    from ottools.server import server

    srv_cfg = _make_server_cfg(enabled=True)
    servers = {"devtools": srv_cfg}
    mock_cfg, mock_proxy = _make_mock_env(servers, connected=["devtools"], tool_counts={"devtools": 26})

    with _patch_env(mock_cfg, mock_proxy):
        result = server(enable="devtools")

    assert not mock_proxy.connect_additional_sync.called
    assert not mock_proxy.reconnect_sync.called
    assert "already" in result


@pytest.mark.unit
@pytest.mark.tools
def test_server_enable_unknown() -> None:
    """server(enable='unknown') returns error."""
    from ottools.server import server

    servers = {"devtools": _make_server_cfg()}
    mock_cfg, mock_proxy = _make_mock_env(servers)

    with _patch_env(mock_cfg, mock_proxy):
        result = server(enable="nonexistent")

    assert "Error" in result or "Unknown" in result


# =============================================================================
# Disable Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_server_disable_enabled_server() -> None:
    """server(disable=...) disables an enabled server."""
    from ottools.server import server

    srv_cfg = _make_server_cfg(enabled=True)
    servers = {"devtools": srv_cfg}
    mock_cfg, mock_proxy = _make_mock_env(servers, connected=["devtools"])

    with _patch_env(mock_cfg, mock_proxy):
        result = server(disable="devtools")

    assert mock_proxy.disconnect_server_sync.called
    assert not mock_proxy.reconnect_sync.called
    assert srv_cfg.enabled is False
    assert "disabled" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_server_disable_already_disabled() -> None:
    """server(disable=...) when already disabled — no reconnect."""
    from ottools.server import server

    srv_cfg = _make_server_cfg(enabled=False)
    servers = {"devtools-auto": srv_cfg}
    mock_cfg, mock_proxy = _make_mock_env(servers)

    with _patch_env(mock_cfg, mock_proxy):
        result = server(disable="devtools-auto")

    assert not mock_proxy.disconnect_server_sync.called
    assert not mock_proxy.reconnect_sync.called
    assert "already" in result


# =============================================================================
# Restart Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_server_restart_connected() -> None:
    """server(restart=...) reconnects a connected server."""
    from ottools.server import server

    srv_cfg = _make_server_cfg(enabled=True)
    servers = {"playwright": srv_cfg}
    mock_cfg, mock_proxy = _make_mock_env(servers, connected=["playwright"], tool_counts={"playwright": 15})

    with _patch_env(mock_cfg, mock_proxy):
        result = server(restart="playwright")

    assert mock_proxy.disconnect_server_sync.called
    assert mock_proxy.connect_additional_sync.called
    assert not mock_proxy.reconnect_sync.called
    assert "restarted" in result.lower() or "playwright" in result


@pytest.mark.unit
@pytest.mark.tools
def test_server_restart_disconnected() -> None:
    """server(restart=...) on disconnected server attempts reconnect."""
    from ottools.server import server

    srv_cfg = _make_server_cfg(enabled=False)
    servers = {"playwright": srv_cfg}
    mock_cfg, mock_proxy = _make_mock_env(servers, connected=[], tool_counts={})

    with _patch_env(mock_cfg, mock_proxy):
        result = server(restart="playwright")

    assert mock_proxy.disconnect_server_sync.called
    assert mock_proxy.connect_additional_sync.called
    assert not mock_proxy.reconnect_sync.called
    assert "playwright" in result
