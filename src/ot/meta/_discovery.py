"""Tool, pack, and server discovery functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ot.config import get_config
from ot.logging import LogSpan
from ot.meta._tool_discovery import _build_proxy_tool_info, _build_tool_info
from ot.proxy import get_proxy_manager

if TYPE_CHECKING:
    from ot.meta._constants import InfoLevel, ServerInfoLevel

log = LogSpan


def tools(
    *,
    pattern: str = "",
    info: InfoLevel = "list",
) -> list[dict[str, Any] | str]:
    """List all available tools with optional filtering.

    Lists registered local tools and proxied MCP server tools.
    Use pattern for substring filtering.

    Args:
        pattern: Filter tools by name pattern (case-insensitive substring match)
        info: Output verbosity level - "list" (names only, default), "min" (name +
              description truncated to 100 chars), "core" (name + signature + truncated
              description + args — recommended for tool discovery), or "full" (complete details)

    Returns:
        List of tool names (info="list") or tool dicts (info="min"/"full")

    Example:
        ot.tools()
        ot.tools(pattern="search")
        ot.tools(pattern="brave.")
        ot.tools(info="list")
        ot.tools(pattern="brave.search", info="core")
        ot.tools(pattern="brave.search", info="full")
    """
    from ot.executor.tool_loader import load_tool_registry

    with log(span="ot.tools", pattern=pattern or None, info=info) as s:
        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()

        tools_list: list[dict[str, Any] | str] = []

        # Local tools from registry
        from ot.executor.worker_proxy import WorkerPackProxy

        for pack_name, pack_funcs in runner_registry.packs.items():
            # Handle both dict and WorkerPackProxy
            if isinstance(pack_funcs, WorkerPackProxy):
                func_names = list(pack_funcs.functions)
                func_items = [(n, getattr(pack_funcs, n)) for n in func_names]
            else:
                func_items = list(pack_funcs.items())

            for func_name, func in func_items:
                full_name = f"{pack_name}.{func_name}"

                if pattern and pattern.lower() not in full_name.lower():
                    continue

                tools_list.append(_build_tool_info(full_name, func, "local", info))

        # Proxied tools
        for proxy_tool in proxy.list_tools():
            tool_name = f"{proxy_tool.server}.{proxy_tool.name}"

            if pattern and pattern.lower() not in tool_name.lower():
                continue

            tools_list.append(
                _build_proxy_tool_info(
                    tool_name,
                    proxy_tool.description or "",
                    proxy_tool.input_schema,
                    f"mcp:{proxy_tool.server}",
                    info,
                )
            )

        # Sort by name (handle both str and dict)
        tools_list.sort(key=lambda t: t if isinstance(t, str) else t["name"])
        s.add("count", len(tools_list))
        return tools_list


def packs(
    *,
    pattern: str = "",
    info: InfoLevel = "min",
) -> list[dict[str, Any] | str]:
    """List all packs with optional filtering.

    Lists all available packs (local and proxy).
    Use pattern for substring filtering.

    Args:
        pattern: Filter packs by name pattern (case-insensitive substring)
        info: Output verbosity level - "list" (names only), "min" (name + source + tool_count),
              or "full" (detailed info with instructions and tool list)

    Returns:
        List of pack names (info="list") or pack dicts/strings (info="min"/"full")

    Example:
        ot.packs()
        ot.packs(pattern="brav")
        ot.packs(info="list")
        ot.packs(pattern="brave", info="full")
    """
    from ot.executor.tool_loader import load_tool_registry
    from ot.prompts import PromptsError, get_pack_instructions, get_prompts

    with log(span="ot.packs", pattern=pattern or None, info=info) as s:
        runner_registry = load_tool_registry()
        proxy = get_proxy_manager()

        # Build lookup of extension packs (user-created, non-internal)
        ext_lookup = {t.pack: t for t in runner_registry.extension_tools if t.pack}

        # Collect all packs
        local_packs = set(runner_registry.packs.keys())
        proxy_packs = set(proxy.servers)
        all_pack_names = sorted(local_packs | proxy_packs)

        # Filter by pattern
        if pattern:
            all_pack_names = [p for p in all_pack_names if pattern.lower() in p.lower()]

        # info="list" - just names
        if info == "list":
            s.add("count", len(all_pack_names))
            return all_pack_names  # type: ignore[return-value]

        # info="full" - detailed info for each matching pack
        if info == "full":
            results: list[dict[str, Any] | str] = []
            cfg = get_config()

            for pack_name in all_pack_names:
                is_local = pack_name in local_packs

                # Build detailed pack info
                lines = [f"# {pack_name} pack", ""]

                # Show source type
                if is_local:
                    if pack_name in ext_lookup:
                        lines.append("**Type:** Extension")
                        lines.append(f"**Path:** {ext_lookup[pack_name].path}")
                    else:
                        lines.append("**Type:** Local")
                else:
                    lines.append("**Type:** MCP Proxy Server")
                lines.append("")

                # Get instructions from prompts.yaml
                try:
                    prompts_config = get_prompts()
                    configured = get_pack_instructions(prompts_config, pack_name)
                    if configured:
                        lines.append("## Instructions")
                        lines.append("")
                        lines.append(configured)
                        lines.append("")
                except PromptsError:
                    pass

                # For proxy packs, also check server config for instructions
                if not is_local and pack_name in cfg.servers:
                    server_cfg = cfg.servers[pack_name]
                    if server_cfg.instructions:
                        # Only add header if not already added from prompts
                        if "## Instructions" not in "\n".join(lines):
                            lines.append("## Instructions")
                            lines.append("")
                        lines.append(server_cfg.instructions.strip())
                        lines.append("")

                # List tools in this pack
                lines.append("## Tools")
                lines.append("")

                if is_local:
                    from ot.executor.worker_proxy import WorkerPackProxy

                    pack_funcs = runner_registry.packs[pack_name]
                    if isinstance(pack_funcs, WorkerPackProxy):
                        func_items = [(n, getattr(pack_funcs, n)) for n in pack_funcs.functions]
                    else:
                        func_items = list(pack_funcs.items())

                    for func_name, func in sorted(func_items):
                        doc = func.__doc__ or "(no description)"
                        first_line = doc.split("\n")[0].strip()
                        lines.append(f"- **{pack_name}.{func_name}**: {first_line}")
                else:
                    proxy_tools = proxy.list_tools(server=pack_name)
                    for tool in sorted(proxy_tools, key=lambda t: t.name):
                        desc = tool.description or "(no description)"
                        first_line = desc.split("\n")[0].strip()
                        lines.append(f"- **{pack_name}.{tool.name}**: {first_line}")

                results.append("\n".join(lines))

            s.add("count", len(results))
            return results

        # info="min" (default) - summary for each pack
        packs_list: list[dict[str, Any] | str] = []

        for pack_name in all_pack_names:
            is_local = pack_name in local_packs
            source = "local" if is_local else "mcp"

            # Count tools in pack
            if is_local:
                from ot.executor.worker_proxy import WorkerPackProxy

                pack_funcs = runner_registry.packs[pack_name]
                if isinstance(pack_funcs, WorkerPackProxy):
                    tool_count = len(pack_funcs.functions)
                else:
                    tool_count = len(pack_funcs)
            else:
                tool_count = len(proxy.list_tools(server=pack_name))

            entry: dict[str, Any] = {
                "name": pack_name,
                "source": source,
                "tool_count": tool_count,
            }
            if pack_name in ext_lookup:
                entry["is_extension"] = True
                entry["path"] = str(ext_lookup[pack_name].path)
            packs_list.append(entry)

        s.add("count", len(packs_list))
        return packs_list


def servers(
    *,
    pattern: str = "",
    info: ServerInfoLevel = "min",
) -> list[dict[str, Any] | str]:
    """List configured MCP proxy servers with optional filtering.

    Shows all MCP servers configured in servers.yaml, including their
    connection status, tool count, and instructions.

    Args:
        pattern: Filter servers by name pattern (case-insensitive substring)
        info: Output verbosity level:
            - "list": names only
            - "min": name + status + tool_count (default)
            - "full": detailed info with instructions and tools
            - "resources": list resources per server
            - "prompts": list prompts per server

    Returns:
        List of server names (info="list") or server dicts/strings (info="min"/"full"/"resources"/"prompts")

    Example:
        ot.servers()
        ot.servers(pattern="github")
        ot.servers(info="full")
        ot.servers(info="resources")
        ot.servers(pattern="chrome-devtools", info="prompts")
    """
    proxy = get_proxy_manager()
    cfg = get_config()

    with log(span="ot.servers", pattern=pattern or None, info=info) as s:
        # Get all configured servers
        all_server_names = sorted(cfg.servers.keys())

        # Filter by pattern
        if pattern:
            all_server_names = [
                name for name in all_server_names if pattern.lower() in name.lower()
            ]

        # info="list" - just names
        if info == "list":
            s.add("count", len(all_server_names))
            return all_server_names  # type: ignore[return-value]

        # info="full" - detailed info for each server
        if info == "full":
            results: list[dict[str, Any] | str] = []

            for server_name in all_server_names:
                server_cfg = cfg.servers[server_name]
                conn = proxy.get_connection(server_name)
                status = "connected" if conn else "disconnected"
                tool_count = len(proxy.list_tools(server=server_name)) if conn else 0

                lines = [f"# {server_name} server", ""]
                lines.append(f"**Type:** MCP Proxy Server ({server_cfg.type})")
                lines.append(f"**Status:** {status}")
                lines.append(f"**Enabled:** {server_cfg.enabled}")
                if server_cfg.type == "http" and server_cfg.url:
                    lines.append(f"**URL:** {server_cfg.url}")
                elif server_cfg.type == "stdio" and server_cfg.command:
                    cmd = f"{server_cfg.command} {' '.join(server_cfg.args)}"
                    lines.append(f"**Command:** {cmd}")

                # Add resource and prompt counts if connected
                if conn:
                    try:
                        resource_count = len(proxy.list_resources_sync(server_name))
                        prompt_count = len(proxy.list_prompts_sync(server_name))
                        lines.append(f"**Resources:** {resource_count}")
                        lines.append(f"**Prompts:** {prompt_count}")
                    except Exception:
                        # Silently skip if resources/prompts not supported
                        pass

                lines.append("")

                # Show instructions if configured
                if server_cfg.instructions:
                    lines.append("## Instructions")
                    lines.append("")
                    lines.append(server_cfg.instructions.strip())
                    lines.append("")

                # List tools if connected
                if conn:
                    lines.append(f"## Tools ({tool_count})")
                    lines.append("")
                    proxy_tools = proxy.list_tools(server=server_name)
                    for tool in sorted(proxy_tools, key=lambda t: t.name):
                        desc = tool.description or "(no description)"
                        first_line = desc.split("\n")[0].strip()
                        lines.append(f"- **{server_name}.{tool.name}**: {first_line}")
                elif server_cfg.enabled:
                    lines.append("## Tools")
                    lines.append("")
                    lines.append("(not connected)")
                    # Show error if available
                    error = proxy.get_error(server_name)
                    if error:
                        lines.append("")
                        lines.append(f"**Error:** {error}")

                results.append("\n".join(lines))

            s.add("count", len(results))
            return results

        # info="resources" - list resources per server
        if info == "resources":
            results_resources: list[dict[str, Any] | str] = []

            for server_name in all_server_names:
                conn = proxy.get_connection(server_name)
                if not conn:
                    results_resources.append({
                        "server": server_name,
                        "status": "disconnected",
                        "resources": [],
                    })
                    continue

                try:
                    resources = proxy.list_resources_sync(server_name, timeout=10.0)

                    results_resources.append({
                        "server": server_name,
                        "status": "connected",
                        "resource_count": len(resources),
                        "resources": resources,
                    })
                except Exception as e:
                    results_resources.append({
                        "server": server_name,
                        "status": "error",
                        "error": str(e),
                        "resources": [],
                    })

            s.add("count", len(results_resources))
            return results_resources

        # info="prompts" - list prompts per server
        if info == "prompts":
            results_prompts: list[dict[str, Any] | str] = []

            for server_name in all_server_names:
                conn = proxy.get_connection(server_name)
                if not conn:
                    results_prompts.append({
                        "server": server_name,
                        "status": "disconnected",
                        "prompts": [],
                    })
                    continue

                try:
                    prompts = proxy.list_prompts_sync(server_name, timeout=10.0)

                    results_prompts.append({
                        "server": server_name,
                        "status": "connected",
                        "prompt_count": len(prompts),
                        "prompts": prompts,
                    })
                except Exception as e:
                    results_prompts.append({
                        "server": server_name,
                        "status": "error",
                        "error": str(e),
                        "prompts": [],
                    })

            s.add("count", len(results_prompts))
            return results_prompts

        # info="min" (default) - summary for each server
        servers_list: list[dict[str, Any] | str] = []

        for server_name in all_server_names:
            server_cfg = cfg.servers[server_name]
            conn = proxy.get_connection(server_name)
            status = "connected" if conn else "disconnected"
            tool_count = len(proxy.list_tools(server=server_name)) if conn else 0

            server_info: dict[str, Any] = {
                "name": server_name,
                "type": server_cfg.type,
                "enabled": server_cfg.enabled,
                "status": status,
                "tool_count": tool_count,
            }
            # Include error if disconnected
            if not conn:
                error = proxy.get_error(server_name)
                if error:
                    server_info["error"] = error
            servers_list.append(server_info)

        s.add("count", len(servers_list))
        return servers_list
