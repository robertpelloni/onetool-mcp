"""Persistent memory for AI agents with SQLite storage and optional OpenAI embeddings.

Provides topic-based memory storage with semantic search, content dedup,
secret redaction, and importance decay. Requires OPENAI_API_KEY in secrets.yaml
when embeddings are enabled.
"""

from __future__ import annotations

# Pack for dot notation: mem.write(), mem.search(), etc.
pack = "mem"

# Only public functions are exposed as MCP tools.
__all__ = [
    "append",
    "context",
    "count",
    "decay",
    "delete",
    "embed",
    "export",
    "flush",
    "grep",
    "list",
    "load",
    "read",
    "read_batch",
    "refresh",
    "restore",
    "search",
    "slice",
    "slice_batch",
    "snap",
    "stale",
    "stats",
    "toc",
    "update",
    "update_batch",
    "write",
    "write_batch",
]

# Dependency declarations for CLI validation
__ot_requires__ = {
    "lib": [
        ("openai", "pip install openai"),
        ("tiktoken", "pip install tiktoken"),
    ],
    # API key checked at runtime when embeddings enabled (not pack-level requirement)
}

from otutil.tools._mem import (
    append,
    context,
    count,
    decay,
    delete,
    embed,
    export,
    flush,
    grep,
    list,
    load,
    read,
    read_batch,
    refresh,
    restore,
    search,
    slice,
    slice_batch,
    snap,
    stale,
    stats,
    toc,
    update,
    update_batch,
    write,
    write_batch,
)
