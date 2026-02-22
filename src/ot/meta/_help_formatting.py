"""Help formatting utilities for ot.help()."""

from __future__ import annotations

from typing import Any

from ot.meta._constants import DOC_BASE_URL, DOC_SLUGS, InfoLevel


def _get_doc_url(pack: str) -> str:
    """Get documentation URL for a pack.

    Args:
        pack: Pack name (e.g., "brave", "file")

    Returns:
        Documentation URL for the pack
    """
    slug = DOC_SLUGS.get(pack, pack)
    return f"{DOC_BASE_URL}{slug}/"


def _fuzzy_match(query: str, candidates: list[str], threshold: float = 0.6) -> list[str]:
    """Return candidates that fuzzy match query, sorted by score.

    Args:
        query: Search query string
        candidates: List of candidate strings to match against
        threshold: Minimum similarity ratio (0.0 to 1.0) for fuzzy matches

    Returns:
        List of matching candidates, sorted by match score (best first)
    """
    from difflib import SequenceMatcher

    query_lower = query.lower()
    scored: list[tuple[str, float]] = []

    for candidate in candidates:
        candidate_lower = candidate.lower()
        # Substring match gets high score
        if query_lower in candidate_lower:
            scored.append((candidate, 1.0))
        else:
            ratio = SequenceMatcher(None, query_lower, candidate_lower).ratio()
            if ratio >= threshold:
                scored.append((candidate, ratio))

    return [c for c, _ in sorted(scored, key=lambda x: -x[1])]


def _format_general_help() -> str:
    """Format general help overview shown when no query is provided.

    Returns:
        Formatted help text with discovery commands, info levels, and examples
    """
    return """# OneTool Help

## Discovery
  ot.tools()              - List all tools
  ot.tools(pattern="web") - Filter by pattern
  ot.packs()              - List all packs (local + MCP)
  ot.servers()            - List MCP proxy servers
  ot.snippets()           - List all snippets
  ot.aliases()            - List all aliases
  ot.help(query="..")     - Search for help

## Info Levels
  info="list" - Names only
  info="min"  - Name + description (default)
  info="full" - Everything (includes instructions)

## Quick Examples
  brave.search(query="AI news")
  web.fetch(url="https://...")
  $b_q q=search terms

## Tips
  - Use keyword args: func(arg=value)
  - Batch when possible: func(items=[...])"""


def _format_tool_help(tool_info: dict[str, Any], pack: str) -> str:
    """Format detailed help for a single tool.

    Args:
        tool_info: Tool info dict from _build_tool_info with info="full"
        pack: Pack name for documentation URL

    Returns:
        Formatted tool help text
    """
    lines = [f"# {tool_info['name']}", ""]

    if tool_info.get("description"):
        lines.append(tool_info["description"])
        lines.append("")

    if tool_info.get("signature"):
        lines.append("## Signature")
        lines.append(tool_info["signature"])
        lines.append("")

    if tool_info.get("args"):
        lines.append("## Arguments")
        for arg in tool_info["args"]:
            lines.append(f"- {arg}")
        lines.append("")

    if tool_info.get("returns"):
        lines.append("## Returns")
        lines.append(tool_info["returns"])
        lines.append("")

    if tool_info.get("example"):
        lines.append("## Example")
        lines.append(tool_info["example"])
        lines.append("")

    lines.append("## Docs")
    lines.append(_get_doc_url(pack))

    return "\n".join(lines)


def _format_pack_help(pack_name: str, pack_info: str) -> str:
    """Format detailed help for a pack.

    Args:
        pack_name: Name of the pack
        pack_info: Pack info string from packs(info="full")

    Returns:
        Formatted pack help text with doc URL appended
    """
    lines = [pack_info, "", "## Docs", _get_doc_url(pack_name)]
    return "\n".join(lines)


def _format_snippet_help(snippet_info: str) -> str:
    """Format detailed help for a snippet.

    Args:
        snippet_info: Snippet info string from snippets(info="full")

    Returns:
        Formatted snippet help text
    """
    return f"# Snippet\n\n{snippet_info}"


def _format_alias_help(alias_name: str, target: str) -> str:
    """Format detailed help for an alias.

    Args:
        alias_name: Name of the alias
        target: Target function the alias maps to

    Returns:
        Formatted alias help text
    """
    lines = [
        f"# Alias: {alias_name}",
        "",
        f"Maps to: `{target}`",
        "",
        "Use this alias as a shorthand for the target function.",
    ]
    return "\n".join(lines)


def _item_matches(item: dict[str, Any] | str, matched_names: list[str], key: str = "name") -> bool:
    """Check if item name is in matched_names list.

    Args:
        item: Either a string name or dict with name key
        matched_names: List of matched name strings
        key: Dict key to extract name from (default: "name")

    Returns:
        True if item's name is in matched_names
    """
    if isinstance(item, str):
        # For "name: desc" or "name -> target" formats, extract the name part
        if ": " in item:
            name = item.split(":")[0]
        elif " ->" in item:
            name = item.split(" ->")[0]
        else:
            name = item
        return name in matched_names
    return item.get(key) in matched_names


def _snippet_matches(item: dict[str, Any] | str, matched_names: list[str]) -> bool:
    """Check if snippet item matches any of the matched names.

    Args:
        item: Either a string or dict snippet item
        matched_names: List of matched snippet name strings

    Returns:
        True if snippet matches
    """
    if not matched_names:
        return False
    if isinstance(item, str):
        name = item.split(":")[0]
        if name in matched_names:
            return True
        return any(item == m or item.startswith(m + ":") for m in matched_names)
    return item.get("name") in matched_names


def _format_search_results(
    query: str,
    tools_results: list[dict[str, Any] | str],
    packs_results: list[dict[str, Any] | str],
    snippets_results: list[dict[str, Any] | str],
    aliases_results: list[dict[str, Any] | str],
    info: InfoLevel,
) -> str:
    """Format search results grouped by type.

    Args:
        query: Original search query
        tools_results: Matching tools
        packs_results: Matching packs
        snippets_results: Matching snippets
        aliases_results: Matching aliases
        info: Output verbosity level

    Returns:
        Formatted search results text
    """
    lines = [f'# Search results for "{query}"', ""]

    if tools_results:
        lines.append("## Tools")
        for tool in tools_results:
            if isinstance(tool, str):
                lines.append(f"- {tool}")
            elif info == "min":
                lines.append(f"- {tool['name']}: {tool.get('description', '')}")
            else:
                lines.append(f"- {tool['name']}")
        lines.append("")

    if packs_results:
        lines.append("## Packs")
        for pack in packs_results:
            if isinstance(pack, str):
                lines.append(f"- {pack}")
            elif info == "min":
                lines.append(f"- {pack['name']} ({pack.get('tool_count', 0)} tools)")
            else:
                lines.append(f"- {pack['name']}")
        lines.append("")

    if snippets_results:
        lines.append("## Snippets")
        for snippet in snippets_results:
            if isinstance(snippet, str):
                # For info="min", format is "name: description"
                snippet_name = snippet.split(":")[0] if ":" in snippet else snippet
                lines.append(f"- ${snippet_name}")
            else:
                lines.append(f"- ${snippet}")
        lines.append("")

    if aliases_results:
        lines.append("## Aliases")
        for alias in aliases_results:
            if isinstance(alias, str):
                lines.append(f"- {alias}")
            else:
                lines.append(f"- {alias['name']} -> {alias['target']}")
        lines.append("")

    if not any([tools_results, packs_results, snippets_results, aliases_results]):
        lines.append("No matches found.")
        lines.append("")
        lines.append("Try browsing with:")
        lines.append("  ot.tools()    - List all tools")
        lines.append("  ot.packs()    - List all packs (local + MCP)")
        lines.append("  ot.servers()  - List MCP proxy servers")
        lines.append("  ot.snippets() - List all snippets")
        lines.append("  ot.aliases()  - List all aliases")

    return "\n".join(lines).rstrip()
