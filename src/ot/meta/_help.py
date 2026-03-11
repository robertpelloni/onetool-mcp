"""Unified help entry point."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ot.config import get_config
from ot.logging import LogSpan
from ot.meta._discovery import packs, servers, tools
from ot.meta._help_formatting import (
    _format_alias_help,
    _format_general_help,
    _format_pack_help,
    _format_search_results,
    _format_server_help,
    _format_snippet_help,
    _format_tool_help,
    _fuzzy_match,
    _item_matches,
    _snippet_matches,
)
from ot.meta._introspection import aliases, snippets

if TYPE_CHECKING:
    from ot.meta._constants import InfoLevel

log = LogSpan


def help(*, query: str = "", info: InfoLevel = "default") -> str:
    """Get help on OneTool commands, tools, packs, snippets, or aliases.

    Provides a unified entry point for discovering and getting help on
    any OneTool component. With no arguments, shows a general overview.
    With a query, searches across all types and returns detailed help.

    Args:
        query: Tool name, pack name, snippet, alias, or search term.
               Empty string shows general help overview.
        info: Detail level - "min" (names only), "default" (name + description,
              default), "full" (everything).

    Returns:
        Formatted help text

    Example:
        ot.help()
        ot.help(query="brave.search")
        ot.help(query="brave")
        ot.help(query="$b_q")
        ot.help(query="web fetch", info="min")
    """
    with log(span="ot.help", query=query or None, info=info) as s:
        # No query - show general help
        if not query:
            s.add("type", "general")
            return _format_general_help()

        cfg = get_config()

        # Check for exact tool match (contains "."); resolve short alias prefix
        if "." in query:
            from ot.meta._constants import PACK_SHORT_NAMES
            from ot.meta._discovery import tool_info as _tool_info
            _alias_to_full_t = {alias: full for full, alias in PACK_SHORT_NAMES.items()}
            pack_prefix, _, tool_suffix = query.partition(".")
            resolved_tool_query = f"{_alias_to_full_t.get(pack_prefix, pack_prefix)}.{tool_suffix}"
            detail = _tool_info(name=resolved_tool_query, info="full")
            if detail:
                assert isinstance(detail, dict)
                pack = resolved_tool_query.split(".")[0]
                s.add("type", "tool")
                s.add("match", resolved_tool_query)
                return _format_tool_help(detail, pack)

        # Check for exact server match (MCP proxy servers).
        # Try exact, then normalize hyphens→underscores (canonical form),
        # then underscores→hyphens (backward compat for old user configs).
        query_as_server = next(
            (q for q in [query, query.replace("-", "_"), query.replace("_", "-")]
             if q in cfg.servers),
            None,
        )
        if query_as_server is not None:
            from ot.proxy import get_proxy_manager as _get_proxy_mgr
            _proxy = _get_proxy_mgr()
            server_cfg = cfg.servers[query_as_server]
            conn = _proxy.get_connection(query_as_server)
            status = "connected" if conn else "disconnected"
            proxy_tools = _proxy.list_tools(server=query_as_server) if conn else []
            native_instructions = _proxy.get_server_instructions(query_as_server)
            s.add("type", "server")
            s.add("match", query_as_server)
            return _format_server_help(
                query_as_server, server_cfg, status, proxy_tools, native_instructions
            )

        # Check for exact pack match (also resolves short aliases like "img" → "ot_image")
        from ot.meta._constants import PACK_SHORT_NAMES
        _alias_to_full = {alias: full for full, alias in PACK_SHORT_NAMES.items()}
        resolved_query = _alias_to_full.get(query, query)

        pack_names = packs(info="min")
        if resolved_query in pack_names:
            from ot.meta._discovery import pack_info as _pack_info
            pi = _pack_info(name=resolved_query, info="default")
            if pi and "error" not in pi:
                s.add("type", "pack")
                s.add("match", resolved_query)
                return _format_pack_help(resolved_query, pi)

        # Check for snippet match (starts with "$")
        if query.startswith("$"):
            snippet_name = query[1:]  # Remove "$"
            from ot.meta._introspection import snippet_info as _snippet_info
            si = _snippet_info(name=snippet_name, info="full")
            if "error" not in si:
                assert isinstance(si, dict)
                s.add("type", "snippet")
                s.add("match", query)
                return _format_snippet_help(si)

        # Check for exact alias match
        if cfg.alias and query in cfg.alias:
            target = cfg.alias[query]
            s.add("type", "alias")
            s.add("match", query)
            return _format_alias_help(query, target)

        # Fuzzy search across all types
        s.add("type", "search")

        # Fetch once at default level — used for both name extraction and display
        all_tools = tools()
        all_packs = packs()
        all_snippets = snippets()
        all_aliases = aliases()
        all_server_names: list[str] = servers(info="min")  # type: ignore[assignment]

        # Fuzzy match across types
        matched_tools = _fuzzy_match(query, [t["name"] if isinstance(t, dict) else t for t in all_tools])
        matched_packs = _fuzzy_match(query, [p["name"] if isinstance(p, dict) else p for p in all_packs])
        matched_snippets = _fuzzy_match(query, [sn["name"] if isinstance(sn, dict) else sn for sn in all_snippets])
        matched_aliases = _fuzzy_match(query, [a["name"] if isinstance(a, dict) else a for a in all_aliases])
        matched_servers = _fuzzy_match(query, all_server_names)

        total_matches = (
            len(matched_tools) + len(matched_packs) + len(matched_snippets)
            + len(matched_aliases) + len(matched_servers)
        )
        s.add("matches", total_matches)

        # Filter from already-fetched results — no additional discovery calls
        tools_results = [t for t in all_tools if _item_matches(t, matched_tools)]
        packs_results = [p for p in all_packs if _item_matches(p, matched_packs)]
        snippets_results = [sn for sn in all_snippets if _snippet_matches(sn, matched_snippets)]
        aliases_results = [a for a in all_aliases if _item_matches(a, matched_aliases)]
        servers_results = [n for n in all_server_names if n in matched_servers]

        return _format_search_results(
            query=query,
            tools_results=tools_results,
            packs_results=packs_results,
            snippets_results=snippets_results,
            aliases_results=aliases_results,
            info=info,
            servers_results=servers_results,
        )
