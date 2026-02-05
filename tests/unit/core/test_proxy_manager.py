"""Tests for MCP ProxyManager class."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ot.proxy.manager import ProxyManager, get_proxy_manager, reset_proxy_manager


@pytest.mark.unit
@pytest.mark.core
class TestProxyManager:
    """Tests for ProxyManager class."""

    def test_init_creates_empty_state(self) -> None:
        """Should initialize with empty state."""
        manager = ProxyManager()

        assert manager._clients == {}
        assert manager._tools_by_server == {}
        assert manager._initialized is False
        assert manager._loop is None

    def test_servers_returns_client_keys(self) -> None:
        """Should return list of connected server names."""
        manager = ProxyManager()
        manager._clients = {"server1": MagicMock(), "server2": MagicMock()}

        assert set(manager.servers) == {"server1", "server2"}

    def test_tool_count_sums_all_servers(self) -> None:
        """Should return total tool count across servers."""
        manager = ProxyManager()
        manager._tools_by_server = {
            "server1": [MagicMock(), MagicMock()],
            "server2": [MagicMock()],
        }

        assert manager.tool_count == 3

    def test_get_connection_returns_client(self) -> None:
        """Should return client by server name."""
        manager = ProxyManager()
        mock_client = MagicMock()
        manager._clients = {"server1": mock_client}

        assert manager.get_connection("server1") is mock_client
        assert manager.get_connection("unknown") is None


@pytest.mark.unit
@pytest.mark.core
class TestProxyManagerReconnectSync:
    """Tests for reconnect_sync method."""

    def test_reconnect_sync_without_loop_resets_state(self) -> None:
        """Should reset state when no event loop available."""
        manager = ProxyManager()
        manager._clients = {"old": MagicMock()}
        manager._tools_by_server = {"old": [MagicMock()]}
        manager._initialized = True
        manager._loop = None

        # Call with empty configs - should reset state
        manager.reconnect_sync({})

        assert manager._clients == {}
        assert manager._tools_by_server == {}
        assert manager._initialized is False

    def test_reconnect_sync_with_stored_loop_uses_it(self) -> None:
        """Should use stored loop for reconnection."""
        import asyncio

        manager = ProxyManager()
        mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)
        mock_loop.is_running.return_value = True
        manager._loop = mock_loop

        # Mock run_coroutine_threadsafe to avoid actual async execution
        with patch("asyncio.run_coroutine_threadsafe") as mock_threadsafe:
            mock_future = MagicMock()
            mock_future.result.return_value = None
            mock_threadsafe.return_value = mock_future

            manager.reconnect_sync({})

            mock_threadsafe.assert_called_once()
            # Verify it was called with the stored loop
            call_args = mock_threadsafe.call_args
            assert call_args[0][1] is mock_loop

            # Close the coroutine to avoid "never awaited" warning
            # (the mock doesn't actually schedule it)
            call_args[0][0].close()


@pytest.mark.unit
@pytest.mark.core
class TestProxyManagerListTools:
    """Tests for list_tools method."""

    def test_list_tools_all_servers(self) -> None:
        """Should list tools from all servers."""
        from mcp import types

        manager = ProxyManager()

        # Create mock tools
        tool1 = MagicMock(spec=types.Tool)
        tool1.name = "search"
        tool1.description = "Search the web"
        tool1.inputSchema = {"type": "object"}

        tool2 = MagicMock(spec=types.Tool)
        tool2.name = "fetch"
        tool2.description = "Fetch a URL"
        tool2.inputSchema = {"type": "object"}

        manager._tools_by_server = {
            "brave": [tool1],
            "web": [tool2],
        }

        tools = manager.list_tools()

        assert len(tools) == 2
        assert any(t.server == "brave" and t.name == "search" for t in tools)
        assert any(t.server == "web" and t.name == "fetch" for t in tools)

    def test_list_tools_filtered_by_server(self) -> None:
        """Should filter tools by server name."""
        from mcp import types

        manager = ProxyManager()

        tool1 = MagicMock(spec=types.Tool)
        tool1.name = "search"
        tool1.description = "Search"
        tool1.inputSchema = {}

        tool2 = MagicMock(spec=types.Tool)
        tool2.name = "fetch"
        tool2.description = "Fetch"
        tool2.inputSchema = {}

        manager._tools_by_server = {
            "brave": [tool1],
            "web": [tool2],
        }

        tools = manager.list_tools(server="brave")

        assert len(tools) == 1
        assert tools[0].name == "search"
        assert tools[0].server == "brave"


@pytest.mark.unit
@pytest.mark.core
class TestGlobalProxyManager:
    """Tests for global proxy manager functions."""

    def test_get_proxy_manager_creates_singleton(self) -> None:
        """Should create singleton instance."""
        reset_proxy_manager()

        manager1 = get_proxy_manager()
        manager2 = get_proxy_manager()

        assert manager1 is manager2

    def test_reset_proxy_manager_clears_singleton(self) -> None:
        """Should clear singleton instance."""
        manager1 = get_proxy_manager()
        reset_proxy_manager()
        manager2 = get_proxy_manager()

        assert manager1 is not manager2


@pytest.mark.unit
@pytest.mark.core
class TestProxyManagerAuth:
    """Tests for HTTP client authentication."""

    @patch("ot.proxy.manager.StreamableHttpTransport")
    @patch("ot.proxy.manager.Client")
    def test_http_client_no_auth(
        self, mock_client: MagicMock, mock_transport: MagicMock
    ) -> None:
        """Should create HTTP client without auth when not configured."""
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        config = McpServerConfig(
            type="http",
            url="https://api.example.com/mcp",
        )

        manager._create_http_client("test", config)

        # Verify transport created with no auth
        mock_transport.assert_called_once()
        call_kwargs = mock_transport.call_args[1]
        assert call_kwargs["auth"] is None

    @patch("ot.proxy.manager.OAuth")
    @patch("ot.proxy.manager.StreamableHttpTransport")
    @patch("ot.proxy.manager.Client")
    def test_http_client_oauth(
        self,
        mock_client: MagicMock,
        mock_transport: MagicMock,
        mock_oauth: MagicMock,
    ) -> None:
        """Should create HTTP client with OAuth when configured."""
        from ot.config.models import AuthConfig, McpServerConfig

        manager = ProxyManager()
        config = McpServerConfig(
            type="http",
            url="https://api.example.com/mcp",
            auth=AuthConfig(type="oauth", scopes=["tools:read", "tools:write"]),
        )

        manager._create_http_client("test", config)

        # Verify OAuth created with correct params
        mock_oauth.assert_called_once_with(
            mcp_url="https://api.example.com/mcp",
            scopes=["tools:read", "tools:write"],
            client_name="OneTool",
        )

        # Verify transport created with OAuth
        mock_transport.assert_called_once()
        call_kwargs = mock_transport.call_args[1]
        assert call_kwargs["auth"] == mock_oauth.return_value

    @patch("ot.proxy.manager.BearerAuth")
    @patch("ot.proxy.manager.StreamableHttpTransport")
    @patch("ot.proxy.manager.Client")
    @patch("ot.proxy.manager.expand_vars")
    def test_http_client_bearer(
        self,
        mock_expand: MagicMock,
        mock_client: MagicMock,
        mock_transport: MagicMock,
        mock_bearer: MagicMock,
    ) -> None:
        """Should create HTTP client with Bearer auth when configured."""
        from ot.config.models import AuthConfig, McpServerConfig

        mock_expand.return_value = "expanded-token-123"

        manager = ProxyManager()
        config = McpServerConfig(
            type="http",
            url="https://api.example.com/mcp",
            auth=AuthConfig(type="bearer", token="${GITHUB_TOKEN}"),
        )

        manager._create_http_client("test", config)

        # Verify token expansion
        mock_expand.assert_called_once_with("${GITHUB_TOKEN}")

        # Verify BearerAuth created with expanded token
        mock_bearer.assert_called_once_with("expanded-token-123")

        # Verify transport created with BearerAuth
        mock_transport.assert_called_once()
        call_kwargs = mock_transport.call_args[1]
        assert call_kwargs["auth"] == mock_bearer.return_value

    @patch("ot.proxy.manager.StreamableHttpTransport")
    @patch("ot.proxy.manager.Client")
    def test_http_url_upgrade_to_https(
        self, mock_client: MagicMock, mock_transport: MagicMock
    ) -> None:
        """Should upgrade http:// to https:// automatically."""
        from ot.config.models import McpServerConfig

        manager = ProxyManager()
        config = McpServerConfig(
            type="http",
            url="http://api.example.com/mcp",
        )

        manager._create_http_client("test", config)

        # Verify URL was upgraded to HTTPS
        mock_transport.assert_called_once()
        call_kwargs = mock_transport.call_args[1]
        assert call_kwargs["url"] == "https://api.example.com/mcp"


@pytest.mark.unit
@pytest.mark.core
class TestProxyManagerResources:
    """Tests for resource methods."""

    @pytest.mark.asyncio
    async def test_list_resources_no_connection(self) -> None:
        """Should raise ValueError when server not connected."""
        manager = ProxyManager()

        with pytest.raises(ValueError, match="not connected"):
            await manager.list_resources("unknown")

    @pytest.mark.asyncio
    async def test_list_resources_success(self) -> None:
        """Should list resources from connected server."""
        manager = ProxyManager()

        # Mock client with list_resources method
        mock_client = MagicMock()
        mock_resource = MagicMock()
        mock_resource.uri = "file:///test.txt"
        mock_resource.name = "Test File"
        mock_resource.description = "A test file"
        mock_client.list_resources = AsyncMock(return_value=[mock_resource])

        manager._clients = {"test_server": mock_client}

        resources = await manager.list_resources("test_server")

        assert len(resources) == 1
        assert resources[0]["uri"] == "file:///test.txt"
        assert resources[0]["name"] == "Test File"
        assert resources[0]["description"] == "A test file"

    @pytest.mark.asyncio
    async def test_read_resource_no_connection(self) -> None:
        """Should raise ValueError when server not connected."""
        manager = ProxyManager()

        with pytest.raises(ValueError, match="not connected"):
            await manager.read_resource("unknown", "file:///test.txt")

    @pytest.mark.asyncio
    async def test_read_resource_success(self) -> None:
        """Should read resource content from connected server."""
        manager = ProxyManager()

        # Mock client with read_resource method
        mock_client = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Resource content"

        # Mock ReadResourceResult with contents attribute
        mock_result = MagicMock()
        mock_result.contents = [mock_content]
        mock_client.read_resource = AsyncMock(return_value=mock_result)

        manager._clients = {"test_server": mock_client}

        content = await manager.read_resource("test_server", "file:///test.txt")

        assert content == "Resource content"


@pytest.mark.unit
@pytest.mark.core
class TestProxyManagerPrompts:
    """Tests for prompt methods."""

    @pytest.mark.asyncio
    async def test_list_prompts_no_connection(self) -> None:
        """Should raise ValueError when server not connected."""
        manager = ProxyManager()

        with pytest.raises(ValueError, match="not connected"):
            await manager.list_prompts("unknown")

    @pytest.mark.asyncio
    async def test_list_prompts_success(self) -> None:
        """Should list prompts from connected server."""
        manager = ProxyManager()

        # Mock client with list_prompts method
        mock_client = MagicMock()
        mock_prompt = MagicMock()
        mock_prompt.name = "summarize"
        mock_prompt.description = "Summarize text"
        mock_client.list_prompts = AsyncMock(return_value=[mock_prompt])

        manager._clients = {"test_server": mock_client}

        prompts = await manager.list_prompts("test_server")

        assert len(prompts) == 1
        assert prompts[0]["name"] == "summarize"
        assert prompts[0]["description"] == "Summarize text"

    @pytest.mark.asyncio
    async def test_get_prompt_no_connection(self) -> None:
        """Should raise ValueError when server not connected."""
        manager = ProxyManager()

        with pytest.raises(ValueError, match="not connected"):
            await manager.get_prompt("unknown", "summarize")

    @pytest.mark.asyncio
    async def test_get_prompt_success(self) -> None:
        """Should get rendered prompt from connected server."""
        manager = ProxyManager()

        # Mock client with get_prompt method
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Summarize this text"
        mock_result = MagicMock()
        mock_result.messages = [mock_message]
        mock_client.get_prompt = AsyncMock(return_value=mock_result)

        manager._clients = {"test_server": mock_client}

        content = await manager.get_prompt("test_server", "summarize", {"text": "test"})

        assert content == "Summarize this text"
