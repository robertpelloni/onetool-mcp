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


def help(*, query: str = "", info: InfoLevel = "min") -> str:
    """Get help on OneTool commands, tools, packs, snippets, or aliases.

    Provides a unified entry point for discovering and getting help on
    any OneTool component. With no arguments, shows a general overview.
    With a query, searches across all types and returns detailed help.

    Args:
        query: Tool name, pack name, snippet, alias, or search term.
               Empty string shows general help overview.
        info: Detail level - "list" (names only), "min" (name + description),
              "full" (everything). Default is "min".

    Returns:
        Formatted help text

    Example:
        ot.help()
        ot.help(query="brave.search")
        ot.help(query="brave")
        ot.help(query="$b_q")
        ot.help(query="web fetch", info="list")
    """
    with log(span="ot.help", query=query or None, info=info) as s:
        # No query - show general help
        if not query:
            s.add("type", "general")
            return _format_general_help()

        cfg = get_config()

        # Check for exact tool match (contains ".")
        if "." in query:
            tool_results = tools(pattern=query, info="full")
            # Look for exact match
            for tool in tool_results:
                if isinstance(tool, dict) and tool.get("name") == query:
                    pack = query.split(".")[0]
                    s.add("type", "tool")
                    s.add("match", query)
                    return _format_tool_help(tool, pack)

        # Check for exact server match (MCP proxy servers)
        server_names = servers(info="list")
        if query in server_names:
            server_results = servers(pattern=query, info="full")
            if server_results:
                s.add("type", "server")
                s.add("match", query)
                return str(server_results[0])

        # Check for exact pack match
        pack_names = packs(info="list")
        if query in pack_names:
            pack_results = packs(pattern=query, info="full")
            if pack_results:
                s.add("type", "pack")
                s.add("match", query)
                return _format_pack_help(query, str(pack_results[0]))

        # Check for snippet match (starts with "$")
        if query.startswith("$"):
            snippet_name = query[1:]  # Remove "$"
            snippet_results = snippets(pattern=snippet_name, info="full")
            # Look for exact match
            for snippet in snippet_results:
                if isinstance(snippet, str) and snippet.startswith(f"name: {snippet_name}"):
                    s.add("type", "snippet")
                    s.add("match", query)
                    return _format_snippet_help(snippet)

        # Check for exact alias match
        if cfg.alias and query in cfg.alias:
            target = cfg.alias[query]
            s.add("type", "alias")
            s.add("match", query)
            return _format_alias_help(query, target)

        # Fuzzy search across all types
        s.add("type", "search")

        # Get all candidates for fuzzy matching
        all_tool_names = tools(info="list")
        all_pack_names = pack_names  # Already have this
        all_snippet_names = snippets(info="list")
        all_alias_names = aliases(info="list")

        # Fuzzy match across types
        matched_tools = _fuzzy_match(query, [str(t) for t in all_tool_names])
        matched_packs = _fuzzy_match(query, [str(p) for p in all_pack_names])
        matched_snippets = _fuzzy_match(query, [str(sn) for sn in all_snippet_names])
        matched_aliases = _fuzzy_match(query, [str(a) for a in all_alias_names])

        total_matches = len(matched_tools) + len(matched_packs) + len(matched_snippets) + len(matched_aliases)
        s.add("matches", total_matches)

        # Show search results - info parameter controls detail level
        tools_results = [t for t in tools(info=info) if _item_matches(t, matched_tools)]
        packs_results = [p for p in packs(info=info) if _item_matches(p, matched_packs)]
        snippets_results = [sn for sn in snippets(info=info) if _snippet_matches(sn, matched_snippets)]
        aliases_results = [a for a in aliases(info=info) if _item_matches(a, matched_aliases)]

        return _format_search_results(
            query=query,
            tools_results=tools_results,
            packs_results=packs_results,
            snippets_results=snippets_results,
            aliases_results=aliases_results,
            info=info,
        )
