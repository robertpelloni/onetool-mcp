"""Maintenance tools for the ctx pack: delete and purge."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ot.logging import LogSpan
from ot.utils.fs import unlink_tracking_bytes

from .db import _get_connection, delete_fts_for_handle, now_ts

log = LogSpan


# ---------------------------------------------------------------------------
# ctx_delete
# ---------------------------------------------------------------------------


def ctx_delete(
    handle: str,
    *,
    db: Any = None,
) -> dict[str, Any]:
    """Delete a single handle and all associated data.

    Also unlinks the backing file if is_file=1.
    """
    with log(span="ctx.delete", handle=handle):
        if db is None:
            db = _get_connection()

        row = db.execute(
            "SELECT is_file FROM results WHERE handle=?", (handle,)
        ).fetchone()
        if row is None:
            return {"error": f"Handle not found: {handle}"}

        # File pointer cleanup
        if row["is_file"]:
            body_row = db.execute("SELECT body FROM content WHERE handle=?", (handle,)).fetchone()
            if body_row:
                unlink_tracking_bytes(Path(body_row["body"]))

        # FTS5 manual cleanup (no FK support)
        delete_fts_for_handle(db, handle)

        # CASCADE deletes content, vocabulary, chunk_embeddings
        db.execute("DELETE FROM results WHERE handle=?", (handle,))
        db.commit()

        # Remove threading.Event
        from .write import _remove_event
        _remove_event(handle)

        return {"deleted": handle}


# ---------------------------------------------------------------------------
# ctx_purge
# ---------------------------------------------------------------------------


def ctx_purge(
    *,
    all: bool = False,
    minutes: int = 15,
    source: str = "",
    status: str = "",
    db: Any = None,
) -> dict[str, Any]:
    """Delete handles and compact the database.

    With no filters: deletes handles older than ``minutes`` (default 15), then compacts.
    With ``all=True``: ignores the age filter — deletes every handle that matches the
    ``source``/``status`` filters (or all handles when no filters are given).
    With ``source``/``status``: bulk-deletes matching handles older than ``minutes``.

    Args:
        all: If True, bypass the age filter. Source/status filters still apply.
        minutes: Delete handles older than this many minutes. Must be positive.
            Ignored when ``all=True``.
        source: Source substring filter (case-insensitive).
        status: Status filter ("pending", "indexing", "ready", "failed").
        db: SQLite connection (uses module default if not provided).

    Returns:
        Dict with "deleted" (handle count) and "bytes_freed" (content bytes removed).

    Raises:
        ValueError: If ``minutes`` is zero or negative.

    Examples:
        ctx.purge()                          # delete handles older than 15 min + compact
        ctx.purge(all=True)                  # wipe everything
        ctx.purge(minutes=60)                # delete handles older than 1 hour
        ctx.purge(source="brave")            # delete brave handles older than 15 min
        ctx.purge(all=True, source="brave")  # delete ALL brave handles regardless of age
        ctx.purge(status="failed")           # delete failed handles older than 15 min
        ctx.purge(all=True, status="failed") # delete ALL failed handles regardless of age
    """
    if not all and minutes <= 0:
        raise ValueError("minutes must be a positive integer")

    with log(
        span="ctx.purge",
        all=all or None,
        minutes=minutes if not all else None,
        source=source or None,
        status=status or None,
    ) as s:
        if db is None:
            db = _get_connection()

        # -- Determine which handles to delete -----------------------------------

        cutoff_ts = None if all else (now_ts() - minutes * 60)

        rows = db.execute(
            "SELECT handle, source, status, created_at, is_file, size_bytes FROM results"
        ).fetchall()

        to_delete = []
        for row in rows:
            if cutoff_ts is not None and row["created_at"] > cutoff_ts:
                continue
            if source and source.lower() not in (row["source"] or "").lower():
                continue
            if status and row["status"] != status:
                continue
            to_delete.append(row)

        bytes_freed = sum(row["size_bytes"] or 0 for row in to_delete)

        from .write import _remove_event
        for row in to_delete:
            handle = row["handle"]
            if row["is_file"]:
                body_row = db.execute("SELECT body FROM content WHERE handle=?", (handle,)).fetchone()
                if body_row:
                    unlink_tracking_bytes(Path(body_row["body"]))
            delete_fts_for_handle(db, handle)
            db.execute("DELETE FROM results WHERE handle=?", (handle,))
            _remove_event(handle)

        db.commit()
        deleted = len(to_delete)

        # Always compact after deletion
        db.execute("VACUUM")

        s.add("deleted", deleted)
        s.add("bytes_freed", bytes_freed)
        return {"deleted": deleted, "bytes_freed": bytes_freed}


__all__ = [
    "ctx_delete",
    "ctx_purge",
]
