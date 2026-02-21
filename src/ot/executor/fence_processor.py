"""Fence processing for command execution.

Handles stripping of:
- Execution trigger prefixes (>>>, __run, __ot, __onetool, mcp__onetool__run)
- Markdown code fences (triple backticks with/without language)
- Inline backticks (single and double)

Used by the runner to clean commands before execution.
"""

from __future__ import annotations

import re


def strip_fences(command: str) -> tuple[str, bool]:
    """Strip execution prefixes, markdown code fences, and inline backticks.

    Execution trigger prefixes (stripped first):
        >>>                  - Python REPL symbol; recommended human-friendly form
        __run                - short form following __(tool) pattern; systematic
        __ot                 - legacy; kept for backward compat; not in docs
        __ot__run            - legacy variant
        __onetool            - legacy full name
        __onetool__run       - legacy full name explicit
        mcp__onetool__run    - canonical MCP tool name

    Each prefix supports two invocation styles:
        <prefix> func(arg="value")     - simple call
        <prefix> + code fence          - multi-line code fence

    Note: mcp__ot__run is NOT a valid prefix.

    Markdown fences (stripped after prefix):
        ```python
        code here
        ```

        `code here`

        `` `code here` ``

    Args:
        command: Raw command string that may contain prefixes and fences

    Returns:
        Tuple of (stripped command, whether anything was stripped)
    """
    # Normalize line endings before any processing
    stripped = command.strip().replace("\r\n", "\n").replace("\r", "\n")
    anything_stripped = False

    # Strip execution trigger prefixes:
    # - >>> (Python REPL symbol; recommended)
    # - __run (short form; systematic)
    # - __ot, __ot__run (legacy short name)
    # - __onetool, __onetool__run (legacy full name)
    # - mcp__onetool__run (canonical MCP call)
    # Note: mcp__ot__run is NOT valid
    prefix_pattern = r"^(?:mcp__onetool__run|__onetool(?:__run)?|__ot(?:__run)?|__run|>>>)\s*"
    match = re.match(prefix_pattern, stripped)
    if match:
        stripped = stripped[match.end() :].strip()
        anything_stripped = True

    # Handle triple backtick fenced blocks
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1 and stripped.endswith("```"):
            content = stripped[first_newline + 1 : -3].strip()
            return content, True

    # Handle double backtick fenced blocks: `` `code` ``
    if stripped.startswith("`` `") and stripped.endswith("` ``"):
        content = stripped[4:-4].strip()
        return content, True

    if stripped.startswith("``") and stripped.endswith("``"):
        content = stripped[2:-2].strip()
        return content, True

    # Handle inline single backticks: `code`
    if stripped.startswith("`") and stripped.endswith("`") and stripped.count("`") == 2:
        content = stripped[1:-1].strip()
        return content, True

    return stripped, anything_stripped
