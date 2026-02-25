"""Runtime server management for OneTool proxy servers.

Provides enable/disable/restart/status for named MCP proxy servers.
All changes are in-memory only — state resets on server restart.

Example:
    server()                          # list all servers and status
    server(status="devtools")         # show status for one server
    server(enable="devtools-auto")    # enable a disabled server
    server(disable="devtools")        # disable an enabled server
    server(restart="devtools")        # disconnect and reconnect a server
"""

from __future__ import annotations

from typing import Any

from ot.config.loader import get_config
from ot.logging import LogSpan
from ot.proxy import get_proxy_manager

__all__ = ["server"]


def _get_server_info(server_name: str) -> dict[str, Any]:
    """Get connection info for a named server."""
    proxy = get_proxy_manager()
    conn = proxy.get_connection(server_name)
    connected = conn is not None
    tool_count = len(proxy.list_tools(server=server_name)) if connected else 0

    return {
        "name": server_name,
        "connected": connected,
        "tool_count": tool_count,
    }


def _format_server_row(
    name: str, enabled: bool, connected: bool, tool_count: int
) -> str:
    status_str = "connected" if connected else "disconnected"
    enabled_str = "enabled" if enabled else "disabled"
    tool_str = f" ({tool_count} tools)" if connected else ""
    return f"  {name}: {enabled_str}, {status_str}{tool_str}"


def server(
    status: str | None = None,
    enable: str | None = None,
    disable: str | None = None,
    restart: str | None = None,
) -> str:
    """List or manage runtime proxy server state.

    Without arguments, lists all configured servers with their status.
    Accepts one action at a time: status, enable, disable, or restart.

    All changes are in-memory only — state resets when OneTool restarts.

    Args:
        status: Show detailed status for a named server
        enable: Enable a disabled server and connect it
        disable: Disable an enabled server and disconnect it
        restart: Disconnect and reconnect a server (re-reads config)

    Returns:
        Status report or action confirmation message

    Example:
        ot.server()                           # list all servers
        ot.server(status="devtools")          # show status for devtools
        ot.server(enable="devtools-auto")     # enable devtools-auto
        ot.server(disable="devtools")         # disable devtools
        ot.server(restart="playwright")       # reconnect playwright
    """
    cfg = get_config()
    proxy = get_proxy_manager()

    if not cfg.servers:
        return "No servers configured. Add servers to servers.yaml."

    configured = cfg.servers

    def _unknown_error(name: str) -> str:
        available = ", ".join(sorted(configured.keys()))
        return f"Error: Unknown server '{name}'. Configured servers: {available}"

    with LogSpan(span="server") as s:
        # --- List all servers ---
        if status is None and enable is None and disable is None and restart is None:
            lines = [f"Servers ({len(configured)} configured):"]
            for srv_name in sorted(configured.keys()):
                srv_cfg = configured[srv_name]
                info = _get_server_info(srv_name)
                lines.append(
                    _format_server_row(
                        srv_name, srv_cfg.enabled, info["connected"], info["tool_count"]
                    )
                )
            s.add(count=len(configured))
            return "\n".join(lines)

        # --- Status for named server ---
        if status is not None:
            if status not in configured:
                return _unknown_error(status)
            srv_cfg = configured[status]
            info = _get_server_info(status)
            connected_str = "connected" if info["connected"] else "disconnected"
            enabled_str = "enabled" if srv_cfg.enabled else "disabled"
            lines = [
                f"Server: {status}",
                f"  State: {enabled_str}, {connected_str}",
            ]
            if info["connected"]:
                lines.append(f"  Tools: {info['tool_count']}")
            if err := proxy.get_error(status):
                lines.append(f"  Last error: {err}")
            s.add(server=status, connected=info["connected"])
            return "\n".join(lines)

        # --- Enable a server ---
        if enable is not None:
            if enable not in configured:
                return _unknown_error(enable)
            srv_cfg = configured[enable]
            if srv_cfg.enabled:
                info = _get_server_info(enable)
                if info["connected"]:
                    s.add(server=enable, action="enable", noop=True)
                    return f"Server '{enable}' is already enabled and connected ({info['tool_count']} tools)."
            srv_cfg.enabled = True
            proxy.connect_additional_sync(enable, srv_cfg)
            info = _get_server_info(enable)
            connected_str = "connected" if info["connected"] else "connection failed"
            tool_str = f" ({info['tool_count']} tools)" if info["connected"] else ""
            s.add(server=enable, action="enable", connected=info["connected"])
            return f"Server '{enable}' enabled — {connected_str}{tool_str}."

        # --- Disable a server ---
        if disable is not None:
            if disable not in configured:
                return _unknown_error(disable)
            srv_cfg = configured[disable]
            if not srv_cfg.enabled:
                s.add(server=disable, action="disable", noop=True)
                return f"Server '{disable}' is already disabled."
            srv_cfg.enabled = False
            proxy.disconnect_server_sync(disable)
            s.add(server=disable, action="disable")
            return f"Server '{disable}' disabled."

        # --- Restart a server ---
        if restart is not None:
            if restart not in configured:
                return _unknown_error(restart)
            srv_cfg = configured[restart]
            # Enable if currently disabled, then reconnect
            was_disabled = not srv_cfg.enabled
            if was_disabled:
                srv_cfg.enabled = True
            proxy.disconnect_server_sync(restart)
            proxy.connect_additional_sync(restart, srv_cfg)
            info = _get_server_info(restart)
            connected_str = "connected" if info["connected"] else "connection failed"
            tool_str = f" ({info['tool_count']} tools)" if info["connected"] else ""
            s.add(server=restart, action="restart", connected=info["connected"])
            return f"Server '{restart}' restarted — {connected_str}{tool_str}."

        return "No action specified."
