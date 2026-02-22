"""OneTool core introspection tools (ot pack).

Provides tool discovery and messaging under the unified `ot` pack.
These are core introspection functions, not external tools, so they
live in the core package rather than tools_dir.

Functions:
    ot.tools() - List or get tools with full documentation
    ot.packs() - List or get packs with instructions
    ot.aliases() - List or get alias definitions
    ot.snippets() - List or get snippet definitions
    ot.config() - Show configuration summary
    ot.health() - Check system health
    ot.stats() - Get runtime statistics
    ot.result() - Query stored large output results
    ot.notify() - Publish message to topic
    ot.reload() - Force configuration reload
"""

from __future__ import annotations

import time
from typing import Any

from ot import __version__
from ot.logging import LogSpan
from ot.meta._config_health import config, health, reload
from ot.meta._constants import PACK_NAME, resolve_ot_path
from ot.meta._debug import debug
from ot.meta._discovery import packs, servers, tools
from ot.meta._help import help
from ot.meta._help_formatting import (
    _format_general_help,
    _format_search_results,
    _format_tool_help,
    _fuzzy_match,
    _get_doc_url,
)
from ot.meta._introspection import aliases, snippets
from ot.meta._messaging import _match_topic_to_file, _resolve_path, notify
from ot.meta._server_mgmt import security, server, skills
from ot.meta._stats import result, stats
from ot.meta._tool_discovery import (
    _build_proxy_tool_info,
    _parse_input_schema,
    _schema_to_signature,
    _truncate,
)

# Track when module was first loaded (OneTool start time)
_MODULE_LOAD_TIME = time.time()

# Alias for cleaner logging calls in this module
log = LogSpan

__all__ = [
    "PACK_NAME",
    "_build_proxy_tool_info",
    "_format_general_help",
    "_format_search_results",
    "_format_tool_help",
    "_fuzzy_match",
    "_get_doc_url",
    "_match_topic_to_file",
    "_parse_input_schema",
    "_resolve_path",
    "_schema_to_signature",
    "_truncate",
    "aliases",
    "config",
    "debug",
    "get_ot_pack_functions",
    "health",
    "help",
    "notify",
    "packs",
    "reload",
    "resolve_ot_path",
    "result",
    "security",
    "server",
    "servers",
    "skills",
    "snippets",
    "stats",
    "tools",
    "version",
]


def version() -> str:
    """Return OneTool version string.

    Returns:
        Version string (e.g., "1.0.0")

    Example:
        ot.version()
    """
    return __version__


def get_ot_pack_functions() -> dict[str, Any]:
    """Get all ot pack functions for registration.

    Returns:
        Dict mapping function names to callables
    """
    return {
        "tools": tools,
        "packs": packs,
        "server": server,
        "servers": servers,
        "aliases": aliases,
        "snippets": snippets,
        "skills": skills,
        "config": config,
        "debug": debug,
        "health": health,
        "help": help,
        "result": result,
        "security": security,
        "stats": stats,
        "notify": notify,
        "reload": reload,
        "version": version,
    }
