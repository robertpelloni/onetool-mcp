"""Persistent memory for AI agents with DuckDB storage and OpenAI embeddings.

Provides topic-based memory storage with semantic search, content dedup,
secret redaction, and importance decay. Requires OPENAI_API_KEY in secrets.yaml.

Thread safety: Uses a shared DuckDB connection. Concurrent calls from multiple
threads should use _use_connection() to hold the lock for the full operation.
MCP tool dispatch is single-threaded so this is safe in normal usage.

Reference: ChunkHound connection patterns, code_search.py embedding patterns.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import math
import re
import shutil
import threading
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
    "export",
    "list_memories",
    "load",
    "read",
    "read_batch",
    "search",
    "stats",
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
    ],
    "secrets": ["OPENAI_API_KEY"],
}

from pydantic import BaseModel, Field

from ot.config import get_tool_config
from ot.config.secrets import get_secret
from ot.logging import LogSpan
from ot.paths import expand_path
from ot.utils.pathsec import DEFAULT_EXCLUDE_PATTERNS, validate_path

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import ModuleType

    from openai import OpenAI

logger = logging.getLogger(__name__)

# Thread lock for connection operations
_connection_lock = threading.RLock()
_connection: Any = None

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
        default="~/.onetool/mem.db",
        description="Path to memory DuckDB database",
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
    """Get the memory database path, expanding ~ and creating parent dirs."""
    config = _get_config()
    db_path = expand_path(config.db_path)
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


def _ensure_tables(conn: Any) -> None:
    """Create memory tables if they don't exist."""
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
            embedding      FLOAT[{dim}]
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


def _close_connection() -> None:
    """Close the module-level connection (for testing)."""
    global _connection
    with _connection_lock:
        if _connection is not None:
            import contextlib

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


def _generate_embedding(text: str) -> list[float]:
    """Generate embedding vector for text."""
    config = _get_config()
    with LogSpan(span="mem.embedding", model=config.model, textLen=len(text)) as span:
        client = _get_openai_client()
        response = client.embeddings.create(
            model=config.model,
            input=text,
        )
        span.add("dimensions", len(response.data[0].embedding))
        return response.data[0].embedding


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

    Returns:
        Confirmation message with memory ID, or error message.

    Example:
        mem.write(topic="projects/onetool/rules", content="Always use keyword-only args")
        mem.write(topic="learnings/python", content="Use __future__ annotations", category="discovery")
        mem.write(topic="config", file="~/.onetool/config/onetool.yaml")
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

            if file:
                validated_path, error = _validate_file_path(file, must_exist=True)
                if error:
                    s.add("error", "path_validation")
                    return f"Error: {error}"
                assert validated_path is not None
                file_size = validated_path.stat().st_size
                if file_size > 1_000_000:
                    s.add("error", "file_too_large")
                    return f"Error: File too large ({file_size / 1_000_000:.1f}MB). Max 1MB for memory content."
                content = validated_path.read_text(encoding="utf-8")

            content = _redact(content)
            content_hash = _content_hash(content)

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
            embedding = _generate_embedding(content)

            conn.execute(
                """
                INSERT INTO memories (id, topic, content, content_hash, category, tags, relevance, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [memory_id, topic, content, content_hash, category, validated_tags, relevance, embedding],
            )

            s.add("memoryId", memory_id)
            s.add("contentLen", len(content))
            return f"Stored memory {memory_id} in topic '{topic}'"

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

    Returns:
        Summary of stored memories.

    Example:
        mem.write_batch(topic="docs", glob_pattern="docs/**/*.md", category="context")
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


def read(
    *,
    topic: str,
    id: str | None = None,
    meta: bool = False,
) -> str:
    """Read a memory by exact topic match or ID.

    Increments the access count on each read.

    Args:
        topic: Exact topic path to read
        id: Optional memory ID for direct lookup (overrides topic match)
        meta: If True, include metadata header (topic, category, tags, etc.)

    Returns:
        Memory content (with metadata header if meta=True), or error if not found.

    Example:
        mem.read(topic="projects/onetool/rules")
        mem.read(topic="projects/onetool/rules", meta=True)
        mem.read(id="abc-123-def")
    """
    with LogSpan(span="mem.read", topic=topic) as s:
        try:
            conn = _get_connection()

            if id:
                row = conn.execute(
                    "SELECT id, topic, content, category, tags, relevance, access_count, created_at, updated_at FROM memories WHERE id = ?",
                    [id],
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT id, topic, content, category, tags, relevance, access_count, created_at, updated_at FROM memories WHERE topic = ?",
                    [topic],
                ).fetchone()

            if not row:
                s.add("found", False)
                return f"No memory found for topic '{topic}'" if not id else f"No memory found with id '{id}'"

            # Increment access count
            conn.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed = now() WHERE id = ?",
                [row[0]],
            )

            s.add("found", True)
            s.add("memoryId", row[0])

            if not meta:
                return row[2]

            return (
                f"Topic: {row[1]}\n"
                f"Category: {row[3]}\n"
                f"Tags: {', '.join(row[4]) if row[4] else 'none'}\n"
                f"Relevance: {row[5]}\n"
                f"Accessed: {row[6] + 1} times\n"
                f"Created: {row[7]}\n"
                f"Updated: {row[8]}\n"
                f"ID: {row[0]}\n"
                f"\n{row[2]}"
            )

        except Exception as e:
            s.add("error", str(e))
            return f"Error reading memory: {e}"


def read_batch(
    *,
    topic: str | None = None,
    ids: list[str] | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    meta: bool = False,
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
        limit: Maximum results (default: 50)

    Returns:
        Concatenated memory contents separated by dividers, or error.

    Example:
        mem.read_batch(topic="projects/onetool/agents/")
        mem.read_batch(ids=["abc-123", "def-456"], meta=True)
        mem.read_batch(category="rule", limit=10)
    """
    if not any([topic, ids, category, tags]):
        return "Error: At least one filter (topic, ids, category, or tags) is required"

    if ids and any([topic, category, tags]):
        return "Error: ids cannot be combined with other filters (topic, category, tags)"

    with LogSpan(span="mem.read_batch", topic=topic, limit=limit) as s:
        try:
            conn = _get_connection()

            if ids:
                placeholders = ", ".join("?" for _ in ids)
                sql = f"SELECT id, topic, content, category, tags, relevance, access_count, created_at, updated_at FROM memories WHERE id IN ({placeholders})"
                params: list[Any] = list(ids)
            else:
                sql = "SELECT id, topic, content, category, tags, relevance, access_count, created_at, updated_at FROM memories WHERE 1=1"
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
                if meta:
                    parts.append(
                        f"Topic: {row[1]}\n"
                        f"Category: {row[3]}\n"
                        f"Tags: {', '.join(row[4]) if row[4] else 'none'}\n"
                        f"Relevance: {row[5]}\n"
                        f"Accessed: {row[6] + 1} times\n"
                        f"Created: {row[7]}\n"
                        f"Updated: {row[8]}\n"
                        f"ID: {row[0]}\n"
                        f"\n{row[2]}"
                    )
                else:
                    parts.append(f"# {row[1]}\n\n{row[2]}")

            noun = "memory" if len(rows) == 1 else "memories"
            return f"Read {len(rows)} {noun}\n\n---\n\n" + "\n\n---\n\n".join(parts)

        except Exception as e:
            s.add("error", str(e))
            return f"Error reading memories: {e}"


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
        WHERE (content ILIKE ? OR topic ILIKE ?)
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


def list_memories(
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
        mem.list_memories()
        mem.list_memories(topic="projects/onetool/")
        mem.list_memories(category="rule")
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
                    "SELECT id, content FROM memories WHERE id = ?", [id]
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, content FROM memories WHERE topic = ?", [topic]
                ).fetchall()

            if not rows:
                s.add("error", "not_found")
                return f"No memory found for topic '{topic}'" if not id else f"No memory found with id '{id}'"

            if len(rows) > 1:
                s.add("error", "multiple_matches")
                return f"Multiple memories ({len(rows)}) match topic '{topic}'. Use id= for specific update."

            memory_id = rows[0][0]
            old_content = rows[0][1]

            # Save history
            history_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO memory_history (id, memory_id, content) VALUES (?, ?, ?)",
                [history_id, memory_id, old_content],
            )

            # Redact and update
            content = _redact(content)
            new_hash = _content_hash(content)
            embedding = _generate_embedding(content)

            conn.execute(
                """
                UPDATE memories
                SET content = ?, content_hash = ?, embedding = ?, updated_at = now()
                WHERE id = ?
                """,
                [content, new_hash, embedding, memory_id],
            )

            s.add("memoryId", memory_id)
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
                    "SELECT id, content FROM memories WHERE id = ?", [id]
                ).fetchone()
            else:
                rows = conn.execute(
                    "SELECT id, content FROM memories WHERE topic = ?", [topic]
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

            # Save history
            history_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO memory_history (id, memory_id, content) VALUES (?, ?, ?)",
                [history_id, memory_id, old_content],
            )

            new_content = old_content + separator + _redact(content)
            new_hash = _content_hash(new_content)
            embedding = _generate_embedding(new_content)

            conn.execute(
                """
                UPDATE memories
                SET content = ?, content_hash = ?, embedding = ?, updated_at = now()
                WHERE id = ?
                """,
                [new_content, new_hash, embedding, memory_id],
            )

            s.add("memoryId", memory_id)
            s.add("newLen", len(new_content))
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

            sql = "SELECT id, topic, content FROM memories WHERE content LIKE ?"
            params: list[Any] = [f"%{search_text}%"]

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
                embedding = _generate_embedding(new_content)

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

            s.add("total", total)

            lines = [
                "Memory Statistics:\n",
                f"  Total memories: {total}",
                f"  History entries: {history_count}",
                f"  Total content: {size_stats[0]:,} chars",
                f"  Avg content: {int(size_stats[1]):,} chars",
                f"  Max content: {size_stats[2]:,} chars",
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


def export(
    *,
    format: str = "yaml",
    topic: str | None = None,
    output: str | None = None,
) -> str:
    """Export memories to YAML or Markdown format.

    Args:
        format: Output format - "yaml" or "markdown"
        topic: Optional topic prefix filter
        output: Output file path (default: prints to stdout)

    Returns:
        Exported content or file path confirmation.

    Example:
        mem.export(format="yaml", output="memories.yaml")
        mem.export(format="markdown", topic="projects/onetool/")
    """
    if format not in ("yaml", "markdown"):
        return f"Error: Invalid format '{format}'. Must be 'yaml' or 'markdown'"

    with LogSpan(span="mem.export", format=format, topic=topic) as s:
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

            content = _export_yaml(rows) if format == "yaml" else _export_markdown(rows)

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


def _export_markdown(rows: list[tuple]) -> str:
    """Export memories to Markdown format."""
    lines = ["# Memory Export\n"]
    current_topic = None

    for r in rows:
        topic = r[1]
        if topic != current_topic:
            lines.append(f"\n## {topic}\n")
            current_topic = topic

        tags_str = ", ".join(r[4]) if r[4] else "none"
        lines.extend([
            f"### {r[3]} (relevance: {r[5]})",
            f"*Tags: {tags_str} | Accessed: {r[6]}x | ID: {r[0]}*\n",
            r[2],
            "",
        ])
    return "\n".join(lines)


def load(
    *,
    file: str,
    overwrite: bool = False,
) -> str:
    """Import memories from a YAML file.

    Args:
        file: Path to YAML file to import
        overwrite: If True, overwrite existing memories with same topic+hash

    Returns:
        Import summary.

    Example:
        mem.load(file="memories.yaml")
        mem.load(file="backup.yaml", overwrite=True)
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

                if existing and not overwrite:
                    skipped += 1
                    continue

                if existing and overwrite:
                    conn.execute("DELETE FROM memories WHERE id = ?", [existing[0]])

                memory_id = mem_data.get("id", str(uuid.uuid4()))
                category = mem_data.get("category", "note")
                tags = mem_data.get("tags", [])
                relevance = max(1, min(10, int(mem_data.get("relevance", 5))))

                embedding = _generate_embedding(content)

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
            return f"Imported {imported} memories, skipped {skipped}"

        except ImportError as e:
            return f"Error: {e}"
        except Exception as e:
            s.add("error", str(e))
            return f"Error importing memories: {e}"
