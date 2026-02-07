"""Persistent memory for AI agents with DuckDB storage and optional OpenAI embeddings.

Provides topic-based memory storage with semantic search, content dedup,
secret redaction, and importance decay. Requires OPENAI_API_KEY in secrets.yaml
when embeddings are enabled.

Thread safety: Uses a shared DuckDB connection. Concurrent calls from multiple
threads should use _use_connection() to hold the lock for the full operation.
MCP tool dispatch is single-threaded so this is safe in normal usage.

Reference: ChunkHound connection patterns, code_search.py embedding patterns.
"""

from __future__ import annotations

import builtins
import contextlib
import hashlib
import logging
import math
import queue
import re
import shutil
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
    "restore",
    "search",
    "slice",
    "snap",
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
        ("duckdb", "pip install duckdb"),
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

logger = logging.getLogger(__name__)

# Alias to avoid conflict with the module-level list() function
_builtins_list = builtins.list

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
        description="Path to memory DuckDB database (relative to .onetool/)",
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


# ---------------------------------------------------------------------------
# Database connection and schema
# ---------------------------------------------------------------------------


def _import_duckdb() -> ModuleType:
    """Lazy import duckdb module."""
    try:
        import duckdb
    except ImportError as e:
        raise ImportError(
            "duckdb is required for mem. Install with: pip install duckdb"
        ) from e
    return duckdb


def _get_db_path() -> Path:
    """Get the memory database path, resolving relative to .onetool/ directory.

    Uses resolve_ot_path (not expand_path) so the default "mem.db" resolves
    against project .onetool/ first, then get_global_dir() which honours
    OT_GLOBAL_DIR. See agents/rules.md "Path Resolution".
    """
    from ot.meta import resolve_ot_path

    config = _get_config()
    db_path = resolve_ot_path(config.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


_WAL_CORRUPTION_INDICATORS = [
    "Failure while replaying WAL file",
    "BinderException",
    "Binder Error",
    "Cannot bind index",
]


def _is_wal_corruption_error(error_msg: str) -> bool:
    """Check if a DuckDB error indicates WAL corruption."""
    return any(indicator in error_msg for indicator in _WAL_CORRUPTION_INDICATORS)


def _handle_wal_corruption(db_path: Path) -> None:
    """Handle WAL corruption by backing up and removing the WAL file."""
    wal_path = db_path.with_suffix(".duckdb.wal")
    if wal_path.exists():
        backup_path = wal_path.with_suffix(".wal.corrupt")
        logger.warning("WAL corruption detected, backing up to %s", backup_path)
        shutil.copy2(wal_path, backup_path)
        wal_path.unlink()


def _get_connection() -> Any:
    """Get or create a read-write DuckDB connection with WAL handling.

    Uses a module-level connection with thread lock for safety.
    Follows ChunkHound patterns for WAL corruption detection and recovery.
    """
    global _connection
    with _connection_lock:
        if _connection is not None:
            try:
                _connection.execute("SELECT 1").fetchone()
                return _connection
            except Exception:
                _connection = None

        duckdb = _import_duckdb()
        db_path = _get_db_path()

        try:
            _connection = duckdb.connect(str(db_path), read_only=False)
        except Exception as e:
            if _is_wal_corruption_error(str(e)):
                _handle_wal_corruption(db_path)
                _connection = duckdb.connect(str(db_path), read_only=False)
            else:
                raise

        _ensure_tables(_connection)
        return _connection


@contextlib.contextmanager
def _use_connection() -> Generator[Any, None, None]:
    """Context manager that holds the connection lock for the entire operation.

    Ensures thread-safe access to the shared DuckDB connection.
    """
    conn = _get_connection()
    with _connection_lock:
        yield conn


def _has_column(conn: Any, table: str, column: str) -> bool:
    """Check if a column exists in a DuckDB table."""
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = ? AND column_name = ?",
        [table, column],
    ).fetchall()
    return len(rows) > 0


def _ensure_tables(conn: Any) -> None:
    """Create memory tables if they don't exist, then apply migrations."""
    config = _get_config()
    dim = config.dimensions

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS memories (
            id             VARCHAR PRIMARY KEY,
            topic          VARCHAR NOT NULL,
            content        TEXT NOT NULL,
            content_hash   VARCHAR NOT NULL,
            category       VARCHAR DEFAULT 'note',
            tags           VARCHAR[],
            relevance      INTEGER DEFAULT 5,
            access_count   INTEGER DEFAULT 0,
            created_at     TIMESTAMP DEFAULT now(),
            updated_at     TIMESTAMP DEFAULT now(),
            last_accessed  TIMESTAMP DEFAULT now(),
            embedding      FLOAT[{dim}],
            meta           MAP(VARCHAR, VARCHAR) DEFAULT MAP()
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
            id             VARCHAR PRIMARY KEY,
            memory_id      VARCHAR NOT NULL,
            content        TEXT NOT NULL,
            updated_at     TIMESTAMP DEFAULT now()
        )
    """)

    _migrate_tables(conn)


def _migrate_tables(conn: Any) -> None:
    """Apply schema migrations to existing tables.

    Each migration checks before applying so it is safe to call repeatedly.
    """
    # v2: add meta column for extensible key-value metadata
    if not _has_column(conn, "memories", "meta"):
        conn.execute("ALTER TABLE memories ADD COLUMN meta MAP(VARCHAR, VARCHAR) DEFAULT MAP()")


def _close_connection() -> None:
    """Close the module-level connection (for testing)."""
    global _connection
    with _connection_lock:
        if _connection is not None:
            with contextlib.suppress(Exception):
                _connection.close()
            _connection = None


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
# Matches ChunkHound's approach (openai_provider.py:607).
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
                conn = _get_connection()
                row = conn.execute(
                    "SELECT content FROM memories WHERE id = ?", [memory_id]
                ).fetchone()
                if not row:
                    break  # Memory was deleted before we got to it
                embedding = _generate_embedding(row[0])
                conn.execute(
                    "UPDATE memories SET embedding = ? WHERE id = ?",
                    [embedding, memory_id],
                )
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
                [memory_id, topic, content, content_hash, category, validated_tags, relevance, embedding, meta],
            )

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

                validated_path, error = _validate_file_path(str(f), must_exist=True)
                if error:
                    errors.append(f"{f.name}: {error}")
                    continue
                assert validated_path is not None

                # Preserve directory structure relative to glob root
                rel = f.relative_to(glob_root)
                # Strip extension and use path components as subtopic
                subtopic = f"{topic}/{rel.with_suffix('').as_posix()}"
                result = write(
                    topic=subtopic,
                    content=validated_path.read_text(encoding="utf-8"),
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
                "UPDATE memories SET access_count = access_count + 1, last_accessed = now() WHERE id = ?",
                [row[0]],
            )

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
    row_meta: dict[str, str] = dict(row[9]) if row[9] else {}

    if mode == "meta":
        lines = [
            f"Topic: {row[1]}",
            f"Category: {row[3]}",
            f"Tags: {', '.join(row[4]) if row[4] else 'none'}",
            f"Relevance: {row[5]}",
            f"Accessed: {row[6] + 1} times",
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
        f"Tags: {', '.join(row[4]) if row[4] else 'none'}\n"
        f"Relevance: {row[5]}\n"
        f"Accessed: {row[6] + 1} times\n"
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
                    sql += " AND list_has_any(tags, ?)"
                    params.append(tags)

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
                f"UPDATE memories SET access_count = access_count + 1, last_accessed = now() WHERE id IN ({placeholders})",
                row_ids,
            )

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

            row_meta: dict[str, str] = dict(row[9]) if row[9] else {}
            sections = _decode_sections(row_meta.get("sections", ""))
            result = _build_toc(sections, row[2])

            # Staleness detection
            source = row_meta.get("source")
            source_mtime = row_meta.get("source_mtime")
            if source and source_mtime:
                source_path = Path(source)
                if source_path.exists():
                    current_mtime = source_path.stat().st_mtime
                    if current_mtime > float(source_mtime):
                        result += "\n\nWarning: Source file has been modified since this memory was stored. Consider re-writing with mem.write()."
                else:
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
            row_meta: dict[str, str] = dict(row[9]) if row[9] else {}
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
        mode: Search mode - "semantic" (vector cosine), "pattern" (ILIKE), or "hybrid" (RRF)
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
            conn = _get_connection()

            if mode in ("semantic", "hybrid") and not config.embeddings_enabled:
                return "Semantic search requires embeddings. Enable with: tools.mem.embeddings_enabled: true"

            if mode in ("semantic", "hybrid"):
                has_embeddings = conn.execute(
                    "SELECT 1 FROM memories WHERE embedding IS NOT NULL LIMIT 1"
                ).fetchone()
                if not has_embeddings:
                    return "No embeddings found. Run mem.embed(dry_run=False) to generate them."

            if mode == "semantic":
                results = _search_semantic(conn, query, topic, category, tags, limit, config)
            elif mode == "pattern":
                results = _search_pattern(conn, query, topic, category, tags, limit)
            else:
                results = _search_hybrid(conn, query, topic, category, tags, limit, config)

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
    config: Config,
) -> list[dict[str, Any]]:
    """Semantic search using vector cosine similarity."""
    embedding = _generate_embedding(query)
    dim = config.dimensions

    sql = f"""
        SELECT id, topic, content, category, tags, relevance, access_count,
               array_cosine_similarity(embedding, ?::FLOAT[{dim}]) as score
        FROM memories
        WHERE embedding IS NOT NULL
    """
    params: list[Any] = [embedding]

    topic_sql, topic_params = _topic_filter(topic)
    sql += topic_sql
    params.extend(topic_params)

    if category:
        sql += " AND category = ?"
        params.append(category)

    if tags:
        sql += " AND list_has_any(tags, ?)"
        params.append(tags)

    sql += " ORDER BY score DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "id": r[0], "topic": r[1], "content": r[2], "category": r[3],
            "tags": r[4], "relevance": r[5], "access_count": r[6], "score": round(r[7], 4),
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
    """Pattern search using ILIKE matching."""
    sql = """
        SELECT id, topic, content, category, tags, relevance, access_count
        FROM memories
        WHERE (content ILIKE ? ESCAPE '\\' OR topic ILIKE ? ESCAPE '\\')
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
        sql += " AND list_has_any(tags, ?)"
        params.append(tags)

    sql += " ORDER BY relevance DESC, updated_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "id": r[0], "topic": r[1], "content": r[2], "category": r[3],
            "tags": r[4], "relevance": r[5], "access_count": r[6], "score": 1.0,
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
    config: Config,
) -> list[dict[str, Any]]:
    """Hybrid search combining semantic and pattern results via RRF.

    Uses Reciprocal Rank Fusion: rrf_score = sum(1 / (k + rank))
    """
    k = 60  # RRF constant

    # Get both result sets (fetch more than limit for better fusion)
    fetch_limit = limit * 3
    semantic_results = _search_semantic(conn, query, topic, category, tags, fetch_limit, config)
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
) -> str:
    """List memories with optional topic prefix and category filtering.

    Args:
        topic: Topic prefix filter (e.g., "projects/" lists all under projects)
        category: Filter by category
        limit: Maximum results (default: 50)

    Returns:
        Formatted list of memories.

    Example:
        mem.list()
        mem.list(topic="projects/onetool/")
        mem.list(category="rule")
    """
    with LogSpan(span="mem.list", topic=topic, category=category, limit=limit) as s:
        try:
            conn = _get_connection()

            sql = "SELECT id, topic, category, tags, relevance, access_count, created_at, length(content) as content_len FROM memories WHERE 1=1"
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
                return "No memories found"

            s.add("resultCount", len(rows))

            noun = "memory" if len(rows) == 1 else "memories"
            lines = [f"Found {len(rows)} {noun}:\n"]
            for r in rows:
                tags_str = ", ".join(r[3]) if r[3] else ""
                lines.append(
                    f"  {r[1]} [{r[2]}] rel={r[4]} accessed={r[5]}x len={r[7]}"
                    f"{' tags=' + tags_str if tags_str else ''}"
                    f" id={r[0][:8]}..."
                )
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
            existing_meta: dict[str, str] = dict(rows[0][2]) if rows[0][2] else {}

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
                SET content = ?, content_hash = ?, embedding = ?, meta = ?, updated_at = now()
                WHERE id = ?
                """,
                [content, new_hash, embedding, existing_meta, memory_id],
            )

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
            existing_meta: dict[str, str] = dict(row[2]) if row[2] else {}

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
                SET content = ?, content_hash = ?, embedding = ?, meta = ?, updated_at = now()
                WHERE id = ?
                """,
                [new_content, new_hash, embedding, existing_meta, memory_id],
            )

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
                f"UPDATE memories SET access_count = access_count + 1, last_accessed = now() WHERE id IN ({placeholders})",
                ids,
            )

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
            sql = "SELECT id, topic, content FROM memories WHERE content LIKE ? ESCAPE '\\'"
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

                # Save history
                history_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO memory_history (id, memory_id, content) VALUES (?, ?, ?)",
                    [history_id, memory_id, old_content],
                )

                new_content = old_content.replace(search_text, replace_text)
                new_hash = _content_hash(new_content)
                embedding = _maybe_embed(memory_id, new_content)

                conn.execute(
                    """
                    UPDATE memories
                    SET content = ?, content_hash = ?, embedding = ?, updated_at = now()
                    WHERE id = ?
                    """,
                    [new_content, new_hash, embedding, memory_id],
                )
                updated += 1

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
                memory_id, topic, relevance, access_count, created_at = r
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=UTC)
                age_days = (now - created_at).total_seconds() / 86400

                decay_factor = 0.5 ** (age_days / half_life)
                access_boost = 1 + math.log(access_count + 1) * 0.1
                decayed_score = relevance * decay_factor * access_boost
                new_relevance = max(1, min(10, round(decayed_score)))

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
                    CASE WHEN position('/' IN topic) > 0
                         THEN substring(topic, 1, position('/' IN topic) - 1)
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
                    [embedding, memory_id],
                )
                generated += 1

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
                       created_at, updated_at
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
        tags_str = "[" + ", ".join(f'"{t}"' for t in (r[4] or [])) + "]"
        # Use block scalar |- for content to safely handle newlines and special chars
        content_lines = r[2].split("\n")
        indented_content = "\n".join(f"      {line}" for line in content_lines)
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
                tags = mem_data.get("tags", [])
                relevance = max(1, min(10, int(mem_data.get("relevance", 5))))

                embedding = _maybe_embed(memory_id, content)

                conn.execute(
                    """
                    INSERT INTO memories (id, topic, content, content_hash, category, tags, relevance, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [memory_id, topic, content, content_hash, category, tags, relevance, embedding],
                )
                imported += 1

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
    ext: str = ".md",
    on_conflict: str = "skip",
) -> str:
    """Write memories to a directory as individual files with an index.yaml.

    Creates one file per memory record with an index.yaml containing metadata.
    Round-trips losslessly with `mem.restore()`.

    Args:
        output: Output directory path
        topic: Topic prefix filter (all memories if omitted)
        ext: File extension for content files (default: ".md")
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
                       created_at, updated_at
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
                _id, mem_topic, content, category, tags, relevance = (
                    r[0], r[1], r[2], r[3], r[4] or [], r[5],
                )

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
                index_lines.extend([
                    f'  - topic: "{entry["topic"]}"',
                    f'    file: "{entry["file"]}"',
                    f'    category: "{entry["category"]}"',
                    f"    tags: {tags_str}",
                    f'    relevance: {entry["relevance"]}',
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

            for entry in memories:
                mem_topic = entry.get("topic", "")
                file_rel = entry.get("file", "")
                category = entry.get("category", "note")
                tags = entry.get("tags", [])
                relevance = max(1, min(10, int(entry.get("relevance", 5))))

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

                conn = _get_connection()

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
                    INSERT INTO memories (id, topic, content, content_hash, category, tags, relevance, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [memory_id, mem_topic, content, content_hash, category, tags, relevance, embedding],
                )
                restored += 1

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
