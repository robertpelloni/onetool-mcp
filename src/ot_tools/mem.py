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

import builtins
import contextlib
import hashlib
import json
import logging
import math
import queue
import re
import sqlite3
import struct
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Pack for dot notation: mem.write(), mem.search(), etc.
pack = "mem"

__all__ = [
    "append",
    "cache_clear",
    "context",
    "count",
    "decay",
    "delete",
    "embed",
    "export",
    "flush",
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

from pydantic import BaseModel, Field

from ot.config import get_tool_config
from ot.config.secrets import get_secret
from ot.logging import LogSpan
from ot.utils.pathsec import DEFAULT_EXCLUDE_PATTERNS, validate_path

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import ModuleType

    from openai import OpenAI

# Alias to avoid conflict with the module-level list() function
_builtins_list = builtins.list

logger = logging.getLogger(__name__)

# Thread lock for connection operations
_connection_lock = threading.RLock()
_connection: Any = None

# Read cache: key = (topic or id) -> (content_row_tuple, timestamp)
_read_cache: dict[str, tuple[Any, float]] = {}
_read_cache_lock = threading.Lock()

# Valid categories for memories
VALID_CATEGORIES = {"rule", "context", "decision", "mistake", "discovery", "note"}

# Built-in redaction patterns for secrets/PII
_BUILTIN_REDACTION_PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,}", "[REDACTED:api_key]"),
    (r"ghp_[a-zA-Z0-9]{36,}", "[REDACTED:github_token]"),
    (r"gho_[a-zA-Z0-9]{36,}", "[REDACTED:github_token]"),
    (r"github_pat_[a-zA-Z0-9_]{22,}", "[REDACTED:github_token]"),
    (r"xoxb-[a-zA-Z0-9\-]+", "[REDACTED:slack_token]"),
    (r"xoxp-[a-zA-Z0-9\-]+", "[REDACTED:slack_token]"),
    (r"AKIA[0-9A-Z]{16}", "[REDACTED:aws_key]"),
    (r"(?i)password\s*[=:]\s*\S+", "[REDACTED:password]"),
    (r"(?i)(?:api[_-]?key|token|secret)\s*[=:]\s*['\"]?[a-zA-Z0-9_\-]{16,}['\"]?", "[REDACTED:secret]"),
    (r"(?i)(?:postgres|mysql|mongodb|redis)://\S+:\S+@\S+", "[REDACTED:connection_string]"),
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    db_path: str = Field(
        default="mem.db",
        description="Path to memory SQLite database (relative to .onetool/)",
    )
    model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model",
    )
    base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenAI-compatible API base URL for embeddings",
    )
    dimensions: int = Field(
        default=1536,
        description="Embedding dimensions (must match model)",
    )
    search_limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Default maximum search results",
    )
    search_extract: int = Field(
        default=200,
        ge=0,
        description="Character limit for content extract in search results (0 = full content)",
    )
    redaction_enabled: bool = Field(
        default=True,
        description="Enable secret/PII redaction on write",
    )
    redaction_patterns: list[str] = Field(
        default_factory=list,
        description="Additional regex patterns for redaction (beyond built-in defaults)",
    )
    tags_whitelist: list[str] = Field(
        default_factory=list,
        description="Allowed tag prefixes (empty = no restriction). Supports wildcard: 'project/*'",
    )
    decay_half_life_days: int = Field(
        default=30,
        ge=1,
        description="Half-life in days for importance decay",
    )
    allowed_file_dirs: list[str] = Field(
        default_factory=list,
        description="Allowed directories for file read/write (empty = cwd only)",
    )
    exclude_file_patterns: list[str] = Field(
        default_factory=lambda: DEFAULT_EXCLUDE_PATTERNS.copy(),
        description="Path patterns to exclude from file operations",
    )
    max_embedding_tokens: int = Field(
        default=8191,
        ge=1,
        description="Max tokens for embedding input (text-embedding-3-small limit: 8191)",
    )
    read_cache_max_size: int = Field(
        default=128,
        ge=0,
        description="Max entries in read cache (0 = disabled)",
    )
    read_cache_ttl_seconds: int = Field(
        default=300,
        ge=0,
        description="Read cache TTL in seconds (0 = no expiry)",
    )
    embeddings_enabled: bool = Field(
        default=False,
        description="Enable embedding generation for semantic search (requires OPENAI_API_KEY)",
    )
    embeddings_async: bool = Field(
        default=True,
        description="Generate embeddings asynchronously (write returns immediately)",
    )


def _get_config() -> Config:
    """Get mem pack configuration."""
    return get_tool_config("mem", Config)


def _validate_file_path(
    path: str, *, must_exist: bool = True
) -> tuple[Path | None, str | None]:
    """Validate path for mem tool file operations."""
    cfg = _get_config()
    return validate_path(
        path,
        must_exist=must_exist,
        allowed_dirs=cfg.allowed_file_dirs or None,
        exclude_patterns=cfg.exclude_file_patterns,
    )


# ---------------------------------------------------------------------------
# Read cache
# ---------------------------------------------------------------------------


def _cache_get(key: str) -> Any | None:
    """Get a cached read result, or None if missing/expired."""
    config = _get_config()
    if config.read_cache_max_size == 0:
        return None
    with _read_cache_lock:
        entry = _read_cache.get(key)
        if entry is None:
            return None
        row, ts = entry
        if config.read_cache_ttl_seconds > 0 and (time.monotonic() - ts) > config.read_cache_ttl_seconds:
            del _read_cache[key]
            return None
        return row


def _cache_put(key: str, row: Any) -> None:
    """Store a read result in the cache, evicting oldest if full."""
    config = _get_config()
    if config.read_cache_max_size == 0:
        return
    with _read_cache_lock:
        # Evict oldest entries if at capacity (and this is a new key)
        if key not in _read_cache and len(_read_cache) >= config.read_cache_max_size:
            # Remove the oldest entry by timestamp
            oldest_key = min(_read_cache, key=lambda k: _read_cache[k][1])
            del _read_cache[oldest_key]
        _read_cache[key] = (row, time.monotonic())


def _cache_invalidate(topic: str | None = None, id: str | None = None) -> None:
    """Invalidate cache entries matching a topic (prefix) or id."""
    with _read_cache_lock:
        if id:
            # Can't map id back to topic key, so clear entire cache
            _read_cache.clear()
            return
        if topic:
            # Prefix invalidation: remove topic and any children
            keys_to_remove = [
                k
                for k in _read_cache
                if k == f"topic:{topic}" or k.startswith(f"topic:{topic}/")
            ]
            for k in keys_to_remove:
                del _read_cache[k]
            return
        # No filter: clear everything
        _read_cache.clear()


def cache_clear(
    *,
    topic: str | None = None,
) -> str:
    """Clear the in-memory read cache.

    Args:
        topic: Clear only entries under this topic prefix. If omitted, clears the entire cache.

    Returns:
        Confirmation message with number of evicted entries.

    Example:
        mem.cache_clear()
        mem.cache_clear(topic="docs/")
    """
    # Perform count and invalidation under one lock to avoid TOCTOU race.
    # Inline the invalidation logic here instead of calling _cache_invalidate
    # which also acquires _read_cache_lock (non-reentrant).
    with _read_cache_lock:
        before = len(_read_cache)
        if topic:
            keys_to_remove = [
                k for k in _read_cache
                if k == f"topic:{topic}" or k.startswith(f"topic:{topic}/")
            ]
            for k in keys_to_remove:
                del _read_cache[k]
        else:
            _read_cache.clear()
        after = len(_read_cache)
    evicted = before - after
    scope = f"topic '{topic}'" if topic else "all"
    return f"Cache cleared ({scope}): {evicted} entries evicted, {after} remaining"


# ---------------------------------------------------------------------------
# Database connection and schema
# ---------------------------------------------------------------------------


def _get_db_path() -> Path:
    """Get the memory database path, resolving relative to .onetool/ directory.

    Uses resolve_ot_path (not expand_path) so the default "mem.db" resolves
    against project .onetool/ first, then get_global_dir() which honours
    OT_GLOBAL_DIR. See dev/project/guides/configuration.md "Path Resolution".
    """
    from ot.meta import resolve_ot_path

    config = _get_config()
    db_path = resolve_ot_path(config.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def _cosine_similarity(a_blob: bytes | None, b_blob: bytes | None) -> float | None:
    """Cosine similarity between two packed float32 BLOB vectors.

    Registered as a SQLite UDF so it can be used in ORDER BY clauses.
    """
    if a_blob is None or b_blob is None:
        return None
    n = len(a_blob) // 4
    a = struct.unpack(f"<{n}f", a_blob)
    b = struct.unpack(f"<{n}f", b_blob)
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _get_connection() -> sqlite3.Connection:
    """Get or create a read-write SQLite connection with WAL mode.

    Uses a module-level connection with thread lock for safety.
    """
    global _connection
    with _connection_lock:
        if _connection is not None:
            try:
                _connection.execute("SELECT 1").fetchone()
                return _connection
            except Exception:
                _connection = None

        db_path = _get_db_path()
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        # Register cosine similarity UDF
        conn.create_function("cosine_similarity", 2, _cosine_similarity)

        _connection = conn
        _ensure_tables(_connection)
        return _connection


@contextlib.contextmanager
def _use_connection() -> Generator[Any, None, None]:
    """Context manager that holds the connection lock for the entire operation.

    Ensures thread-safe access to the shared SQLite connection.
    """
    conn = _get_connection()
    with _connection_lock:
        yield conn


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check if a column exists in a SQLite table."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Create memory tables if they don't exist, then apply migrations."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id             TEXT PRIMARY KEY,
            topic          TEXT NOT NULL,
            content        TEXT NOT NULL,
            content_hash   TEXT NOT NULL,
            category       TEXT DEFAULT 'note',
            tags           TEXT DEFAULT '[]',
            relevance      INTEGER DEFAULT 5,
            access_count   INTEGER DEFAULT 0,
            created_at     TEXT DEFAULT (datetime('now')),
            updated_at     TEXT DEFAULT (datetime('now')),
            last_accessed  TEXT DEFAULT (datetime('now')),
            embedding      BLOB,
            meta           TEXT DEFAULT '{}'
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_topic ON memories(topic)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_content_hash ON memories(content_hash)
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_history (
            id             TEXT PRIMARY KEY,
            memory_id      TEXT NOT NULL,
            content        TEXT NOT NULL,
            updated_at     TEXT DEFAULT (datetime('now'))
        )
    """)

    _migrate_tables(conn)


def _migrate_tables(conn: sqlite3.Connection) -> None:
    """Apply schema migrations to existing tables.

    Each migration checks before applying so it is safe to call repeatedly.
    """
    # v2: add meta column for extensible key-value metadata
    if not _has_column(conn, "memories", "meta"):
        conn.execute("ALTER TABLE memories ADD COLUMN meta TEXT DEFAULT '{}'")
    conn.commit()


def _close_connection() -> None:
    """Close the module-level connection (for testing)."""
    global _connection
    with _connection_lock:
        if _connection is not None:
            with contextlib.suppress(Exception):
                _connection.close()
            _connection = None


# ---------------------------------------------------------------------------
# Serialisation helpers for SQLite columns
# ---------------------------------------------------------------------------


def _serialize_embedding(vec: list[float] | None) -> bytes | None:
    """Pack a float list into a BLOB for SQLite storage."""
    if vec is None:
        return None
    return struct.pack(f"<{len(vec)}f", *vec)


def _deserialize_embedding(blob: bytes | None) -> list[float] | None:
    """Unpack a BLOB back to a float list."""
    if blob is None:
        return None
    n = len(blob) // 4
    return _builtins_list(struct.unpack(f"<{n}f", blob))


def _serialize_tags(tags: list[str] | None) -> str:
    """Serialize tag list to JSON string."""
    return json.dumps(tags or [])


def _deserialize_tags(raw: str | None) -> list[str]:
    """Deserialize JSON string back to tag list."""
    if not raw:
        return []
    return json.loads(raw)


def _serialize_meta(meta: dict[str, str] | None) -> str:
    """Serialize meta dict to JSON string."""
    return json.dumps(meta or {})


def _deserialize_meta(raw: str | None) -> dict[str, str]:
    """Deserialize JSON string back to meta dict."""
    if not raw:
        return {}
    return json.loads(raw)


# ---------------------------------------------------------------------------
# OpenAI embedding helpers
# ---------------------------------------------------------------------------


def _get_openai_client() -> OpenAI:
    """Get OpenAI client for embedding generation."""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError(
            "openai is required for mem. Install with: pip install openai"
        ) from e

    api_key = get_secret("OPENAI_API_KEY") or ""
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY not configured in secrets.yaml (required for memory embeddings)"
        )
    config = _get_config()
    return OpenAI(api_key=api_key, base_url=config.base_url or None)


def _import_tiktoken() -> ModuleType:
    """Lazy import tiktoken module."""
    try:
        import tiktoken
    except ImportError as e:
        raise ImportError(
            "tiktoken is required for mem embedding truncation. Install with: pip install tiktoken"
        ) from e
    return tiktoken


# Safety margin subtracted from token limit to avoid edge-case overflows.
# Standard safety margin for embedding token limits.
_TOKEN_SAFETY_MARGIN = 100


def _get_tiktoken_encoding(model: str) -> Any:
    """Get tiktoken encoding for a model, with fallback."""
    tiktoken = _import_tiktoken()
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def _chunk_text_by_tokens(text: str, max_tokens: int, model: str) -> list[str]:
    """Split text into chunks that each fit within the token limit.

    Returns a list of text chunks. If the text fits in one chunk, returns [text].
    """
    encoding = _get_tiktoken_encoding(model)
    tokens = encoding.encode(text)

    if len(tokens) <= max_tokens:
        return [text]

    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk_tokens = tokens[i : i + max_tokens]
        chunks.append(encoding.decode(chunk_tokens))
    return chunks


def _generate_embedding(text: str) -> list[float]:
    """Generate embedding vector for text.

    If text exceeds the token limit, splits into chunks, embeds each,
    and returns the averaged vector. This preserves semantic coverage
    of the full document rather than silently losing the tail.
    """
    config = _get_config()
    effective_limit = max(1, config.max_embedding_tokens - _TOKEN_SAFETY_MARGIN)
    chunks = _chunk_text_by_tokens(text, effective_limit, config.model)

    with LogSpan(
        span="mem.embedding",
        model=config.model,
        textLen=len(text),
        chunks=len(chunks),
    ) as span:
        client = _get_openai_client()

        if len(chunks) == 1:
            response = client.embeddings.create(
                model=config.model,
                input=chunks[0],
            )
            span.add("dimensions", len(response.data[0].embedding))
            return response.data[0].embedding

        # Batch embed all chunks in one API call
        response = client.embeddings.create(
            model=config.model,
            input=chunks,
        )
        vectors = [item.embedding for item in response.data]
        dims = len(vectors[0])
        span.add("dimensions", dims)

        # Average the vectors
        averaged = [0.0] * dims
        for vec in vectors:
            for i in range(dims):
                averaged[i] += vec[i]
        n = len(vectors)
        averaged = [v / n for v in averaged]

        return averaged


# ---------------------------------------------------------------------------
# Background embedding worker
# ---------------------------------------------------------------------------

# Bounded queue: stores only memory IDs (not content) to avoid memory bloat.
# maxsize=1000 provides backpressure - enqueue blocks if queue is full.
_embedding_queue: queue.Queue[str] = queue.Queue(maxsize=1000)
_embedding_worker_started = False
_embedding_worker_lock = threading.Lock()
_embedding_errors: int = 0  # Surfaced in mem.stats()


def _enqueue_embedding(memory_id: str) -> None:
    """Queue a memory ID for background embedding generation."""
    _ensure_embedding_worker()
    _embedding_queue.put(memory_id)


def _ensure_embedding_worker() -> None:
    """Start the background embedding worker if not already running."""
    global _embedding_worker_started
    with _embedding_worker_lock:
        if _embedding_worker_started:
            return
        t = threading.Thread(target=_embedding_worker, daemon=True)
        t.start()
        _embedding_worker_started = True


def _embedding_worker() -> None:
    """Background worker: reads content from DB, generates embedding, writes back.

    Re-reads content from DB (not from queue) to avoid holding large strings
    in memory and to pick up any content changes between enqueue and processing.
    Retries up to 3 times with exponential backoff on failure.
    """
    global _embedding_errors
    while True:
        memory_id = _embedding_queue.get()
        retries = 0
        max_retries = 3
        while retries < max_retries:
            try:
                with _use_connection() as conn:
                    row = conn.execute(
                        "SELECT content FROM memories WHERE id = ?", [memory_id]
                    ).fetchone()
                    if not row:
                        break  # Memory was deleted before we got to it
                    embedding = _generate_embedding(row[0])
                    conn.execute(
                        "UPDATE memories SET embedding = ? WHERE id = ?",
                        [_serialize_embedding(embedding), memory_id],
                    )
                    conn.commit()
                break
            except Exception:
                retries += 1
                _embedding_errors += 1
                if retries < max_retries:
                    time.sleep(2**retries)  # 2s, 4s, 8s
                else:
                    logger.warning(
                        "Failed embedding for %s after %s retries",
                        memory_id,
                        max_retries,
                        exc_info=True,
                    )
        _embedding_queue.task_done()


def _maybe_embed(memory_id: str, content: str) -> list[float] | None:
    """Generate embedding if enabled, async or sync per config. Returns None if skipped/async."""
    config = _get_config()
    if not config.embeddings_enabled:
        return None
    if config.embeddings_async:
        _enqueue_embedding(memory_id)
        return None
    return _generate_embedding(content)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _content_hash(content: str) -> str:
    """Generate SHA-256 hash of content for dedup."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _topic_filter(topic: str | None) -> tuple[str, list[Any]]:
    """Build SQL WHERE clause for topic filtering.

    Supports exact match and prefix matching with trailing /.
    Returns (sql_fragment, params).
    """
    if not topic:
        return "", []

    if topic.endswith("/"):
        return " AND (topic = ? OR topic LIKE ?)", [topic.rstrip("/"), topic + "%"]
    elif "*" in topic:
        like_pattern = topic.replace("*", "%")
        return " AND topic LIKE ?", [like_pattern]
    else:
        return " AND topic = ?", [topic]


def _tags_filter_sql(tags: list[str]) -> tuple[str, list[str]]:
    """Build SQL WHERE clause fragment for tag filtering.

    Tags are stored as a JSON array in a TEXT column. Uses json_each() to
    check if any of the provided tags exist in the stored array.
    Returns (sql_fragment, params).
    """
    placeholders = ", ".join("?" for _ in tags)
    sql = f" AND EXISTS (SELECT 1 FROM json_each(tags) WHERE json_each.value IN ({placeholders}))"
    return sql, tags


def _redact(content: str) -> str:
    """Redact secrets and PII from content.

    Uses built-in patterns plus any additional patterns from config.
    """
    config = _get_config()
    if not config.redaction_enabled:
        return content

    result = content
    for pattern, replacement in _BUILTIN_REDACTION_PATTERNS:
        result = re.sub(pattern, replacement, result)

    for pattern in config.redaction_patterns:
        try:
            result = re.sub(pattern, "[REDACTED]", result)
        except re.error:
            logger.warning("Invalid redaction pattern: %s", pattern)

    return result


def _validate_tags(tags: list[str] | None) -> list[str]:
    """Validate tags against whitelist if configured.

    Returns validated tags or raises ValueError.
    """
    if not tags:
        return []

    config = _get_config()
    if not config.tags_whitelist:
        return tags

    validated = []
    for tag in tags:
        allowed = False
        for prefix in config.tags_whitelist:
            if prefix.endswith("/*"):
                if tag.startswith(prefix[:-1]) or tag == prefix[:-2]:
                    allowed = True
                    break
            elif tag == prefix:
                allowed = True
                break
        if not allowed:
            raise ValueError(
                f"Tag '{tag}' not in whitelist. Allowed: {config.tags_whitelist}"
            )
        validated.append(tag)
    return validated


def _validate_category(category: str) -> str:
    """Validate category value."""
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category '{category}'. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )
    return category


# ---------------------------------------------------------------------------
# Markdown heading parser and section index
# ---------------------------------------------------------------------------

# Matches ATX headings: # Heading, ## Heading, etc.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


def _parse_headings(content: str, *, max_depth: int = 3) -> list[dict[str, Any]]:
    """Parse markdown headings and compute line ranges for each section.

    Returns a list of dicts with keys: heading, level, start, end.
    Lines are 1-indexed. ``end`` is inclusive and points to the last line
    of the section (the line before the next heading or EOF).
    """
    lines = content.split("\n")
    headings: list[dict[str, Any]] = []

    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line)
        if m and len(m.group(1)) <= max_depth:
            headings.append({
                "heading": m.group(2).strip(),
                "level": len(m.group(1)),
                "start": i + 1,  # 1-indexed
                "end": len(lines),  # will be adjusted below
            })

    # Adjust end lines: each section ends just before the next heading
    for idx in range(len(headings) - 1):
        headings[idx]["end"] = headings[idx + 1]["start"] - 1

    return headings


def _encode_sections(headings: list[dict[str, Any]]) -> str:
    """Encode parsed headings into pipe-delimited section index string.

    Format: ``heading:start-end|heading:start-end``

    Pipes in headings are escaped as ``\\|`` to avoid splitting ambiguity.
    """
    parts = []
    for h in headings:
        escaped = h["heading"].replace("\\", "\\\\").replace("|", "\\|")
        parts.append(f"{escaped}:{h['start']}-{h['end']}")
    return "|".join(parts)


def _decode_sections(encoded: str) -> list[dict[str, Any]]:
    """Decode pipe-delimited section index string back to heading dicts.

    Handles escaped pipes (``\\|``) in headings.
    """
    if not encoded:
        return []
    # Split on unescaped pipes: split on | that is not preceded by \
    # We use a two-pass approach: replace escaped pipes with a placeholder,
    # split, then restore.
    placeholder = "\x00"
    safe = encoded.replace("\\|", placeholder)
    sections = []
    for part in safe.split("|"):
        part = part.replace(placeholder, "|")
        # Split on last colon to handle headings containing colons
        colon_idx = part.rfind(":")
        if colon_idx == -1:
            continue
        heading = part[:colon_idx].replace("\\\\", "\\")
        range_str = part[colon_idx + 1:]
        dash_idx = range_str.find("-")
        if dash_idx == -1:
            continue
        try:
            start = int(range_str[:dash_idx])
            end = int(range_str[dash_idx + 1:])
        except ValueError:
            continue
        sections.append({"heading": heading, "start": start, "end": end})
    return sections


def _build_toc(sections: list[dict[str, Any]], content: str) -> str:
    """Build a human-readable table of contents from section data."""
    if not sections:
        return "No sections found"
    total_lines = len(content.split("\n"))
    lines = [f"Table of Contents ({len(sections)} sections, {total_lines} lines)\n"]
    for i, sec in enumerate(sections, 1):
        lines.append(f"  {i}. {sec['heading']} (lines {sec['start']}-{sec['end']})")
    return "\n".join(lines)


def _check_staleness(meta: dict[str, str]) -> str:
    """Check staleness of a file-backed memory.

    Returns one of: "fresh", "stale", "missing", "skipped".
    """
    source = meta.get("source")
    source_mtime = meta.get("source_mtime")
    if not source or not source_mtime:
        return "skipped"
    source_path = Path(source)
    if not source_path.exists():
        return "missing"
    current_mtime = source_path.stat().st_mtime
    if current_mtime > float(source_mtime):
        return "stale"
    return "fresh"


# ---------------------------------------------------------------------------
# Phase 1 - Foundation: CRUD operations
# ---------------------------------------------------------------------------


def write(
    *,
    topic: str,
    content: str | None = None,
    category: str = "note",
    tags: list[str] | None = None,
    relevance: int = 5,
    file: str | None = None,
    toc: bool = False,
) -> str:
    """Store a memory with topic, content, and optional metadata.

    Content is deduplicated by SHA-256 hash within the same topic.
    Secrets and PII are automatically redacted before storage.

    Provide exactly one of content or file.

    Args:
        topic: Topic path using / separator (e.g., "projects/onetool/rules")
        content: Memory content text
        category: One of: rule, context, decision, mistake, discovery, note
        tags: Optional list of tags for categorisation
        relevance: Importance score 1-10 (default: 5)
        file: Path to file to read content from (mutually exclusive with content)
        toc: If True, parse markdown headings and store section index in meta

    Returns:
        Confirmation message with memory ID, or error message.

    Example:
        mem.write(topic="projects/onetool/rules", content="Always use keyword-only args")
        mem.write(topic="learnings/python", content="Use __future__ annotations", category="discovery")
        mem.write(topic="config", file="~/.onetool/config/onetool.yaml")
        mem.write(topic="spec", file="spec.md", toc=True)
    """
    with LogSpan(span="mem.write", topic=topic, category=category) as s:
        try:
            if content is not None and file is not None:
                return "Error: Provide content or file, not both"
            if content is None and file is None:
                return "Error: Provide content or file"

            _validate_category(category)
            if not 1 <= relevance <= 10:
                return "Error: relevance must be between 1 and 10"
            validated_tags = _validate_tags(tags)

            meta: dict[str, str] = {}
            validated_path: Path | None = None

            if file:
                validated_path, error = _validate_file_path(file, must_exist=True)
                if error:
                    s.add("error", "path_validation")
                    return f"Error: {error}"
                assert validated_path is not None
                file_stat = validated_path.stat()
                if file_stat.st_size > 1_000_000:
                    s.add("error", "file_too_large")
                    return f"Error: File too large ({file_stat.st_size / 1_000_000:.1f}MB). Max 1MB for memory content."
                content = validated_path.read_text(encoding="utf-8")

                # Auto-populate file metadata
                meta["source"] = str(validated_path.resolve())
                meta["source_mtime"] = str(file_stat.st_mtime)
                meta["content_type"] = validated_path.suffix.lstrip(".") or "txt"

            assert content is not None  # guaranteed by file read or early return
            content = _redact(content)
            content_hash = _content_hash(content)

            # Parse TOC if requested
            if toc:
                headings = _parse_headings(content)
                if headings:
                    meta["sections"] = _encode_sections(headings)
                    meta["section_count"] = str(len(headings))

            conn = _get_connection()

            # Check for duplicate content in same topic
            existing = conn.execute(
                "SELECT id FROM memories WHERE topic = ? AND content_hash = ?",
                [topic, content_hash],
            ).fetchone()

            if existing:
                s.add("duplicate", True)
                return f"Duplicate: Memory with same content already exists in topic '{topic}' (id: {existing[0]})"

            memory_id = str(uuid.uuid4())
            embedding = _maybe_embed(memory_id, content)

            conn.execute(
                """
                INSERT INTO memories (id, topic, content, content_hash, category, tags, relevance, embedding, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [memory_id, topic, content, content_hash, category,
                 _serialize_tags(validated_tags), relevance,
                 _serialize_embedding(embedding), _serialize_meta(meta)],
            )
            conn.commit()

            s.add("memoryId", memory_id)
            s.add("contentLen", len(content))
            _cache_invalidate(topic=topic)
            toc_msg = f" (toc: {meta.get('section_count', '0')} sections)" if toc else ""
            return f"Stored memory {memory_id} in topic '{topic}'{toc_msg}"

        except ValueError as e:
            s.add("error", "validation")
            return f"Error: {e}"
        except Exception as e:
            s.add("error", str(e))
            return f"Error writing memory: {e}"


def write_batch(
    *,
    topic: str,
    glob_pattern: str,
    category: str = "note",
    tags: list[str] | None = None,
    relevance: int = 5,
    toc: bool = False,
) -> str:
    """Store multiple memories from files matching a glob pattern.

    Each file becomes a separate memory under the given topic,
    preserving the directory structure relative to the glob root.

    Args:
        topic: Base topic path (relative file path appended as subtopic)
        glob_pattern: Glob pattern to match files (e.g., "docs/**/*.md")
        category: Category for all memories
        tags: Tags applied to all memories
        relevance: Relevance score for all memories
        toc: If True, parse markdown headings and store section index per file

    Returns:
        Summary of stored memories.

    Example:
        mem.write_batch(topic="docs", glob_pattern="docs/**/*.md", category="context")
        mem.write_batch(topic="specs", glob_pattern="specs/**/*.md", toc=True)
    """
    from ot.paths import get_effective_cwd

    with LogSpan(span="mem.write_batch", topic=topic, glob=glob_pattern) as s:
        try:
            _validate_category(category)

            base = get_effective_cwd()
            files = sorted(base.glob(glob_pattern))

            if not files:
                s.add("fileCount", 0)
                return f"No files matched pattern: {glob_pattern}"

            # Determine glob root: the non-wildcard prefix of the pattern
            glob_root = base
            for part in Path(glob_pattern).parts:
                if any(c in part for c in ("*", "?", "[")):
                    break
                glob_root = glob_root / part

            stored = 0
            skipped = 0
            errors = []

            for f in files:
                if not f.is_file():
                    continue

                # Preserve directory structure relative to glob root
                rel = f.relative_to(glob_root)
                subtopic = f"{topic}/{rel.as_posix()}"
                result = write(
                    topic=subtopic,
                    file=str(f),
                    category=category,
                    tags=tags,
                    relevance=relevance,
                    toc=toc,
                )
                if result.startswith("Stored"):
                    stored += 1
                elif result.startswith("Duplicate"):
                    skipped += 1
                else:
                    errors.append(f"{f.name}: {result}")

            s.add("stored", stored)
            s.add("skipped", skipped)
            s.add("errors", len(errors))

            parts = [f"Processed {stored + skipped + len(errors)} files: {stored} stored, {skipped} duplicates"]
            if errors:
                parts.append(f", {len(errors)} errors")
                for err in errors[:5]:
                    parts.append(f"\n  - {err}")
            return "".join(parts)

        except ValueError as e:
            s.add("error", "validation")
            return f"Error: {e}"
        except Exception as e:
            s.add("error", str(e))
            return f"Error in batch write: {e}"


_READ_COLUMNS = "id, topic, content, category, tags, relevance, access_count, created_at, updated_at, meta"
_VALID_READ_MODES = {"content", "toc", "meta", "all"}


def read(
    *,
    topic: str,
    id: str | None = None,
    meta: bool = False,
    mode: str = "content",
) -> str:
    """Read a memory by exact topic match or ID.

    Increments the access count on each read.

    Args:
        topic: Exact topic path to read
        id: Optional memory ID for direct lookup (overrides topic match)
        meta: If True, include metadata header (topic, category, tags, etc.)
        mode: Output mode - "content" (default), "toc" (section index), "meta" (metadata only), "all"

    Returns:
        Memory content (with metadata header if meta=True), or error if not found.

    Example:
        mem.read(topic="projects/onetool/rules")
        mem.read(topic="projects/onetool/rules", meta=True)
        mem.read(topic="spec", mode="toc")
        mem.read(id="abc-123-def")
    """
    if mode not in _VALID_READ_MODES:
        return f"Error: Invalid mode '{mode}'. Must be one of: {', '.join(sorted(_VALID_READ_MODES))}"

    with LogSpan(span="mem.read", topic=topic, mode=mode) as s:
        try:
            cache_key = f"id:{id}" if id else f"topic:{topic}"
            cached_row = _cache_get(cache_key)

            if cached_row is not None:
                row = cached_row
                s.add("cache", "hit")
            else:
                conn = _get_connection()

                if id:
                    row = conn.execute(
                        f"SELECT {_READ_COLUMNS} FROM memories WHERE id = ?",
                        [id],
                    ).fetchone()
                else:
                    row = conn.execute(
                        f"SELECT {_READ_COLUMNS} FROM memories WHERE topic = ?",
                        [topic],
                    ).fetchone()

                if not row:
                    s.add("found", False)
                    return f"No memory found for topic '{topic}'" if not id else f"No memory found with id '{id}'"

                _cache_put(cache_key, row)
                s.add("cache", "miss")

            # Increment access count (always, even on cache hit)
            conn = _get_connection()
            conn.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id = ?",
                [row[0]],
            )
            conn.commit()

            # Update row with incremented access_count for accurate display
            row = (*row[:6], row[6] + 1, *row[7:])
            _cache_put(cache_key, row)

            s.add("found", True)
            s.add("memoryId", row[0])

            # row indices: 0=id, 1=topic, 2=content, 3=category, 4=tags,
            #              5=relevance, 6=access_count, 7=created_at, 8=updated_at, 9=meta
            return _format_read_row(row, meta=meta, mode=mode)

        except Exception as e:
            s.add("error", str(e))
            return f"Error reading memory: {e}"


def _format_read_row(row: Any, *, meta: bool, mode: str) -> str:
    """Format a single memory row according to mode and meta flags.

    Row indices: 0=id, 1=topic, 2=content, 3=category, 4=tags,
                 5=relevance, 6=access_count, 7=created_at, 8=updated_at, 9=meta
    """
    tags = _deserialize_tags(row[4])
    row_meta = _deserialize_meta(row[9])

    if mode == "meta":
        lines = [
            f"Topic: {row[1]}",
            f"Category: {row[3]}",
            f"Tags: {', '.join(tags) if tags else 'none'}",
            f"Relevance: {row[5]}",
            f"Accessed: {row[6]} times",
            f"Created: {row[7]}",
            f"Updated: {row[8]}",
            f"ID: {row[0]}",
        ]
        if row_meta:
            lines.append("Meta:")
            for k, v in sorted(row_meta.items()):
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    if mode == "toc":
        sections = _decode_sections(row_meta.get("sections", ""))
        return _build_toc(sections, row[2])

    # mode == "content" or "all"
    content = row[2]
    if not meta and mode == "content":
        return content

    header = (
        f"Topic: {row[1]}\n"
        f"Category: {row[3]}\n"
        f"Tags: {', '.join(tags) if tags else 'none'}\n"
        f"Relevance: {row[5]}\n"
        f"Accessed: {row[6]} times\n"
        f"Created: {row[7]}\n"
        f"Updated: {row[8]}\n"
        f"ID: {row[0]}"
    )
    if row_meta and mode == "all":
        meta_lines = [f"  {k}: {v}" for k, v in sorted(row_meta.items())]
        header += "\nMeta:\n" + "\n".join(meta_lines)

    return f"{header}\n\n{content}"


def read_batch(
    *,
    topic: str | None = None,
    ids: list[str] | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    meta: bool = False,
    mode: str = "content",
    limit: int = 50,
) -> str:
    """Read multiple memories by topic prefix, IDs, category, or tags.

    Returns full content for each matching memory. At least one filter
    (topic, ids, category, or tags) must be provided.

    Args:
        topic: Topic prefix filter (e.g., "projects/" matches all under projects)
        ids: List of specific memory IDs to read
        category: Category filter
        tags: Tag filter (matches memories with any of these tags)
        meta: If True, include metadata header per memory
        mode: Output mode - "content" (default), "toc" (section index), "meta" (metadata only), "all"
        limit: Maximum results (default: 50)

    Returns:
        Concatenated memory contents separated by dividers, or error.

    Example:
        mem.read_batch(topic="projects/onetool/agents/")
        mem.read_batch(ids=["abc-123", "def-456"], meta=True)
        mem.read_batch(category="rule", limit=10)
        mem.read_batch(topic="specs/", mode="toc")
    """
    if mode not in _VALID_READ_MODES:
        return f"Error: Invalid mode '{mode}'. Must be one of: {', '.join(sorted(_VALID_READ_MODES))}"

    if not any([topic, ids, category, tags]):
        return "Error: At least one filter (topic, ids, category, or tags) is required"

    if ids and any([topic, category, tags]):
        return "Error: ids cannot be combined with other filters (topic, category, tags)"

    with LogSpan(span="mem.read_batch", topic=topic, mode=mode, limit=limit) as s:
        try:
            conn = _get_connection()

            if ids:
                placeholders = ", ".join("?" for _ in ids)
                sql = f"SELECT {_READ_COLUMNS} FROM memories WHERE id IN ({placeholders})"
                params: _builtins_list[Any] = _builtins_list(ids)
            else:
                sql = f"SELECT {_READ_COLUMNS} FROM memories WHERE 1=1"
                params = []

                topic_sql, topic_params = _topic_filter(topic)
                sql += topic_sql
                params.extend(topic_params)

                if category:
                    sql += " AND category = ?"
                    params.append(category)

                if tags:
                    tags_sql, tags_params = _tags_filter_sql(tags)
                    sql += tags_sql
                    params.extend(tags_params)

            sql += " ORDER BY topic ASC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()

            if not rows:
                s.add("found", 0)
                return "No memories found matching filters"

            # Increment access counts
            row_ids = [r[0] for r in rows]
            placeholders = ", ".join("?" for _ in row_ids)
            conn.execute(
                f"UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id IN ({placeholders})",
                row_ids,
            )
            conn.commit()

            s.add("found", len(rows))

            parts = []
            for row in rows:
                formatted = _format_read_row(row, meta=meta, mode=mode)
                if mode == "content" and not meta:
                    parts.append(f"# {row[1]}\n\n{formatted}")
                else:
                    parts.append(formatted)

            noun = "memory" if len(rows) == 1 else "memories"
            return f"Read {len(rows)} {noun}\n\n---\n\n" + "\n\n---\n\n".join(parts)

        except Exception as e:
            s.add("error", str(e))
            return f"Error reading memories: {e}"


# Line range regex: matches patterns like ":50", "400:", "151:200", "-50:"
_LINE_RANGE_RE = re.compile(r"^-?\d*:\d*$")


def toc(
    *,
    topic: str,
    id: str | None = None,
) -> str:
    """Display a numbered section index for a memory with table of contents.

    Checks source file staleness when source metadata is available.

    Args:
        topic: Topic of the memory
        id: Optional memory ID (overrides topic)

    Returns:
        Numbered section index with line ranges, or error.

    Example:
        mem.toc(topic="spec")
        mem.toc(id="abc-123")
    """
    with LogSpan(span="mem.toc", topic=topic) as s:
        try:
            conn = _get_connection()

            if id:
                row = conn.execute(
                    f"SELECT {_READ_COLUMNS} FROM memories WHERE id = ?", [id]
                ).fetchone()
            else:
                row = conn.execute(
                    f"SELECT {_READ_COLUMNS} FROM memories WHERE topic = ?", [topic]
                ).fetchone()

            if not row:
                s.add("found", False)
                return f"No memory found for topic '{topic}'" if not id else f"No memory found with id '{id}'"

            row_meta = _deserialize_meta(row[9])
            sections = _decode_sections(row_meta.get("sections", ""))
            result = _build_toc(sections, row[2])

            # Staleness detection
            status = _check_staleness(row_meta)
            if status == "stale":
                result += "\n\nWarning: Source file has been modified since this memory was stored. Consider re-writing with mem.write()."
            elif status == "missing":
                result += "\n\nWarning: Source file no longer exists."

            s.add("sections", len(sections))
            return result

        except Exception as e:
            s.add("error", str(e))
            return f"Error reading toc: {e}"


def slice(
    *,
    topic: str,
    select: int | str | list[int | str],
    id: str | None = None,
) -> str:
    """Extract content by section number, heading path, line range, or mixed list.

    Format detection (polymorphic):
    - int: section number (1-indexed)
    - str matching ``-?\\d*:\\d*``: line range (e.g., ":50", "400:", "151:200", "-50:")
    - str otherwise: heading path lookup (case-insensitive substring match)
    - list: apply the above rules to each element

    Args:
        topic: Topic of the memory
        select: Section selector - int, str, or list of mixed
        id: Optional memory ID (overrides topic)

    Returns:
        Extracted content, or error.

    Example:
        mem.slice(topic="spec", select=1)
        mem.slice(topic="spec", select="Requirements")
        mem.slice(topic="spec", select=":50")
        mem.slice(topic="spec", select=[1, "Requirements", "200:300"])
    """
    with LogSpan(span="mem.slice", topic=topic) as s:
        try:
            conn = _get_connection()

            if id:
                row = conn.execute(
                    f"SELECT {_READ_COLUMNS} FROM memories WHERE id = ?", [id]
                ).fetchone()
            else:
                row = conn.execute(
                    f"SELECT {_READ_COLUMNS} FROM memories WHERE topic = ?", [topic]
                ).fetchone()

            if not row:
                s.add("found", False)
                return f"No memory found for topic '{topic}'" if not id else f"No memory found with id '{id}'"

            content = row[2]
            lines = content.split("\n")
            row_meta = _deserialize_meta(row[9])
            sections = _decode_sections(row_meta.get("sections", ""))

            # Normalise select to a sequence
            selectors: _builtins_list[int | str] = select if type(select) is _builtins_list else [select]  # type: ignore[assignment]

            extracted_parts: list[str] = []
            for sel in selectors:
                part = _resolve_slice(sel, lines, sections)
                if part is not None:
                    extracted_parts.append(part)

            if not extracted_parts:
                return "No matching content found for the given selector(s)"

            s.add("parts", len(extracted_parts))
            return "\n\n".join(extracted_parts)

        except Exception as e:
            s.add("error", str(e))
            return f"Error slicing memory: {e}"


def _resolve_slice(
    sel: int | str,
    lines: list[str],
    sections: list[dict[str, Any]],
) -> str | None:
    """Resolve a single slice selector to content."""
    total = len(lines)

    # int: section number (1-indexed)
    if isinstance(sel, int):
        if 1 <= sel <= len(sections):
            sec = sections[sel - 1]
            return "\n".join(lines[sec["start"] - 1 : sec["end"]])
        return None

    # str: check if line range
    if _LINE_RANGE_RE.match(sel):
        return _resolve_line_range(sel, lines, total)

    # str: heading path lookup (case-insensitive substring)
    sel_lower = sel.lower()
    for sec in sections:
        if sel_lower in sec["heading"].lower():
            return "\n".join(lines[sec["start"] - 1 : sec["end"]])
    return None


def _resolve_line_range(spec: str, lines: list[str], total: int) -> str | None:
    """Parse and resolve a line range spec like ':50', '400:', '151:200', '-50:'."""
    parts = spec.split(":")
    start_str, end_str = parts[0], parts[1]

    if start_str == "" and end_str == "":
        return None  # ":" alone is invalid

    # Parse start
    if start_str == "":
        start = 1
    else:
        start = int(start_str)
        if start < 0:
            start = max(1, total + start + 1)

    # Parse end
    end = total if end_str == "" else int(end_str)

    if start < 1:
        start = 1
    if end > total:
        end = total
    if start > end:
        return None

    return "\n".join(lines[start - 1 : end])


def _selector_label(select: int | str | _builtins_list[int | str]) -> str:
    """Build a human-readable label for a slice selector."""
    if isinstance(select, int):
        return f"Section {select}"
    if isinstance(select, str):
        return select
    # list
    parts = []
    for s in select:
        if isinstance(s, int):
            parts.append(f"Section {s}")
        else:
            parts.append(str(s))
    return ", ".join(parts)


def slice_batch(
    *,
    items: list[dict[str, Any]],
) -> str:
    """Extract sections from multiple memories in a single call.

    Each item specifies a memory (by topic or id) and a selector.
    Uses a batch DB query to minimise round-trips.

    Args:
        items: List of dicts, each with 'topic' or 'id' (str) and 'select'
               (int, str, or list). Max 20 items.

    Returns:
        Concatenated sliced content with topic headers and dividers.

    Example:
        mem.slice_batch(items=[
            {"topic": "docs/creating-tools.md", "select": "Checklist"},
            {"topic": "docs/testing.md", "select": "Required Markers"},
            {"topic": "docs/spec-format.md", "select": "Rules"},
        ])
        mem.slice_batch(items=[
            {"topic": "spec.md", "select": [1, "Requirements"]},
            {"id": "abc-123", "select": ":50"},
        ])
    """
    with LogSpan(span="mem.slice_batch", itemCount=len(items) if items else 0) as s:
        try:
            if not items:
                return "Error: items must be a non-empty list"
            if len(items) > 20:
                return f"Error: Maximum 20 items allowed, got {len(items)}"

            # Validate items and collect lookup keys (deduplicated)
            topic_keys_set: set[str] = set()
            id_keys_set: set[str] = set()
            validated: _builtins_list[tuple[dict[str, Any], str | None, str | None]] = []

            for item in items:
                if not isinstance(item, dict):
                    validated.append((item, None, None))
                    continue
                sel = item.get("select")
                topic = item.get("topic")
                mid = item.get("id")
                if sel is None:
                    validated.append((item, None, None))
                    continue
                if not topic and not mid:
                    validated.append((item, None, None))
                    continue
                if topic and mid:
                    validated.append((item, None, None))
                    continue
                if topic:
                    topic_keys_set.add(topic)
                    validated.append((item, topic, None))
                else:
                    id_keys_set.add(mid)  # type: ignore[arg-type]
                    validated.append((item, None, mid))

            # Batch fetch all needed rows
            row_map: dict[str, Any] = {}  # keyed by topic or id
            conn = _get_connection()

            topic_keys = sorted(topic_keys_set)
            id_keys = sorted(id_keys_set)

            if topic_keys or id_keys:
                conditions = []
                params: _builtins_list[Any] = []
                if topic_keys:
                    placeholders = ", ".join("?" for _ in topic_keys)
                    conditions.append(f"topic IN ({placeholders})")
                    params.extend(topic_keys)
                if id_keys:
                    placeholders = ", ".join("?" for _ in id_keys)
                    conditions.append(f"id IN ({placeholders})")
                    params.extend(id_keys)

                sql = f"SELECT {_READ_COLUMNS} FROM memories WHERE {' OR '.join(conditions)}"
                rows = conn.execute(sql, params).fetchall()

                # Index by topic and id
                for row in rows:
                    row_map[f"topic:{row[1]}"] = row
                    row_map[f"id:{row[0]}"] = row

                # Increment access counts
                if rows:
                    row_ids = [r[0] for r in rows]
                    id_placeholders = ", ".join("?" for _ in row_ids)
                    conn.execute(
                        f"UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id IN ({id_placeholders})",
                        row_ids,
                    )
                    conn.commit()

                # Populate cache
                for row in rows:
                    _cache_put(f"topic:{row[1]}", row)

            # Process each item
            result_parts: _builtins_list[str] = []
            sliced_count = 0

            for item, topic, mid in validated:
                # Items with topic=None and mid=None failed validation in the first pass
                sel = item.get("select") if isinstance(item, dict) else None

                if sel is None:
                    label = topic or mid or str(item)
                    result_parts.append(f"# {label}\n\nError: 'select' is required for each item")
                    continue
                if not topic and not mid:
                    result_parts.append("# (invalid item)\n\nError: Each item must have 'topic' or 'id'")
                    continue

                # Look up row
                key = f"topic:{topic}" if topic else f"id:{mid}"
                row = row_map.get(key)
                if not row:
                    label = topic or mid
                    result_parts.append(f"# {label} [{_selector_label(sel)}]\n\nError: No memory found for {'topic' if topic else 'id'} '{label}'")
                    continue

                # Apply selector
                content = row[2]
                lines = content.split("\n")
                row_meta = _deserialize_meta(row[9])
                sections = _decode_sections(row_meta.get("sections", ""))

                selectors: _builtins_list[int | str] = sel if type(sel) is _builtins_list else [sel]  # type: ignore[assignment]
                extracted: _builtins_list[str] = []
                for sel_item in selectors:
                    part = _resolve_slice(sel_item, lines, sections)
                    if part is not None:
                        extracted.append(part)

                display_topic = row[1]  # use actual topic from DB
                sel_label = _selector_label(sel)
                if extracted:
                    result_parts.append(f"# {display_topic} [{sel_label}]\n\n" + "\n\n".join(extracted))
                    sliced_count += 1
                else:
                    result_parts.append(f"# {display_topic} [{sel_label}]\n\nNo matching content found for selector(s)")

            s.add("sliced", sliced_count)
            s.add("total", len(items))
            noun = "memory" if sliced_count == 1 else "memories"
            return f"Sliced {sliced_count} {noun}\n\n---\n\n" + "\n\n---\n\n".join(result_parts)

        except Exception as e:
            s.add("error", str(e))
            return f"Error in slice_batch: {e}"


def search(
    *,
    query: str,
    mode: str = "semantic",
    topic: str | None = None,
    category: str | None = None,
    limit: int | None = None,
    tags: list[str] | None = None,
    extract: int | None = None,
) -> str:
    """Search memories by semantic similarity, pattern matching, or hybrid.

    Args:
        query: Search query text
        mode: Search mode - "semantic" (vector cosine), "pattern" (LIKE), or "hybrid" (RRF)
        topic: Optional topic prefix filter (e.g., "projects/" matches all under projects)
        category: Optional category filter
        limit: Maximum results (default: config search_limit)
        tags: Optional tag filter (matches memories with any of these tags)
        extract: Character limit for content extract (default: config search_extract, 0 = full content)

    Returns:
        Formatted search results with scores.

    Example:
        mem.search(query="authentication patterns")
        mem.search(query="database", mode="pattern", topic="projects/")
        mem.search(query="error handling", mode="hybrid", category="mistake")
        mem.search(query="rules", extract=500)
    """
    config = _get_config()
    if limit is None:
        limit = config.search_limit
    if extract is None:
        extract = config.search_extract

    if mode not in ("semantic", "pattern", "hybrid"):
        return f"Error: Invalid mode '{mode}'. Must be 'semantic', 'pattern', or 'hybrid'"

    with LogSpan(span="mem.search", query=query, mode=mode, topic=topic, limit=limit) as s:
        try:
            if mode in ("semantic", "hybrid") and not config.embeddings_enabled:
                return "Semantic search requires embeddings. Enable with: tools.mem.embeddings_enabled: true"

            conn = _get_connection()

            if mode in ("semantic", "hybrid"):
                has_embeddings = conn.execute(
                    "SELECT 1 FROM memories WHERE embedding IS NOT NULL LIMIT 1"
                ).fetchone()
                if not has_embeddings:
                    return "No embeddings found. Run mem.embed(dry_run=False) to generate them."

            if mode == "semantic":
                results = _search_semantic(conn, query, topic, category, tags, limit)
            elif mode == "pattern":
                results = _search_pattern(conn, query, topic, category, tags, limit)
            else:
                results = _search_hybrid(conn, query, topic, category, tags, limit)

            if not results:
                s.add("resultCount", 0)
                return f"No memories found for: {query}"

            s.add("resultCount", len(results))
            return _format_search_results(results, query, extract)

        except Exception as e:
            s.add("error", str(e))
            return f"Error searching memories: {e}"


def _search_semantic(
    conn: Any,
    query: str,
    topic: str | None,
    category: str | None,
    tags: list[str] | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Semantic search using vector cosine similarity."""
    embedding = _generate_embedding(query)
    query_blob = _serialize_embedding(embedding)

    sql = """
        SELECT id, topic, content, category, tags, relevance, access_count,
               cosine_similarity(embedding, ?) as score
        FROM memories
        WHERE embedding IS NOT NULL
    """
    params: list[Any] = [query_blob]

    topic_sql, topic_params = _topic_filter(topic)
    sql += topic_sql
    params.extend(topic_params)

    if category:
        sql += " AND category = ?"
        params.append(category)

    if tags:
        tags_sql, tags_params = _tags_filter_sql(tags)
        sql += tags_sql
        params.extend(tags_params)

    sql += " ORDER BY score DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "id": r[0], "topic": r[1], "content": r[2], "category": r[3],
            "tags": _deserialize_tags(r[4]), "relevance": r[5], "access_count": r[6],
            "score": round(r[7], 4) if r[7] is not None else 0.0,
        }
        for r in rows
    ]


def _search_pattern(
    conn: Any,
    query: str,
    topic: str | None,
    category: str | None,
    tags: list[str] | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Pattern search using LIKE matching (case-insensitive in SQLite by default)."""
    sql = """
        SELECT id, topic, content, category, tags, relevance, access_count
        FROM memories
        WHERE (content LIKE ? ESCAPE '\\' OR topic LIKE ? ESCAPE '\\')
    """
    # Escape LIKE special characters so they match literally
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like_pattern = f"%{escaped}%"
    params: list[Any] = [like_pattern, like_pattern]

    topic_sql, topic_params = _topic_filter(topic)
    sql += topic_sql
    params.extend(topic_params)

    if category:
        sql += " AND category = ?"
        params.append(category)

    if tags:
        tags_sql, tags_params = _tags_filter_sql(tags)
        sql += tags_sql
        params.extend(tags_params)

    sql += " ORDER BY relevance DESC, updated_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "id": r[0], "topic": r[1], "content": r[2], "category": r[3],
            "tags": _deserialize_tags(r[4]), "relevance": r[5], "access_count": r[6], "score": 1.0,
        }
        for r in rows
    ]


def _search_hybrid(
    conn: Any,
    query: str,
    topic: str | None,
    category: str | None,
    tags: list[str] | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Hybrid search combining semantic and pattern results via RRF.

    Uses Reciprocal Rank Fusion: rrf_score = sum(1 / (k + rank))
    """
    k = 60  # RRF constant

    # Get both result sets (fetch more than limit for better fusion)
    fetch_limit = limit * 3
    semantic_results = _search_semantic(conn, query, topic, category, tags, fetch_limit)
    pattern_results = _search_pattern(conn, query, topic, category, tags, fetch_limit)

    # Build RRF scores
    rrf_scores: dict[str, float] = {}
    result_map: dict[str, dict[str, Any]] = {}

    for rank, r in enumerate(semantic_results, 1):
        mid = r["id"]
        rrf_scores[mid] = rrf_scores.get(mid, 0) + 1.0 / (k + rank)
        result_map[mid] = r

    for rank, r in enumerate(pattern_results, 1):
        mid = r["id"]
        rrf_scores[mid] = rrf_scores.get(mid, 0) + 1.0 / (k + rank)
        if mid not in result_map:
            result_map[mid] = r

    # Sort by RRF score and return top N
    sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:limit]
    results = []
    for mid in sorted_ids:
        r = result_map[mid]
        r["score"] = round(rrf_scores[mid], 4)
        results.append(r)

    return results


def _format_search_results(results: list[dict[str, Any]], query: str, extract: int) -> str:
    """Format search results for output."""
    lines = [f"Found {len(results)} memories for: {query}\n"]
    for i, r in enumerate(results, 1):
        if extract > 0:
            content_preview = r["content"][:extract]
            if len(r["content"]) > extract:
                content_preview += "..."
        else:
            content_preview = r["content"]
        tags_str = ", ".join(r["tags"]) if r["tags"] else "none"
        lines.append(
            f"{i}. [{r['category']}] {r['topic']} (score: {r['score']})\n"
            f"   Tags: {tags_str} | Relevance: {r['relevance']} | Accessed: {r['access_count']}x\n"
            f"   {content_preview}\n"
            f"   ID: {r['id']}\n"
        )
    return "\n".join(lines)


def list(
    *,
    topic: str | None = None,
    category: str | None = None,
    limit: int = 50,
    format: str = "list",
    depth: int = 0,
) -> str:
    """List memories with optional topic prefix and category filtering.

    Args:
        topic: Topic prefix filter (e.g., "projects/" lists all under projects)
        category: Filter by category
        limit: Maximum results (default: 50)
        format: Output format — "list" (flat, default) or "tree" (hierarchy)
        depth: Tree depth limit (0 = unlimited). Only used when format="tree".

    Returns:
        Formatted list of memories.

    Example:
        mem.list()
        mem.list(topic="projects/onetool/")
        mem.list(category="rule")
        mem.list(format="tree", topic="proj/", depth=1)
    """
    with LogSpan(span="mem.list", topic=topic, category=category, limit=limit, format=format) as s:
        try:
            conn = _get_connection()

            sql = "SELECT id, topic, category, tags, relevance, access_count, created_at, length(content) as content_len, meta FROM memories WHERE 1=1"
            params: list[Any] = []

            topic_sql, topic_params = _topic_filter(topic)
            sql += topic_sql
            params.extend(topic_params)

            if category:
                sql += " AND category = ?"
                params.append(category)

            sql += " ORDER BY topic, updated_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()

            if not rows:
                s.add("resultCount", 0)
                if format == "tree":
                    return "No memories found" + (f" under '{topic}'" if topic else "")
                return "No memories found"

            s.add("resultCount", len(rows))

            if format == "tree":
                return _format_as_tree(rows, topic=topic, depth=depth)

            noun = "memory" if len(rows) == 1 else "memories"
            lines = [f"Found {len(rows)} {noun}:\n"]
            for r in rows:
                tags_list = _deserialize_tags(r[3])
                row_meta = json.loads(r[8]) if r[8] else {}
                section_count = int(row_meta.get("section_count", 0))
                meta_str = _format_entry_meta(
                    mem_id=r[0], content_len=r[7], section_count=section_count,
                    relevance=r[4], category=r[2], tags_list=tags_list,
                )
                lines.append(f"  {r[1]} {meta_str}")
            return "\n".join(lines)

        except Exception as e:
            s.add("error", str(e))
            return f"Error listing memories: {e}"


def count(
    *,
    topic: str | None = None,
    category: str | None = None,
) -> str:
    """Count memories with optional filtering.

    Args:
        topic: Topic prefix filter
        category: Category filter

    Returns:
        Count of matching memories.

    Example:
        mem.count()
        mem.count(topic="projects/")
        mem.count(category="rule")
    """
    with LogSpan(span="mem.count", topic=topic, category=category) as s:
        try:
            conn = _get_connection()

            sql = "SELECT COUNT(*) FROM memories WHERE 1=1"
            params: list[Any] = []

            topic_sql, topic_params = _topic_filter(topic)
            sql += topic_sql
            params.extend(topic_params)

            if category:
                sql += " AND category = ?"
                params.append(category)

            result = conn.execute(sql, params).fetchone()[0]
            s.add("count", result)
            return str(result)

        except Exception as e:
            s.add("error", str(e))
            return f"Error counting memories: {e}"


def delete(
    *,
    topic: str | None = None,
    id: str | None = None,
    confirm: bool = False,
) -> str:
    """Delete memories by topic prefix or ID.

    For safety, deleting multiple memories requires confirm=True.

    Args:
        topic: Topic prefix to delete (e.g., "projects/old/" deletes all under it)
        id: Specific memory ID to delete
        confirm: Required for multi-delete operations

    Returns:
        Deletion confirmation or error.

    Example:
        mem.delete(id="abc-123")
        mem.delete(topic="projects/old/", confirm=True)
    """
    if not topic and not id:
        return "Error: Must specify topic or id"

    with LogSpan(span="mem.delete", topic=topic) as s:
        try:
            conn = _get_connection()

            if id:
                result = conn.execute("DELETE FROM memories WHERE id = ? RETURNING id", [id]).fetchone()
                if result:
                    # Clean up history too
                    conn.execute("DELETE FROM memory_history WHERE memory_id = ?", [id])
                    conn.commit()
                    s.add("deleted", 1)
                    _cache_invalidate(id=id)
                    return f"Deleted memory {id}"
                else:
                    s.add("deleted", 0)
                    return f"No memory found with id '{id}'"

            # Topic-based deletion
            sql = "SELECT COUNT(*) FROM memories WHERE 1=1"
            params: list[Any] = []
            topic_sql, topic_params = _topic_filter(topic)
            sql += topic_sql
            params.extend(topic_params)

            match_count = conn.execute(sql, params).fetchone()[0]

            if match_count == 0:
                s.add("deleted", 0)
                return f"No memories found matching topic '{topic}'"

            if match_count > 1 and not confirm:
                s.add("error", "confirm_required")
                return f"Would delete {match_count} memories. Set confirm=True to proceed."

            # Delete history for matching memories
            del_history_sql = "DELETE FROM memory_history WHERE memory_id IN (SELECT id FROM memories WHERE 1=1" + topic_sql + ")"
            conn.execute(del_history_sql, topic_params)

            del_sql = "DELETE FROM memories WHERE 1=1" + topic_sql
            conn.execute(del_sql, topic_params)
            conn.commit()

            s.add("deleted", match_count)
            _cache_invalidate(topic=topic)
            return f"Deleted {match_count} memories matching topic '{topic}'"

        except Exception as e:
            s.add("error", str(e))
            return f"Error deleting memories: {e}"


def update(
    *,
    topic: str,
    content: str,
    id: str | None = None,
) -> str:
    """Update a memory's content. Must match exactly one memory.

    Stores previous content in history for rollback.
    Re-generates embedding for the new content.

    Args:
        topic: Topic to find the memory (must match exactly one)
        content: New content to replace existing
        id: Optional memory ID for direct update (overrides topic match)

    Returns:
        Update confirmation or error.

    Example:
        mem.update(topic="projects/onetool/rules", content="Updated rule text")
        mem.update(id="abc-123", topic="ignored", content="New content")
    """
    with LogSpan(span="mem.update", topic=topic) as s:
        try:
            conn = _get_connection()

            if id:
                rows = conn.execute(
                    "SELECT id, content, meta FROM memories WHERE id = ?", [id]
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, content, meta FROM memories WHERE topic = ?", [topic]
                ).fetchall()

            if not rows:
                s.add("error", "not_found")
                return f"No memory found for topic '{topic}'" if not id else f"No memory found with id '{id}'"

            if len(rows) > 1:
                s.add("error", "multiple_matches")
                return f"Multiple memories ({len(rows)}) match topic '{topic}'. Use id= for specific update."

            memory_id = rows[0][0]
            old_content = rows[0][1]
            existing_meta: dict[str, str] = _deserialize_meta(rows[0][2])

            # Save history
            history_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO memory_history (id, memory_id, content) VALUES (?, ?, ?)",
                [history_id, memory_id, old_content],
            )

            # Redact and update
            content = _redact(content)
            new_hash = _content_hash(content)
            embedding = _maybe_embed(memory_id, content)

            # Recompute toc if the memory already has sections
            if "sections" in existing_meta:
                headings = _parse_headings(content)
                if headings:
                    existing_meta["sections"] = _encode_sections(headings)
                    existing_meta["section_count"] = str(len(headings))
                else:
                    del existing_meta["sections"]
                    existing_meta.pop("section_count", None)

            conn.execute(
                """
                UPDATE memories
                SET content = ?, content_hash = ?, embedding = ?, meta = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                [content, new_hash, _serialize_embedding(embedding),
                 _serialize_meta(existing_meta), memory_id],
            )
            conn.commit()

            s.add("memoryId", memory_id)
            _cache_invalidate(topic=topic, id=memory_id)
            return f"Updated memory {memory_id} in topic '{topic}'"

        except Exception as e:
            s.add("error", str(e))
            return f"Error updating memory: {e}"


def append(
    *,
    topic: str,
    content: str,
    id: str | None = None,
    separator: str = "\n\n",
) -> str:
    """Append content to an existing memory.

    Args:
        topic: Topic of the memory to append to
        content: Content to append
        id: Optional memory ID (overrides topic match)
        separator: Separator between existing and new content (default: double newline)

    Returns:
        Confirmation or error.

    Example:
        mem.append(topic="projects/onetool/rules", content="New rule to add")
    """
    with LogSpan(span="mem.append", topic=topic) as s:
        try:
            conn = _get_connection()

            if id:
                row = conn.execute(
                    "SELECT id, content, meta FROM memories WHERE id = ?", [id]
                ).fetchone()
            else:
                rows = conn.execute(
                    "SELECT id, content, meta FROM memories WHERE topic = ?", [topic]
                ).fetchall()
                if len(rows) > 1:
                    s.add("error", "multiple_matches")
                    return f"Multiple memories ({len(rows)}) match topic '{topic}'. Use id= for specific append."
                row = rows[0] if rows else None

            if not row:
                s.add("error", "not_found")
                return f"No memory found for topic '{topic}'" if not id else f"No memory found with id '{id}'"

            memory_id = row[0]
            old_content = row[1]
            existing_meta: dict[str, str] = _deserialize_meta(row[2])

            # Save history
            history_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO memory_history (id, memory_id, content) VALUES (?, ?, ?)",
                [history_id, memory_id, old_content],
            )

            new_content = old_content + separator + _redact(content)
            new_hash = _content_hash(new_content)
            embedding = _maybe_embed(memory_id, new_content)

            # Recompute toc if the memory already has sections
            if "sections" in existing_meta:
                headings = _parse_headings(new_content)
                if headings:
                    existing_meta["sections"] = _encode_sections(headings)
                    existing_meta["section_count"] = str(len(headings))
                else:
                    del existing_meta["sections"]
                    existing_meta.pop("section_count", None)

            conn.execute(
                """
                UPDATE memories
                SET content = ?, content_hash = ?, embedding = ?, meta = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                [new_content, new_hash, _serialize_embedding(embedding),
                 _serialize_meta(existing_meta), memory_id],
            )
            conn.commit()

            s.add("memoryId", memory_id)
            s.add("newLen", len(new_content))
            _cache_invalidate(topic=topic, id=memory_id)
            return f"Appended to memory {memory_id} in topic '{topic}' (now {len(new_content)} chars)"

        except Exception as e:
            s.add("error", str(e))
            return f"Error appending to memory: {e}"


# ---------------------------------------------------------------------------
# Phase 2 - Safety and Search: context hot cache
# ---------------------------------------------------------------------------


def context(
    *,
    topic: str | None = None,
    limit: int = 5,
) -> str:
    """Load most-accessed memories for quick context injection.

    Returns the top-N memories by access count, useful for session startup.

    Args:
        topic: Optional topic prefix filter
        limit: Number of memories to return (default: 5)

    Returns:
        Formatted context block with most-accessed memories.

    Example:
        mem.context(topic="projects/onetool/")
        mem.context(limit=10)
    """
    with LogSpan(span="mem.context", topic=topic, limit=limit) as s:
        try:
            conn = _get_connection()

            sql = """
                SELECT id, topic, content, category, tags, relevance, access_count
                FROM memories
                WHERE 1=1
            """
            params: list[Any] = []

            topic_sql, topic_params = _topic_filter(topic)
            sql += topic_sql
            params.extend(topic_params)

            sql += " ORDER BY access_count DESC, relevance DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()

            if not rows:
                s.add("resultCount", 0)
                return "No memories found for context"

            # Increment access counts (batch)
            ids = [r[0] for r in rows]
            placeholders = ", ".join("?" for _ in ids)
            conn.execute(
                f"UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id IN ({placeholders})",
                ids,
            )
            conn.commit()

            s.add("resultCount", len(rows))

            lines = [f"Context: {len(rows)} memories loaded\n"]
            for r in rows:
                lines.append(
                    f"## {r[1]} [{r[3]}]\n"
                    f"{r[2]}\n"
                )
            return "\n".join(lines)

        except Exception as e:
            s.add("error", str(e))
            return f"Error loading context: {e}"


# ---------------------------------------------------------------------------
# Phase 3 - Lifecycle and I/O
# ---------------------------------------------------------------------------


def update_batch(
    *,
    search_text: str,
    replace_text: str,
    topic: str | None = None,
    dry_run: bool = True,
) -> str:
    """Search and replace text across matching memories.

    Args:
        search_text: Text to find in memory content
        replace_text: Text to replace with
        topic: Optional topic prefix to scope the operation
        dry_run: If True (default), only preview changes without applying

    Returns:
        Summary of changes (or preview in dry_run mode).

    Example:
        mem.update_batch(search_text="old_name", replace_text="new_name", topic="projects/", dry_run=True)
        mem.update_batch(search_text="old_name", replace_text="new_name", topic="projects/", dry_run=False)
    """
    with LogSpan(span="mem.update_batch", search=search_text, replace=replace_text, dry_run=dry_run) as s:
        try:
            conn = _get_connection()

            escaped = search_text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            sql = "SELECT id, topic, content, meta FROM memories WHERE content LIKE ? ESCAPE '\\'"
            params: list[Any] = [f"%{escaped}%"]

            topic_sql, topic_params = _topic_filter(topic)
            sql += topic_sql
            params.extend(topic_params)

            rows = conn.execute(sql, params).fetchall()

            if not rows:
                s.add("matchCount", 0)
                return f"No memories contain '{search_text}'"

            s.add("matchCount", len(rows))

            if dry_run:
                lines = [f"Dry run: {len(rows)} memories would be updated:\n"]
                for r in rows:
                    occurrences = r[2].count(search_text)
                    lines.append(f"  {r[1]} ({occurrences} occurrence{'s' if occurrences != 1 else ''}) id={r[0][:8]}...")
                return "\n".join(lines)

            updated = 0
            for r in rows:
                memory_id, _topic, old_content = r[0], r[1], r[2]
                existing_meta: dict[str, str] = _deserialize_meta(r[3])

                # Save history
                history_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO memory_history (id, memory_id, content) VALUES (?, ?, ?)",
                    [history_id, memory_id, old_content],
                )

                new_content = old_content.replace(search_text, replace_text)
                new_hash = _content_hash(new_content)
                embedding = _maybe_embed(memory_id, new_content)

                # Recompute TOC if the memory has sections
                if "sections" in existing_meta:
                    headings = _parse_headings(new_content)
                    if headings:
                        existing_meta["sections"] = _encode_sections(headings)
                        existing_meta["section_count"] = str(len(headings))
                    else:
                        del existing_meta["sections"]
                        existing_meta.pop("section_count", None)

                conn.execute(
                    """
                    UPDATE memories
                    SET content = ?, content_hash = ?, embedding = ?, meta = ?, updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    [new_content, new_hash, _serialize_embedding(embedding),
                     _serialize_meta(existing_meta), memory_id],
                )
                updated += 1

            conn.commit()
            s.add("updated", updated)
            _cache_invalidate()  # Batch update: clear entire cache
            return f"Updated {updated} memories: replaced '{search_text}' with '{replace_text}'"

        except Exception as e:
            s.add("error", str(e))
            return f"Error in batch update: {e}"


def decay(
    *,
    dry_run: bool = True,
) -> str:
    """Apply importance decay to all memories based on age and access patterns.

    Formula: score = relevance * 0.5^(age_days/half_life) * (1 + log(access+1) * 0.1)

    Args:
        dry_run: If True (default), only show decay scores without modifying

    Returns:
        Decay analysis or update confirmation.

    Example:
        mem.decay(dry_run=True)
        mem.decay(dry_run=False)
    """
    with LogSpan(span="mem.decay", dry_run=dry_run) as s:
        try:
            config = _get_config()
            half_life = config.decay_half_life_days
            conn = _get_connection()

            rows = conn.execute(
                "SELECT id, topic, relevance, access_count, created_at FROM memories"
            ).fetchall()

            if not rows:
                return "No memories to decay"

            now = datetime.now(UTC)
            decay_results = []

            for r in rows:
                memory_id, topic, relevance, access_count, created_at_str = r
                # SQLite stores timestamps as ISO text strings
                created_at = datetime.fromisoformat(created_at_str)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=UTC)
                age_days = (now - created_at).total_seconds() / 86400

                decay_factor = 0.5 ** (age_days / half_life)
                access_boost = 1 + math.log(access_count + 1) * 0.1
                decayed_score = relevance * decay_factor * access_boost
                new_relevance = max(1, min(relevance, round(decayed_score)))

                decay_results.append({
                    "id": memory_id,
                    "topic": topic,
                    "old_relevance": relevance,
                    "new_relevance": new_relevance,
                    "age_days": round(age_days, 1),
                    "access_count": access_count,
                })

            s.add("memoryCount", len(decay_results))

            if dry_run:
                lines = [f"Decay preview ({len(decay_results)} memories, half_life={half_life}d):\n"]
                changed = [d for d in decay_results if d["old_relevance"] != d["new_relevance"]]
                for d in changed[:20]:
                    lines.append(
                        f"  {d['topic']}: {d['old_relevance']} -> {d['new_relevance']} "
                        f"(age={d['age_days']}d, accessed={d['access_count']}x)"
                    )
                if not changed:
                    lines.append("  No changes needed")
                elif len(changed) > 20:
                    lines.append(f"  ... and {len(changed) - 20} more")
                return "\n".join(lines)

            updated = 0
            for d in decay_results:
                if d["old_relevance"] != d["new_relevance"]:
                    conn.execute(
                        "UPDATE memories SET relevance = ? WHERE id = ?",
                        [d["new_relevance"], d["id"]],
                    )
                    updated += 1

            conn.commit()
            s.add("updated", updated)
            return f"Applied decay to {updated} memories (half_life={half_life}d)"

        except Exception as e:
            s.add("error", str(e))
            return f"Error applying decay: {e}"


def stats() -> str:
    """Show memory statistics - counts, sizes, category breakdown, topic tree.

    Returns:
        Formatted statistics.

    Example:
        mem.stats()
    """
    with LogSpan(span="mem.stats") as s:
        try:
            conn = _get_connection()

            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            if total == 0:
                return "No memories stored"

            # Category breakdown
            categories = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM memories GROUP BY category ORDER BY cnt DESC"
            ).fetchall()

            # Topic tree (top-level topics)
            topics = conn.execute(
                """
                SELECT
                    CASE WHEN instr(topic, '/') > 0
                         THEN substr(topic, 1, instr(topic, '/') - 1)
                         ELSE topic
                    END as root_topic,
                    COUNT(*) as cnt
                FROM memories
                GROUP BY root_topic
                ORDER BY cnt DESC
                """
            ).fetchall()

            # Size stats
            size_stats = conn.execute(
                "SELECT SUM(length(content)), AVG(length(content)), MAX(length(content)) FROM memories"
            ).fetchone()

            # History count
            history_count = conn.execute("SELECT COUNT(*) FROM memory_history").fetchone()[0]

            # Embedding stats
            without_embeddings = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE embedding IS NULL"
            ).fetchone()[0]
            config = _get_config()

            s.add("total", total)

            lines = [
                "Memory Statistics:\n",
                f"  Total memories: {total}",
                f"  History entries: {history_count}",
                f"  Total content: {size_stats[0]:,} chars",
                f"  Avg content: {int(size_stats[1]):,} chars",
                f"  Max content: {size_stats[2]:,} chars",
                f"\nEmbeddings: {'enabled' if config.embeddings_enabled else 'disabled'}",
                f"  With embeddings: {total - without_embeddings}",
                f"  Without embeddings: {without_embeddings}",
                f"  Pending in queue: {_embedding_queue.qsize()}",
                f"  Embedding errors: {_embedding_errors}",
                "\nCategories:",
            ]
            for cat, cnt in categories:
                lines.append(f"  {cat}: {cnt}")

            lines.append("\nTopics:")
            for topic, cnt in topics:
                lines.append(f"  {topic}/: {cnt}")

            return "\n".join(lines)

        except Exception as e:
            s.add("error", str(e))
            return f"Error getting stats: {e}"


def embed(
    *,
    topic: str | None = None,
    limit: int = 100,
    dry_run: bool = True,
) -> str:
    """Generate embeddings for memories that don't have them.

    Use after enabling embeddings_enabled to backfill existing memories.

    Args:
        topic: Optional topic prefix filter
        limit: Maximum memories to process (default: 100)
        dry_run: If True, only report count without generating (default: True)

    Returns:
        Summary of backfill results.

    Example:
        mem.embed(dry_run=True)           # Preview count
        mem.embed(dry_run=False)           # Generate embeddings
        mem.embed(topic="projects/", dry_run=False)  # Scoped backfill
    """
    config = _get_config()
    if not config.embeddings_enabled:
        return "Embeddings are disabled. Enable with: tools.mem.embeddings_enabled: true"

    with LogSpan(span="mem.embed", topic=topic, limit=limit, dry_run=dry_run) as s:
        try:
            conn = _get_connection()

            sql = "SELECT id, content FROM memories WHERE embedding IS NULL"
            params: list[Any] = []
            if topic:
                topic_sql, topic_params = _topic_filter(topic)
                sql += topic_sql
                params.extend(topic_params)
            sql += " LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()

            if not rows:
                return "All memories already have embeddings"

            if dry_run:
                s.add("count", len(rows))
                return f"Found {len(rows)} memories without embeddings. Run with dry_run=False to generate."

            generated = 0
            for memory_id, content in rows:
                embedding = _generate_embedding(content)
                conn.execute(
                    "UPDATE memories SET embedding = ? WHERE id = ?",
                    [_serialize_embedding(embedding), memory_id],
                )
                generated += 1

            conn.commit()
            s.add("generated", generated)
            return f"Generated embeddings for {generated} memories"

        except Exception as e:
            s.add("error", str(e))
            return f"Error generating embeddings: {e}"


def flush() -> str:
    """Wait for all pending background embeddings to complete.

    Returns:
        Completion status.

    Example:
        mem.flush()
    """
    if not _embedding_worker_started:
        return "No background embeddings pending"
    try:
        _embedding_queue.join()
        return "All pending embeddings completed"
    except Exception as e:
        return f"Error: {e}"


def export(
    *,
    topic: str | None = None,
    output: str | None = None,
) -> str:
    """Export memories to YAML format.

    Args:
        topic: Optional topic prefix filter
        output: Output file path (default: prints to stdout)

    Returns:
        Exported content or file path confirmation.

    Example:
        mem.export(output="memories.yaml")
        mem.export(topic="projects/onetool/")
    """
    with LogSpan(span="mem.export", topic=topic) as s:
        try:
            conn = _get_connection()

            sql = """
                SELECT id, topic, content, category, tags, relevance, access_count,
                       created_at, updated_at, meta
                FROM memories
                WHERE 1=1
            """
            params: list[Any] = []

            topic_sql, topic_params = _topic_filter(topic)
            sql += topic_sql
            params.extend(topic_params)

            sql += " ORDER BY topic, created_at"

            rows = conn.execute(sql, params).fetchall()

            if not rows:
                return "No memories to export"

            s.add("memoryCount", len(rows))

            content = _export_yaml(rows)

            if output:
                validated_path, error = _validate_file_path(output, must_exist=False)
                if error:
                    return f"Error: {error}"
                assert validated_path is not None
                validated_path.parent.mkdir(parents=True, exist_ok=True)
                validated_path.write_text(content, encoding="utf-8")
                return f"Exported {len(rows)} memories to {validated_path}"

            return content

        except Exception as e:
            s.add("error", str(e))
            return f"Error exporting memories: {e}"


def _export_yaml(rows: list[tuple]) -> str:
    """Export memories to YAML format."""
    lines = ["memories:"]
    for r in rows:
        tags_str = "[" + ", ".join(f'"{t}"' for t in _deserialize_tags(r[4])) + "]"
        # Use block scalar |- for content to safely handle newlines and special chars
        content_lines = r[2].split("\n")
        indented_content = "\n".join(f"      {line}" for line in content_lines)
        meta_dict = _deserialize_meta(r[9])
        meta_json = json.dumps(meta_dict) if meta_dict else "{}"
        lines.extend([
            f"  - id: \"{r[0]}\"",
            f"    topic: \"{r[1]}\"",
            "    content: |-",
            indented_content,
            f"    category: \"{r[3]}\"",
            f"    tags: {tags_str}",
            f"    relevance: {r[5]}",
            f"    access_count: {r[6]}",
            f"    created_at: \"{r[7]}\"",
            f"    updated_at: \"{r[8]}\"",
            f"    meta: '{meta_json}'",
            "",
        ])
    return "\n".join(lines)


def load(
    *,
    file: str,
) -> str:
    """Import memories from a YAML file. Skips duplicates.

    Args:
        file: Path to YAML file to import

    Returns:
        Import summary.

    Example:
        mem.load(file="memories.yaml")
    """
    with LogSpan(span="mem.load", file=file) as s:
        try:
            try:
                import yaml
            except ImportError as e:
                raise ImportError(
                    "pyyaml is required for YAML import. Install with: pip install pyyaml"
                ) from e

            validated_path, error = _validate_file_path(file, must_exist=True)
            if error:
                return f"Error: {error}"
            assert validated_path is not None

            data = yaml.safe_load(validated_path.read_text(encoding="utf-8"))
            if not data or "memories" not in data:
                return "Error: Invalid YAML format - expected 'memories' key"

            memories = data["memories"]
            conn = _get_connection()
            imported = 0
            skipped = 0

            for mem_data in memories:
                topic = mem_data.get("topic", "")
                content = mem_data.get("content", "")
                if not topic or not content:
                    skipped += 1
                    continue

                content_hash = _content_hash(content)

                # Check for existing
                existing = conn.execute(
                    "SELECT id FROM memories WHERE topic = ? AND content_hash = ?",
                    [topic, content_hash],
                ).fetchone()

                if existing:
                    skipped += 1
                    continue

                memory_id = mem_data.get("id", str(uuid.uuid4()))
                category = mem_data.get("category", "note")
                mem_tags = mem_data.get("tags", [])
                relevance = max(1, min(10, int(mem_data.get("relevance", 5))))

                # Restore meta if present
                meta_raw = mem_data.get("meta", "{}")
                if isinstance(meta_raw, dict):
                    meta_str = _serialize_meta(meta_raw)
                elif isinstance(meta_raw, str):
                    # Validate it's valid JSON, normalise
                    meta_str = _serialize_meta(_deserialize_meta(meta_raw))
                else:
                    meta_str = "{}"

                embedding = _maybe_embed(memory_id, content)

                conn.execute(
                    """
                    INSERT INTO memories (id, topic, content, content_hash, category, tags, relevance, embedding, meta)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [memory_id, topic, content, content_hash, category,
                     _serialize_tags(mem_tags), relevance, _serialize_embedding(embedding), meta_str],
                )
                imported += 1

            conn.commit()
            s.add("imported", imported)
            s.add("skipped", skipped)
            _cache_invalidate()  # Bulk import: clear entire cache
            return f"Imported {imported} memories, skipped {skipped}"

        except ImportError as e:
            return f"Error: {e}"
        except Exception as e:
            s.add("error", str(e))
            return f"Error importing memories: {e}"


def snap(
    *,
    output: str,
    topic: str | None = None,
    ext: str = "",
    on_conflict: str = "skip",
) -> str:
    """Write memories to a directory as individual files with an index.yaml.

    Creates one file per memory record with an index.yaml containing metadata.
    Round-trips losslessly with `mem.restore()`.

    Args:
        output: Output directory path
        topic: Topic prefix filter (all memories if omitted)
        ext: File extension appended to topic for content files (default: "" — topic is the file path)
        on_conflict: "skip" (default) or "overwrite" for existing files

    Returns:
        Summary of snap results.

    Example:
        mem.snap(output="backup/consult", topic="consult/")
        mem.snap(output="backup/all")
        mem.snap(output="backup/config", topic="config/", ext=".yaml")
    """
    if on_conflict not in ("skip", "overwrite"):
        return f"Error: on_conflict must be 'skip' or 'overwrite', got '{on_conflict}'"

    with LogSpan(span="mem.snap", output=output, topic=topic) as s:
        try:
            conn = _get_connection()

            sql = """
                SELECT id, topic, content, category, tags, relevance, access_count,
                       created_at, updated_at, meta
                FROM memories
                WHERE 1=1
            """
            params: list[Any] = []

            topic_sql, topic_params = _topic_filter(topic)
            sql += topic_sql
            params.extend(topic_params)

            sql += " ORDER BY topic, created_at"

            rows = conn.execute(sql, params).fetchall()

            if not rows:
                return "No memories to snap"

            # Determine topic prefix to strip
            strip_prefix = ""
            if topic and topic.endswith("/"):
                strip_prefix = topic

            validated_path, error = _validate_file_path(output, must_exist=False)
            if error:
                return f"Error: {error}"
            assert validated_path is not None
            validated_path.mkdir(parents=True, exist_ok=True)

            written = 0
            skipped = 0
            index_entries = []

            for r in rows:
                _id, mem_topic, content, category, raw_tags, relevance = (
                    r[0], r[1], r[2], r[3], r[4], r[5],
                )
                tags = _deserialize_tags(raw_tags)
                raw_meta = _deserialize_meta(r[9])

                # Compute relative file path
                rel_topic = mem_topic
                if strip_prefix and mem_topic.startswith(strip_prefix):
                    rel_topic = mem_topic[len(strip_prefix):]
                elif strip_prefix and mem_topic == strip_prefix.rstrip("/"):
                    rel_topic = mem_topic.rsplit("/", 1)[-1]

                file_rel = rel_topic + ext
                file_path = validated_path / file_rel

                if file_path.exists() and on_conflict == "skip":
                    skipped += 1
                    index_entries.append({
                        "topic": mem_topic,
                        "file": file_rel,
                        "category": category,
                        "tags": tags,
                        "relevance": relevance,
                        "meta": raw_meta,
                    })
                    continue

                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
                written += 1

                index_entries.append({
                    "topic": mem_topic,
                    "file": file_rel,
                    "category": category,
                    "tags": tags,
                    "relevance": relevance,
                    "meta": raw_meta,
                })

            # Write index.yaml
            now_str = datetime.now(UTC).isoformat()
            filter_val = f'"{topic}"' if topic else "null"
            index_lines = [
                "snapshot:",
                f'  created_at: "{now_str}"',
                f"  topic_filter: {filter_val}",
                f'  ext: "{ext}"',
                f"  count: {len(index_entries)}",
                "",
                "memories:",
            ]
            for entry in index_entries:
                tags_str = "[" + ", ".join(f'"{t}"' for t in entry["tags"]) + "]"
                meta_json = json.dumps(entry.get("meta", {}))
                index_lines.extend([
                    f'  - topic: "{entry["topic"]}"',
                    f'    file: "{entry["file"]}"',
                    f'    category: "{entry["category"]}"',
                    f"    tags: {tags_str}",
                    f'    relevance: {entry["relevance"]}',
                    f"    meta: '{meta_json}'",
                    "",
                ])

            index_path = validated_path / "index.yaml"
            index_path.write_text("\n".join(index_lines), encoding="utf-8")

            s.add("written", written)
            s.add("skipped", skipped)
            s.add("total", len(index_entries))
            return f"Snap {len(index_entries)} memories to {validated_path} ({written} written, {skipped} skipped)"

        except Exception as e:
            s.add("error", str(e))
            return f"Error creating snap: {e}"


def restore(
    *,
    input: str,
    topic: str | None = None,
    overwrite: bool = False,
) -> str:
    """Restore memories from a snap directory (created by `mem.snap`).

    Reads index.yaml and content files, recreating memories with full metadata.

    Args:
        input: Input directory path (must contain index.yaml)
        topic: Override base topic (otherwise uses topics from index)
        overwrite: If True, overwrite existing memories with same topic+hash

    Returns:
        Restore summary.

    Example:
        mem.restore(input="backup/consult", topic="consult")
        mem.restore(input="backup/consult", topic="consult", overwrite=True)
    """
    with LogSpan(span="mem.restore", input=input) as s:
        try:
            try:
                import yaml
            except ImportError as e:
                raise ImportError(
                    "pyyaml is required for YAML import. Install with: pip install pyyaml"
                ) from e

            validated_path, error = _validate_file_path(input, must_exist=True)
            if error:
                return f"Error: {error}"
            assert validated_path is not None

            if not validated_path.is_dir():
                return f"Error: '{input}' is not a directory"

            index_path = validated_path / "index.yaml"
            if not index_path.exists():
                return f"Error: index.yaml not found in '{input}'"

            data = yaml.safe_load(index_path.read_text(encoding="utf-8"))
            if not data or "memories" not in data:
                return "Error: Invalid index.yaml - expected 'memories' key"

            # Determine topic remapping
            snapshot_meta = data.get("snapshot", {})
            original_filter = snapshot_meta.get("topic_filter")

            memories = data["memories"]
            restored = 0
            skipped = 0
            errors = []
            conn = _get_connection()

            for entry in memories:
                mem_topic = entry.get("topic", "")
                file_rel = entry.get("file", "")
                category = entry.get("category", "note")
                tags = entry.get("tags", [])
                relevance = max(1, min(10, int(entry.get("relevance", 5))))

                # Restore meta if present
                meta_raw = entry.get("meta", {})
                if isinstance(meta_raw, dict):
                    meta_str = _serialize_meta(meta_raw)
                elif isinstance(meta_raw, str):
                    meta_str = _serialize_meta(_deserialize_meta(meta_raw))
                else:
                    meta_str = "{}"

                if not mem_topic or not file_rel:
                    errors.append("Missing topic or file in index entry")
                    continue

                # Remap topic if override provided
                if topic is not None:
                    # Strip original filter prefix, prepend new topic
                    rel = mem_topic
                    if original_filter and mem_topic.startswith(original_filter):
                        rel = mem_topic[len(original_filter):]
                    elif original_filter and mem_topic == original_filter.rstrip("/"):
                        rel = mem_topic.rsplit("/", 1)[-1]
                    mem_topic = f"{topic}/{rel}" if rel else topic

                # Read content file
                content_path = validated_path / file_rel
                if not content_path.exists():
                    errors.append(f"File not found: {file_rel}")
                    continue

                content = content_path.read_text(encoding="utf-8")
                content_hash = _content_hash(content)

                # Check for existing
                existing = conn.execute(
                    "SELECT id FROM memories WHERE topic = ? AND content_hash = ?",
                    [mem_topic, content_hash],
                ).fetchone()

                if existing and not overwrite:
                    skipped += 1
                    continue

                if existing and overwrite:
                    conn.execute("DELETE FROM memories WHERE id = ?", [existing[0]])

                memory_id = str(uuid.uuid4())
                embedding = _maybe_embed(memory_id, content)

                conn.execute(
                    """
                    INSERT INTO memories (id, topic, content, content_hash, category, tags, relevance, embedding, meta)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [memory_id, mem_topic, content, content_hash, category,
                     _serialize_tags(tags), relevance, _serialize_embedding(embedding), meta_str],
                )
                restored += 1

            conn.commit()
            s.add("restored", restored)
            s.add("skipped", skipped)
            s.add("errors", len(errors))
            _cache_invalidate()

            parts = [f"Restored {restored} memories, skipped {skipped}"]
            if errors:
                parts.append(f", {len(errors)} errors")
                for err in errors[:5]:
                    parts.append(f"\n  - {err}")
            return "".join(parts)

        except ImportError as e:
            return f"Error: {e}"
        except Exception as e:
            s.add("error", str(e))
            return f"Error restoring snap: {e}"


# ---------------------------------------------------------------------------
# Staleness, tree, and refresh
# ---------------------------------------------------------------------------


def stale(
    *,
    topic: str | None = None,
) -> str:
    """Check which file-backed memories have outdated content relative to their source files.

    Scans memories for staleness by comparing stored source_mtime against the
    current file modification time. Only checks memories that have source
    metadata (written via file= parameter).

    Args:
        topic: Topic prefix to filter (e.g., "docs/"). If omitted, checks all memories.

    Returns:
        Summary of fresh, stale, missing, and skipped memories.

    Example:
        mem.stale()
        mem.stale(topic="proj/onetool-mcp/dev/")
    """
    with LogSpan(span="mem.stale", topic=topic or "(all)") as s:
        try:
            with _use_connection() as conn:
                sql = "SELECT topic, meta FROM memories WHERE 1=1"
                topic_sql, params = _topic_filter(topic)
                sql += topic_sql
                sql += " ORDER BY topic"
                rows = conn.execute(sql, params).fetchall()

            if not rows:
                s.add("found", 0)
                return "No memories found" + (f" under '{topic}'" if topic else "")

            fresh: _builtins_list[str] = []
            stale_list: _builtins_list[tuple[str, str, str]] = []
            missing_list: _builtins_list[str] = []
            skipped = 0

            for row_topic, raw_meta in rows:
                meta = _deserialize_meta(raw_meta)
                status = _check_staleness(meta)
                if status == "fresh":
                    fresh.append(row_topic)
                elif status == "stale":
                    stored = meta.get("source_mtime", "")
                    source_path = Path(meta["source"])
                    try:
                        current = str(source_path.stat().st_mtime)
                    except OSError:
                        missing_list.append(row_topic)
                        continue
                    stale_list.append((row_topic, stored, current))
                elif status == "missing":
                    missing_list.append(row_topic)
                else:
                    skipped += 1

            total_checked = len(fresh) + len(stale_list) + len(missing_list)
            if total_checked == 0:
                s.add("skipped", skipped)
                return "No file-backed memories found" + (f" under '{topic}'" if topic else "")

            scope = f' under "{topic}"' if topic else ""
            parts = [f"Checked {total_checked} file-backed memories{scope}:"]
            parts.append(f"  {len(fresh)} fresh")

            if stale_list:
                parts.append(f"  {len(stale_list)} stale:")
                for st_topic, stored_mt, current_mt in stale_list:
                    stored_dt = datetime.fromtimestamp(float(stored_mt), tz=UTC).strftime("%Y-%m-%d")
                    current_dt = datetime.fromtimestamp(float(current_mt), tz=UTC).strftime("%Y-%m-%d")
                    parts.append(f"    - {st_topic} (stored: {stored_dt}, file: {current_dt})")

            if missing_list:
                parts.append(f"  {len(missing_list)} missing:")
                for m_topic in missing_list:
                    parts.append(f"    - {m_topic} (source file deleted)")

            if skipped:
                parts.append(f"  ({skipped} memories without source metadata skipped)")

            s.add("fresh", len(fresh))
            s.add("stale", len(stale_list))
            s.add("missing", len(missing_list))
            s.add("skipped", skipped)
            return "\n".join(parts)

        except Exception as e:
            s.add("error", str(e))
            return f"Error checking staleness: {e}"


def _format_as_tree(
    rows: _builtins_list[Any],
    *,
    topic: str | None,
    depth: int,
) -> str:
    """Format list rows as a tree hierarchy.

    Row schema: (id, topic, category, tags, relevance, access_count,
                 created_at, content_len, meta).
    """
    # Strip common prefix if topic filter provided with trailing /
    prefix = ""
    if topic and topic.endswith("/"):
        prefix = topic

    # Build nested tree dict; leaf nodes store metadata tuple
    tree_dict: dict[str, Any] = {}
    for r in rows:
        mem_id, mem_topic, category, tags_raw, relevance = r[0], r[1], r[2], r[3], r[4]
        content_len, meta_json = r[7], r[8]
        rel_topic = mem_topic[len(prefix):] if prefix and mem_topic.startswith(prefix) else mem_topic
        parts = rel_topic.split("/")
        node = tree_dict
        for part in parts[:-1]:
            if part not in node:
                node[part] = {}
            elif not isinstance(node[part], dict):
                # Existing leaf becomes a dict; preserve leaf data under ""
                leaf_data = node[part]
                node[part] = {"": leaf_data}
            node = node[part]
        # Store leaf with metadata tuple
        leaf_name = parts[-1]
        tags_list = _deserialize_tags(tags_raw)
        row_meta = json.loads(meta_json) if meta_json else {}
        section_count = int(row_meta.get("section_count", 0))
        node[leaf_name] = ("_leaf_", mem_id, category, tags_list, content_len, relevance, section_count)

    # Render tree
    lines: _builtins_list[str] = []
    total = len(rows)
    header = f"{prefix}" if prefix else "(all)"
    lines.append(f"{header}  (mem_count={total})")
    _render_tree(tree_dict, lines, prefix="", max_depth=depth)

    return "\n".join(lines)


def _format_entry_meta(
    *,
    mem_id: str,
    content_len: int,
    section_count: int,
    relevance: int,
    category: str,
    tags_list: _builtins_list[str],
) -> str:
    """Format parenthesised metadata for list and tree entries.

    Attribute order: id, len, sec, rel, category, tags.
    Hide-if-default: sec hidden when 0, rel hidden when 5, tags hidden when empty.
    """
    meta_parts = [f"id={mem_id[:8]}", f"len={content_len}"]
    if section_count > 0:
        meta_parts.append(f"sec={section_count}")
    if relevance != 5:
        meta_parts.append(f"rel={relevance}")
    meta_parts.append(f"category={category}")
    if tags_list:
        meta_parts.append(f"tags={'|'.join(tags_list)}")
    return f"({' '.join(meta_parts)})"


def _render_tree(
    node: dict[str, Any],
    lines: _builtins_list[str],
    prefix: str,
    max_depth: int,
    current_depth: int = 1,
) -> None:
    """Recursively render a tree dict into indented lines with box-drawing connectors."""
    entries = sorted(node)
    for idx, name in enumerate(entries):
        is_last = idx == len(entries) - 1
        connector = "└── " if is_last else "├── "
        extension = "    " if is_last else "│   "
        value = node[name]
        if isinstance(value, tuple) and value and value[0] == "_leaf_":
            # Leaf node with metadata
            _, mem_id, category, tags_list, content_len, relevance, section_count = value
            meta = _format_entry_meta(
                mem_id=mem_id, content_len=content_len, section_count=section_count,
                relevance=relevance, category=category, tags_list=tags_list,
            )
            lines.append(f"{prefix}{connector}{name}  {meta}")
        elif isinstance(value, dict):
            # Directory node - count leaves
            leaf_count = _count_leaves(value)
            lines.append(f"{prefix}{connector}{name}/  (mem_count={leaf_count})")
            if not (max_depth > 0 and current_depth >= max_depth):
                _render_tree(
                    value, lines,
                    prefix=prefix + extension,
                    max_depth=max_depth,
                    current_depth=current_depth + 1,
                )


def _count_leaves(node: dict[str, Any] | tuple[Any, ...]) -> int:
    """Count leaf nodes (memories) in a tree dict or tuple leaf."""
    if isinstance(node, tuple):
        return 1
    if not node:
        return 0
    return sum(_count_leaves(v) for v in node.values())


def refresh(
    *,
    topic: str | None = None,
    dry_run: bool = True,
) -> str:
    """Re-read source files for stale file-backed memories.

    Finds memories whose source files have changed since storage and updates
    their content. Preserves history (same as update). Default is dry_run=True
    for safety.

    Args:
        topic: Topic prefix to filter. If omitted, checks all memories.
        dry_run: If True (default), report what would change without modifying.

    Returns:
        Summary of refreshed, skipped, and unchanged memories.

    Example:
        mem.refresh(topic="proj/onetool-mcp/dev/")
        mem.refresh(topic="proj/onetool-mcp/dev/", dry_run=False)
    """
    mode_label = "dry run" if dry_run else "apply"
    with LogSpan(span="mem.refresh", topic=topic or "(all)", dryRun=dry_run) as s:
        try:
            with _use_connection() as conn:
                sql = "SELECT id, topic, content, meta FROM memories WHERE 1=1"
                topic_sql, params = _topic_filter(topic)
                sql += topic_sql
                sql += " ORDER BY topic"
                rows = conn.execute(sql, params).fetchall()

            if not rows:
                s.add("found", 0)
                return "No memories found" + (f" under '{topic}'" if topic else "")

            fresh_count = 0
            stale_entries: _builtins_list[tuple[str, str, str, dict[str, str], str]] = []
            missing_entries: _builtins_list[str] = []
            skipped = 0

            for mem_id, mem_topic, old_content, raw_meta in rows:
                meta = _deserialize_meta(raw_meta)
                status = _check_staleness(meta)
                if status == "fresh":
                    fresh_count += 1
                elif status == "stale":
                    source_path = meta["source"]
                    stale_entries.append((mem_id, mem_topic, old_content, meta, source_path))
                elif status == "missing":
                    missing_entries.append(mem_topic)
                else:
                    skipped += 1

            total_checked = fresh_count + len(stale_entries) + len(missing_entries)
            if total_checked == 0:
                s.add("skipped", skipped)
                return "No file-backed memories found" + (f" under '{topic}'" if topic else "")

            # Build report
            scope = f' for "{topic}"' if topic else ""
            parts = [f"Refresh ({mode_label}){scope}:"]

            if stale_entries:
                verb = "would update" if dry_run else "updated"
                parts.append(f"  {len(stale_entries)} stale - {verb}:")
                for mem_id, mem_topic, old_content, meta, source_path in stale_entries:
                    p = Path(source_path)
                    if dry_run:
                        new_size = p.stat().st_size if p.exists() else 0
                        parts.append(f"    - {mem_topic} ({len(old_content)} -> {new_size} chars)")
                    else:
                        # Actually refresh
                        try:
                            new_content = p.read_text(encoding="utf-8")
                        except OSError:
                            parts.append(f"    - {mem_topic} (skipped: source file disappeared)")
                            continue
                        if len(new_content) > 1_000_000:
                            parts.append(f"    - {mem_topic} (skipped: file too large)")
                            continue

                        new_content = _redact(new_content)
                        new_hash = _content_hash(new_content)
                        new_mtime = str(p.stat().st_mtime)

                        # Save history
                        history_id = str(uuid.uuid4())
                        with _use_connection() as conn:
                            conn.execute(
                                "INSERT INTO memory_history (id, memory_id, content) VALUES (?, ?, ?)",
                                [history_id, mem_id, old_content],
                            )

                            # Recompute TOC if sections existed
                            if "sections" in meta:
                                headings = _parse_headings(new_content)
                                if headings:
                                    meta["sections"] = _encode_sections(headings)
                                    meta["section_count"] = str(len(headings))
                                else:
                                    del meta["sections"]
                                    meta.pop("section_count", None)

                            # Update source_mtime
                            meta["source_mtime"] = new_mtime

                            embedding = _maybe_embed(mem_id, new_content)

                            conn.execute(
                                """
                                UPDATE memories
                                SET content = ?, content_hash = ?, embedding = ?, meta = ?, updated_at = datetime('now')
                                WHERE id = ?
                                """,
                                [new_content, new_hash, _serialize_embedding(embedding),
                                 _serialize_meta(meta), mem_id],
                            )
                            conn.commit()

                        _cache_invalidate(topic=mem_topic)
                        parts.append(f"    - {mem_topic} ({len(old_content)} -> {len(new_content)} chars)")

            if missing_entries:
                parts.append(f"  {len(missing_entries)} missing - skipped:")
                for m_topic in missing_entries:
                    parts.append(f"    - {m_topic}")

            parts.append(f"  {fresh_count} fresh - no change")

            s.add("stale", len(stale_entries))
            s.add("missing", len(missing_entries))
            s.add("fresh", fresh_count)
            s.add("skipped", skipped)
            s.add("dryRun", dry_run)
            return "\n".join(parts)

        except Exception as e:
            s.add("error", str(e))
            return f"Error refreshing memories: {e}"
