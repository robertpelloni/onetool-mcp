"""My extension tool

An extension tool with full onetool access.
Runs in-process with access to ot.logging, ot.config, and ot.tools.
Uses httpx (bundled) for HTTP requests.
"""

from __future__ import annotations

pack = "existing_tool"

import httpx

from ot.config import get_secret, get_tool_config
from ot.logging import LogSpan

# Optional: for calling other tools
# from ot.tools import call_tool, get_pack

__all__ = ["run"]

# Shared HTTP client (connection pooling)
_client = httpx.Client(timeout=30.0, follow_redirects=True)


def run(
    *,
    input: str,
) -> str:
    """Execute the tool function

    Args:
        input: The input string

    Returns:
        Processed result or error message

    Example:
        existing_tool.run(input="hello")
    """
    with LogSpan(span="existing_tool.run", inputLen=len(input)) as s:
        try:
            # TODO: Implement your logic here
            # Access secrets: api_key = get_secret("MY_API_KEY")
            # Access config: timeout = get_tool_config("existing_tool", "timeout", 30.0)
            # Call other tools: result = call_tool("ot_llm.transform", input=text, prompt="...")
            result = f"Processed: {input}"
            s.add(outputLen=len(result))
            return result
        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"
