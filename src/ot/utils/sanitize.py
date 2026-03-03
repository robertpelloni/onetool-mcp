"""Output sanitization for prompt injection protection.

Protects against indirect prompt injection by sanitizing tool outputs
that may contain malicious payloads designed to trick the LLM.

Three-layer defense:
1. Trigger sanitization: Replace __ot, __run, mcp__onetool patterns
2. Tag sanitization: Remove <external-content-*> patterns
3. GUID-tagged boundaries: Wrap content in unpredictable tags
"""

from __future__ import annotations

import re
import uuid

__all__ = [
    "sanitize_output",
    "sanitize_tag_closes",
    "sanitize_triggers",
    "wrap_external_content",
]

# Regex patterns for trigger detection (case-insensitive)
# Matches legacy triggers: __ot, mcp__onetool, mcp__onetool__run
# Matches >>> tool-call form (>>> pack.tool() pattern) — bare >>> is NOT matched
# to avoid false positives in Python REPL output and docstrings.
TRIGGER_PATTERN = re.compile(
    r"(__ot\b|__run\b|mcp__onetool\w*|>>>\s+\w+\.\w+\s*\()",
    re.IGNORECASE,
)

# Pattern for tag injection attempts (both opening and closing)
# Matches: <external-content-*> and </external-content-*>
TAG_PATTERN = re.compile(
    r"</?external-content-[a-f0-9-]*>?",
    re.IGNORECASE,
)


def sanitize_triggers(content: str) -> str:
    """Replace trigger patterns that could invoke OneTool.

    Replaces patterns like __ot, mcp__onetool__run (legacy triggers) and
    >>> pack.tool( (primary trigger form) with [REDACTED:trigger] to prevent
    indirect prompt injection. Bare >>> without a pack.tool( call is preserved.

    Args:
        content: String content that may contain trigger patterns

    Returns:
        Content with triggers replaced by [REDACTED:trigger]
    """
    if not content:
        return content

    return TRIGGER_PATTERN.sub("[REDACTED:trigger]", content)


def sanitize_tag_closes(content: str) -> str:
    """Remove boundary tag patterns that could escape or confuse boundaries.

    Attackers may include </external-content-*> to close the boundary early,
    or <external-content-*> to create fake boundaries and confuse parsing.

    Args:
        content: String content that may contain boundary tag attempts

    Returns:
        Content with boundary tag patterns replaced by [REDACTED:tag]
    """
    if not content:
        return content

    return TAG_PATTERN.sub("[REDACTED:tag]", content)


def wrap_external_content(
    content: str,
    source: str | None = None,
    fmt: str = "",
) -> str:
    """Wrap external content in GUID-tagged boundaries.

    Applies all three defense layers:
    1. Sanitize trigger patterns
    2. Sanitize tag patterns
    3. Wrap in unpredictable GUID boundary tags using format-native comments

    Boundary style adapts to the output format:
    - yml/yml_h: ``# <external-content-XXXX>``
    - json/json_h: ``/* <external-content-XXXX> */`` (not strict JSON; for LLM consumption only)
    - raw/other: ``<external-content-XXXX>`` (XML-style)

    Args:
        content: External content to wrap
        source: Optional source identifier (e.g., URL, tool name)
        fmt: Output format mode (json, json_h, yml, yml_h, raw)

    Returns:
        Content wrapped in boundary tags with sanitization applied.
        Empty content is still wrapped (boundaries always apply).
    """
    # Generate unique boundary ID (4 hex chars = 16 bits = 65,536 possibilities)
    # Sufficient for unpredictability within a single request context
    boundary_id = uuid.uuid4().hex[:4]

    # Apply sanitization layers
    content = sanitize_triggers(content)
    content = sanitize_tag_closes(content)

    # Build boundary tag based on format
    tag = f"external-content-{boundary_id}"
    if source:
        tag += f' source="{source}"'

    if fmt in ("yml", "yml_h"):
        open_tag = f"# <{tag}>"
        close_tag = f"# </external-content-{boundary_id}>"
    elif fmt in ("json", "json_h"):
        open_tag = f"/* <{tag}> */"
        close_tag = f"/* </external-content-{boundary_id}> */"
    else:
        open_tag = f"<{tag}>"
        close_tag = f"</external-content-{boundary_id}>"

    return f"{open_tag}\n{content}\n{close_tag}"


def sanitize_output(
    content: str,
    source: str | None = None,
    enabled: bool = True,
    fmt: str = "",
) -> str:
    """Sanitize tool output for prompt injection protection.

    Main entry point for output sanitization. When enabled, wraps content
    in boundary tags and sanitizes trigger patterns.

    Args:
        content: Tool output content
        source: Optional source identifier (e.g., tool name, URL)
        enabled: Whether sanitization is enabled (default True)
        fmt: Output format mode for format-native comment boundaries

    Returns:
        Sanitized content wrapped in boundary tags, or original if disabled
    """
    if not enabled:
        return content

    return wrap_external_content(content, source=source, fmt=fmt)
