"""SQLite connection, schema, and TTL helpers for the ctx pack.

Database location: .onetool/sessions/<date>-<id>/ctx.db

Tables:
    results           - Handle metadata (status, source, TTL, etc.)
    content           - Raw content per handle (or file path if is_file=1)
    chunks            - FTS5 virtual table, porter tokenizer
    chunks_trigram    - FTS5 virtual table, trigram tokenizer
    vocabulary        - Top distinctive terms per handle (IDF-scored)
    chunk_embeddings  - Optional per-chunk float32 embeddings
"""
from __future__ import annotations

import contextlib
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

from ot.utils.sqlite_pool import SqlitePool, open_db_connection

# ---------------------------------------------------------------------------
# Setup function applied to every new connection
# ---------------------------------------------------------------------------


def _ctx_setup(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA synchronous=NORMAL")
    _ensure_schema(conn)
    _migration_guard(conn)


# ---------------------------------------------------------------------------
# Pool (shared connection) and public API
# ---------------------------------------------------------------------------


def get_db_path() -> Path:
    """Return path to ctx.db in the session directory, creating it as needed."""
    from ot.utils.session import get_session_dir

    db_path = get_session_dir() / "ctx.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


_pool = SqlitePool(get_db_path, _ctx_setup)


def _get_connection() -> sqlite3.Connection:
    """Get or create the shared connection."""
    return _pool.get()


def _close_connection() -> None:
    """Close the shared connection (for testing)."""
    _pool.close()


def use_connection() -> AbstractContextManager[sqlite3.Connection]:
    """Context manager that yields the shared connection."""
    return _pool.use()


def _open_connection(db_path: Path) -> sqlite3.Connection:
    """Open a fresh SQLite connection (for background threads)."""
    return open_db_connection(db_path, _ctx_setup)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create all tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS results (
            handle       TEXT PRIMARY KEY,
            source       TEXT DEFAULT '',
            size_bytes   INTEGER DEFAULT 0,
            total_lines  INTEGER DEFAULT 0,
            status       TEXT DEFAULT 'pending',
            created_at   REAL NOT NULL,
            expires_at   REAL,
            access_count INTEGER DEFAULT 0,
            is_file      INTEGER DEFAULT 0,
            meta         TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS content (
            handle TEXT PRIMARY KEY,
            body   TEXT NOT NULL,
            FOREIGN KEY (handle) REFERENCES results(handle) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS vocabulary (
            handle TEXT NOT NULL,
            term   TEXT NOT NULL,
            score  REAL DEFAULT 0.0,
            PRIMARY KEY (handle, term),
            FOREIGN KEY (handle) REFERENCES results(handle) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS chunk_embeddings (
            handle    TEXT NOT NULL,
            chunk_idx INTEGER NOT NULL,
            embedding BLOB,
            PRIMARY KEY (handle, chunk_idx),
            FOREIGN KEY (handle) REFERENCES results(handle) ON DELETE CASCADE
        );
    """)

    # FTS5 virtual tables (no FK support — deleted manually)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
            handle UNINDEXED,
            chunk_idx UNINDEXED,
            start_line UNINDEXED,
            end_line UNINDEXED,
            title,
            body,
            tokenize='porter ascii'
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_trigram USING fts5(
            handle UNINDEXED,
            chunk_idx UNINDEXED,
            start_line UNINDEXED,
            end_line UNINDEXED,
            title,
            body,
            tokenize='trigram'
        )
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Migration guard: mark stale 'indexing' rows as 'failed' on startup
# ---------------------------------------------------------------------------


def _migration_guard(conn: sqlite3.Connection) -> None:
    """Mark any handles stuck in 'indexing' status as 'failed'.

    Called once on connection open to clean up crash remnants.
    Also applies additive schema migrations (ALTER TABLE ADD COLUMN).
    """
    conn.execute(
        "UPDATE results SET status='failed' WHERE status='indexing'"
    )
    # Additive column migrations — safe to retry (ignored if column exists)
    with contextlib.suppress(Exception):
        conn.execute("ALTER TABLE results ADD COLUMN meta TEXT DEFAULT '{}'")
    conn.commit()


# ---------------------------------------------------------------------------
# TTL helpers
# ---------------------------------------------------------------------------


def now_ts() -> float:
    """Return current Unix timestamp."""
    return time.time()


def expires_at(ttl: int) -> float | None:
    """Return expiry timestamp, or None if TTL is 0 (no expiry)."""
    if ttl <= 0:
        return None
    return now_ts() + ttl


def is_expired(row: sqlite3.Row | dict[str, Any]) -> bool:
    """Return True if the handle has passed its TTL."""
    exp = row["expires_at"]
    if exp is None:
        return False
    return bool(now_ts() > exp)


def ttl_remaining(row: sqlite3.Row | dict[str, Any]) -> float:
    """Return remaining TTL in seconds (0 if no expiry or already expired)."""
    exp = row["expires_at"]
    if exp is None:
        return 0.0
    remaining = float(exp) - now_ts()
    return max(0.0, remaining)


# ---------------------------------------------------------------------------
# FTS5 cascade helpers (manual, since FTS5 has no FK support)
# ---------------------------------------------------------------------------


def delete_fts_for_handle(conn: sqlite3.Connection, handle: str) -> None:
    """Delete all FTS5 rows for a handle (both tables)."""
    conn.execute("DELETE FROM chunks WHERE handle = ?", (handle,))
    conn.execute("DELETE FROM chunks_trigram WHERE handle = ?", (handle,))


def get_content(conn: sqlite3.Connection, handle: str, *, is_file: int | None = None) -> str | None:
    """Return raw content for a handle, reading from file if is_file=1.

    Args:
        conn: SQLite connection.
        handle: Context store handle.
        is_file: Pass the ``is_file`` value from an already-fetched ``results``
            row to skip the second query. When ``None`` (default), the value is
            fetched from the database.
    """
    row = conn.execute(
        "SELECT body FROM content WHERE handle = ?", (handle,)
    ).fetchone()
    if row is None:
        return None

    # Resolve is_file if not provided by caller
    if is_file is None:
        meta = conn.execute(
            "SELECT is_file FROM results WHERE handle = ?", (handle,)
        ).fetchone()
        is_file = meta["is_file"] if meta else 0

    if is_file:
        try:
            return Path(row["body"]).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
    return str(row["body"])


__all__ = [
    "_close_connection",
    "_get_connection",
    "_open_connection",
    "delete_fts_for_handle",
    "expires_at",
    "get_content",
    "get_db_path",
    "is_expired",
    "now_ts",
    "ttl_remaining",
    "use_connection",
]
