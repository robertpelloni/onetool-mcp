"""Unit tests for ProxyManager native instruction capture."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
@pytest.mark.core
class TestNativeInstructions:
    """Tests for _server_instructions capture in ProxyManager._connect_server."""

    def _make_manager(self) -> "ProxyManager":
        from ot.proxy.manager import ProxyManager

        return ProxyManager()

    def test_instructions_empty_by_default(self) -> None:
        """get_server_instructions returns '' for unknown server."""
        mgr = self._make_manager()
        assert mgr.get_server_instructions("nonexistent") == ""

    def test_instructions_captured_on_connect(self) -> None:
        """After _connect_server, get_server_instructions returns the value from initialize_result."""
        import asyncio

        from ot.proxy.manager import ProxyManager

        mgr = ProxyManager()

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.list_tools = AsyncMock(return_value=[])
        mock_client.initialize_result = MagicMock()
        mock_client.initialize_result.instructions = "Use take_screenshot after every action."

        mock_config = MagicMock()
        mock_config.type = "stdio"
        mock_config.timeout = 30

        with patch.object(mgr, "_create_client", return_value=mock_client):
            asyncio.run(mgr._connect_server("my_server", mock_config))

        assert mgr.get_server_instructions("my_server") == "Use take_screenshot after every action."

    def test_instructions_empty_when_server_provides_none(self) -> None:
        """initialize_result.instructions = None → get_server_instructions returns ''."""
        import asyncio

        from ot.proxy.manager import ProxyManager

        mgr = ProxyManager()

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.list_tools = AsyncMock(return_value=[])
        mock_client.initialize_result = MagicMock()
        mock_client.initialize_result.instructions = None

        mock_config = MagicMock()
        mock_config.type = "stdio"
        mock_config.timeout = 30

        with patch.object(mgr, "_create_client", return_value=mock_client):
            asyncio.run(mgr._connect_server("my_server", mock_config))

        assert mgr.get_server_instructions("my_server") == ""

    def test_instructions_empty_when_initialize_result_is_none(self) -> None:
        """Client.initialize_result = None (server didn't provide one) → returns ''."""
        import asyncio

        from ot.proxy.manager import ProxyManager

        mgr = ProxyManager()

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.list_tools = AsyncMock(return_value=[])
        mock_client.initialize_result = None  # server returned no InitializeResult

        mock_config = MagicMock()
        mock_config.type = "stdio"
        mock_config.timeout = 30

        with patch.object(mgr, "_create_client", return_value=mock_client):
            asyncio.run(mgr._connect_server("my_server", mock_config))

        assert mgr.get_server_instructions("my_server") == ""

    def test_instructions_cleared_on_disconnect(self) -> None:
        """disconnect_server removes the server's instructions entry."""
        import asyncio

        from ot.proxy.manager import ProxyManager

        mgr = ProxyManager()

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.list_tools = AsyncMock(return_value=[])
        mock_client.initialize_result = MagicMock()
        mock_client.initialize_result.instructions = "Some instructions."

        mock_config = MagicMock()
        mock_config.type = "stdio"
        mock_config.timeout = 30

        with patch.object(mgr, "_create_client", return_value=mock_client):
            asyncio.run(mgr._connect_server("my_server", mock_config))

        assert mgr.get_server_instructions("my_server") == "Some instructions."

        asyncio.run(mgr.disconnect_server("my_server"))
        assert "my_server" not in mgr._server_instructions
