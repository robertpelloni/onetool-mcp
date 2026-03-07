"""Management tools for the ctx pack: list, inspect, stats."""
from __future__ import annotations

import json
from typing import Any

from ot.logging import LogSpan

from .db import _get_connection, get_db_path, is_expired, ttl_remaining


def _meta_get(row: Any, key: str) -> Any:
    """Extract a key from the JSON meta column, returning None if missing."""
    raw = row.get("meta", None) if hasattr(row, "get") else row["meta"]
    if not raw:
        return None
    try:
        return json.loads(raw).get(key)
    except (json.JSONDecodeError, AttributeError):
        return None

log = LogSpan

_VALID_STATUSES = {"pending", "indexing", "ready", "failed"}


def ctx_list(
    *,
    source: str = "",
    status: str = "",
    db: Any = None,
) -> list[dict[str, Any]]:
    """Return all active (non-expired) handles with summary information.

    Args:
        source: Filter by source substring (case-insensitive)
        status: Filter by status ("pending", "indexing", "ready", "failed")
        db: SQLite connection
    """
    if status and status not in _VALID_STATUSES:
        raise ValueError(
            f"Invalid status {status!r}. Valid values: {', '.join(sorted(_VALID_STATUSES))}"
        )

    with log(span="ctx.list", source=source or None, status=status or None) as s:
        if db is None:
            db = _get_connection()

        rows = db.execute(
            "SELECT handle, source, size_bytes, total_lines, status, expires_at, meta "
            "FROM results "
            "WHERE (expires_at IS NULL OR expires_at > unixepoch()) "
            "AND (:status = '' OR status = :status) "
            "AND (:source = '' OR LOWER(source) LIKE '%' || LOWER(:source) || '%') "
            "ORDER BY rowid DESC",
            {"status": status, "source": source},
        ).fetchall()

        active = []
        for row in rows:
            if is_expired(row):  # safety net for sub-second races
                continue
            handle = row["handle"]
            entry: dict[str, Any] = {
                "handle": handle,
                "source": row["source"] or "",
                "size_bytes": row["size_bytes"],
                "total_lines": row["total_lines"],
                "status": row["status"],
                "abstract": _meta_get(row, "abstract"),
                "command": f"ctx.read('{handle}')",
                "ttl_remaining": int(ttl_remaining(row)),
            }
            active.append(entry)

        s.add("count", len(active))
        return active


def ctx_inspect(
    handle: str,
    *,
    db: Any = None,
) -> dict[str, Any]:
    """Return detailed metadata for a single handle.

    Args:
        handle: Context store handle
        db: SQLite connection
    """
    with log(span="ctx.inspect", handle=handle):
        if db is None:
            db = _get_connection()

        row = db.execute(
            "SELECT handle, source, size_bytes, total_lines, status, created_at, "
            "expires_at, access_count, is_file, meta FROM results WHERE handle=?",
            (handle,),
        ).fetchone()
        if row is None:
            return {"error": f"Handle not found: {handle}"}

        counts = db.execute(
            "SELECT"
            " (SELECT COUNT(*) FROM chunks WHERE handle=?) as chunk_count,"
            " (SELECT COUNT(*) FROM vocabulary WHERE handle=?) as vocab_size,"
            " (SELECT COUNT(*) FROM chunk_embeddings WHERE handle=?) as emb_count",
            (handle, handle, handle),
        ).fetchone()
        chunk_count = counts["chunk_count"]
        vocab_size = counts["vocab_size"]
        emb_count = counts["emb_count"]

        return {
            "handle": row["handle"],
            "source": row["source"] or "",
            "size_bytes": row["size_bytes"],
            "total_lines": row["total_lines"],
            "status": row["status"],
            "abstract": _meta_get(row, "abstract"),
            "created_at": row["created_at"],
            "access_count": row["access_count"],
            "is_file_pointer": bool(row["is_file"]),
            "chunk_count": chunk_count,
            "vocab_size": vocab_size,
            "has_embeddings": emb_count > 0,
            "ttl_remaining": int(ttl_remaining(row)),
        }


def ctx_stats(
    *,
    db: Any = None,
) -> dict[str, Any]:
    """Return session-level storage and savings metrics.

    Returns total_handles, handles_by_status, total_bytes_stored,
    estimated_tokens_saved, db_size_bytes.
    """
    with log(span="ctx.stats") as s:
        if db is None:
            db = _get_connection()

        rows = db.execute(
            "SELECT status, COUNT(*) as cnt, SUM(size_bytes) as total_bytes FROM results GROUP BY status"
        ).fetchall()

        handles_by_status: dict[str, int] = {}
        total_bytes = 0
        total_handles = 0

        for row in rows:
            handles_by_status[row["status"]] = row["cnt"]
            total_bytes += row["total_bytes"] or 0
            total_handles += row["cnt"]

        estimated_tokens_saved = total_bytes // 4

        # DB file size
        db_path = get_db_path()
        db_size = db_path.stat().st_size if db_path.exists() else 0

        s.add("total_handles", total_handles)
        s.add("total_bytes", total_bytes)
        return {
            "total_handles": total_handles,
            "handles_by_status": handles_by_status,
            "total_bytes_stored": total_bytes,
            "estimated_tokens_saved": estimated_tokens_saved,
            "db_size_bytes": db_size,
        }


__all__ = ["ctx_inspect", "ctx_list", "ctx_stats"]
