"""Thread-safe lazy SQLite connection pool for a single shared connection.

Provides ``SqlitePool`` for managed shared connections and ``open_db_connection``
for background threads that need their own independent connection.

Example::

    def _setup(conn: sqlite3.Connection) -> None:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA synchronous=NORMAL")
        _ensure_schema(conn)

    _pool = SqlitePool(get_db_path, _setup)

    # Shared connection (health-checked, reconnects on failure):
    conn = _pool.get()

    # Managed context (holds lock for duration):
    with _pool.use() as conn:
        conn.execute("SELECT 1")

    # Background thread — fresh independent connection:
    bg_conn = open_db_connection(db_path, _setup)
"""

from __future__ import annotations

import contextlib
import sqlite3
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path

__all__ = ["SqlitePool", "open_db_connection"]


def _open_raw(
    path: Path, setup_fn: Callable[[sqlite3.Connection], None]
) -> sqlite3.Connection:
    """Open a SQLite connection with WAL + FK pragmas, then run setup_fn."""
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    setup_fn(conn)
    return conn


class SqlitePool:
    """Thread-safe lazy SQLite connection pool for a single shared connection.

    Args:
        path_fn: Callable that returns the database ``Path`` (called lazily on
            first access so the path can be resolved from runtime config).
        setup_fn: Callable that receives a freshly opened connection and applies
            pragmas, schema creation, migrations, and UDF registration.
    """

    def __init__(
        self,
        path_fn: Callable[[], Path],
        setup_fn: Callable[[sqlite3.Connection], None],
    ) -> None:
        self._path_fn = path_fn
        self._setup_fn = setup_fn
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None

    def get(self) -> sqlite3.Connection:
        """Get or create the shared connection.

        Health-checked with ``SELECT 1``; reconnects automatically if the
        connection is stale or was closed.

        Returns:
            The shared ``sqlite3.Connection``.
        """
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.execute("SELECT 1").fetchone()
                    return self._conn
                except Exception:
                    self._conn = None
            self._conn = _open_raw(self._path_fn(), self._setup_fn)
            return self._conn

    def close(self) -> None:
        """Close the shared connection (for testing or graceful shutdown)."""
        with self._lock:
            if self._conn is not None:
                with contextlib.suppress(Exception):
                    self._conn.close()
                self._conn = None

    @contextlib.contextmanager
    def use(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager that yields the shared connection under the lock.

        Yields:
            The shared ``sqlite3.Connection``.
        """
        conn = self.get()
        with self._lock:
            yield conn


def open_db_connection(
    path: Path, setup_fn: Callable[[sqlite3.Connection], None]
) -> sqlite3.Connection:
    """Open a fresh SQLite connection (not pooled).

    For background threads that need their own independent connection —
    open, use, and close it themselves.

    Args:
        path: Path to the SQLite database file.
        setup_fn: Callable applied to the new connection (pragmas, schema, UDFs).

    Returns:
        A new ``sqlite3.Connection``.
    """
    return _open_raw(path, setup_fn)
