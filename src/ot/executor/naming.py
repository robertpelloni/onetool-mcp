"""Naming utilities for MCP tool alias resolution.

Provides fuzzy matching to support multiple naming conventions:
- snake_case (Python, Rust)
- kebab-case (CLI tools, MCP servers)
- camelCase (JavaScript, Java variables, Go)
- PascalCase (Java/C# methods, Go, classes)

All conventions are normalized to a canonical form for matching.
"""

from __future__ import annotations


def canonicalize_name(name: str) -> str:
    """Normalize a name to canonical form for fuzzy matching.

    Removes separators (-, _) and converts to lowercase.

    Args:
        name: Function/tool name in any convention.

    Returns:
        Canonical form: lowercase, no separators.

    Examples:
        >>> canonicalize_name("list_accounts")
        'listaccounts'
        >>> canonicalize_name("list-accounts")
        'listaccounts'
        >>> canonicalize_name("listAccounts")
        'listaccounts'
        >>> canonicalize_name("ListAccounts")
        'listaccounts'
        >>> canonicalize_name("LIST_ACCOUNTS")
        'listaccounts'
        >>> canonicalize_name("list-account_BY-Company")
        'listaccountbycompany'
    """
    return name.replace("_", "").replace("-", "").lower()


def find_canonical_match(
    accessor_name: str,
    available_names: list[str],
) -> str | None:
    """Find a tool name that matches the accessor via canonical normalization.

    Tries exact match first (fast path), then fuzzy matching.

    Args:
        accessor_name: Name used to access the tool (e.g., "list_accounts").
        available_names: List of actual tool names from MCP server.

    Returns:
        Matching tool name if found, None otherwise.

    Raises:
        ValueError: If multiple tools match the same canonical form (ambiguous).

    Examples:
        >>> find_canonical_match("list_accounts", ["list-accounts", "get-user"])
        'list-accounts'
        >>> find_canonical_match("listAccounts", ["list-accounts", "get-user"])
        'list-accounts'
        >>> find_canonical_match("unknown", ["list-accounts"])
        None
    """
    # Fast path: exact match
    if accessor_name in available_names:
        return accessor_name

    # Fuzzy match via canonicalization
    canonical_accessor = canonicalize_name(accessor_name)

    matches: list[str] = []
    for tool_name in available_names:
        if canonicalize_name(tool_name) == canonical_accessor:
            matches.append(tool_name)

    if not matches:
        return None

    if len(matches) > 1:
        # Multiple tools normalize to same canonical form - ambiguous
        raise ValueError(
            f"Ambiguous tool name '{accessor_name}': matches multiple tools: {matches}. "
            f"Use exact name with getattr(pack, 'exact-name')()"
        )

    return matches[0]


def suggest_similar_names(
    accessor_name: str,
    available_names: list[str],
    max_suggestions: int = 5,
) -> list[str]:
    """Suggest tool names that are similar to the accessor.

    Uses canonical form similarity - suggests tools whose canonical form
    starts with the canonical accessor, or contains it.

    Args:
        accessor_name: Name that was not found.
        available_names: List of actual tool names.
        max_suggestions: Maximum number of suggestions to return.

    Returns:
        List of suggested tool names, sorted by relevance.

    Examples:
        >>> suggest_similar_names("list_acc", ["list-accounts", "list-items", "get-account"])
        ['list-accounts', 'get-account']
    """
    canonical_accessor = canonicalize_name(accessor_name)

    # Categorize matches
    starts_with: list[str] = []
    contains: list[str] = []

    for tool_name in available_names:
        canonical_tool = canonicalize_name(tool_name)

        if canonical_tool.startswith(canonical_accessor):
            starts_with.append(tool_name)
        elif canonical_accessor in canonical_tool:
            contains.append(tool_name)

    # Combine: starts_with first (more relevant), then contains
    suggestions = starts_with + contains

    return suggestions[:max_suggestions]
