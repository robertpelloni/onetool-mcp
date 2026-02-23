"""Persistent memory for AI agents with SQLite storage and optional OpenAI embeddings.

Provides topic-based memory storage with semantic search, content dedup,
secret redaction, and importance decay. Requires OPENAI_API_KEY in secrets.yaml
when embeddings are enabled.

Thread safety: Uses a shared SQLite connection with WAL mode. Concurrent calls
from multiple threads should use _use_connection() to hold the lock for the
full operation. MCP tool dispatch is single-threaded so this is safe in normal
usage.
"""
from __future__ import annotations

# Pack for dot notation: mem.write(), mem.search(), etc.
pack = "mem"

__all__ = [
    "VALID_CATEGORIES",
    "_TOKEN_SAFETY_MARGIN",
    "Config",
    "_build_toc",
    "_cache_get",
    "_cache_invalidate",
    "_cache_put",
    "_check_staleness",
    "_chunk_text_by_tokens",
    "_close_connection",
    "_content_hash",
    "_decode_sections",
    "_deserialize_meta",
    "_encode_sections",
    "_export_yaml",
    "_generate_embedding",
    "_get_connection",
    "_get_openai_client",
    "_maybe_embed",
    "_parse_headings",
    "_read_cache",
    "_read_cache_lock",
    "_redact",
    "_resolve_line_range",
    "_serialize_meta",
    "_topic_filter",
    "_validate_category",
    "_validate_tags",
    "append",
    "cache_clear",
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

from .cache import (
    _cache_get,
    _cache_invalidate,
    _cache_put,
    _read_cache,
    _read_cache_lock,
    cache_clear,
)
from .config import VALID_CATEGORIES, Config

# Private functions re-exported for testing
from .content import (
    _build_toc,
    _check_staleness,
    _content_hash,
    _decode_sections,
    _encode_sections,
    _parse_headings,
    _redact,
    _topic_filter,
    _validate_category,
    _validate_tags,
)
from .db import (
    _close_connection,
    _deserialize_meta,
    _get_connection,
    _serialize_meta,
)
from .embedding import (
    _TOKEN_SAFETY_MARGIN,
    _chunk_text_by_tokens,
    _generate_embedding,
    _get_openai_client,
    _maybe_embed,
)
from .formatting import stale
from .io import _export_yaml, export, load
from .lifecycle import decay, embed, flush, stats
from .listing import count, list
from .maintenance import context, update_batch
from .mutations import append, delete, update
from .read import read, read_batch
from .refresh import refresh
from .search import grep, search
from .slicing import _resolve_line_range, slice, slice_batch, toc
from .snapshots import restore, snap
from .write import write, write_batch
