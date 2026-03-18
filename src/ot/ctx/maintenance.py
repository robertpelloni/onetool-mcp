"""Maintenance tools for the ctx pack: delete and purge."""
from __future__ import annotations

from typing import Any

from ot.logging import LogSpan

from .store import HandleStore, _get_store, _resolve_handle, now_ts

log = LogSpan


def ctx_delete(
    handle: str,
    *,
    store: HandleStore | None = None,
) -> dict[str, Any]:
    """Delete a single handle and both associated files.

    Args:
        handle: Context store handle to delete.
        store: HandleStore instance (uses session default if not provided).
    """
    with log(span="ctx.delete", handle=handle):
        if store is None:
            store = _get_store()

        try:
            handle = _resolve_handle(handle)
        except TypeError as e:
            return {"error": str(e)}

        if not store.exists(handle):
            return {"error": f"Handle not found: {handle}"}

        store.delete(handle)
        return {"deleted": handle}


def ctx_purge(
    *,
    delete_all: bool = False,
    minutes: int = 15,
    source: str = "",
    status: str = "",
    store: HandleStore | None = None,
) -> dict[str, Any]:
    """Delete handles matching the given filters.

    With no filters: deletes handles older than ``minutes`` (default 15).
    With ``delete_all=True``: ignores the age filter — deletes every handle
    that matches the ``source``/``status`` filters (or all handles when no
    filters are given).
    With ``source``/``status``: bulk-deletes matching handles older than
    ``minutes``.

    Args:
        delete_all: If True, bypass the age filter. Source/status filters still apply.
        minutes: Delete handles older than this many minutes. Must be positive.
            Ignored when ``delete_all=True``.
        source: Source substring filter (case-insensitive).
        status: Status filter ("ready", "failed").
        store: HandleStore instance (uses session default if not provided).

    Returns:
        Dict with "deleted" (handle count) and "bytes_freed" (content bytes removed).

    Raises:
        ValueError: If ``minutes`` is zero or negative.

    Examples:
        ctx.purge()                                 # delete handles older than 15 min
        ctx.purge(delete_all=True)                  # wipe everything
        ctx.purge(minutes=60)                       # delete handles older than 1 hour
        ctx.purge(source="brave")                   # delete brave handles older than 15 min
        ctx.purge(delete_all=True, source="brave")  # delete ALL brave handles regardless of age
        ctx.purge(status="failed")                  # delete failed handles older than 15 min
        ctx.purge(delete_all=True, status="failed") # delete ALL failed handles regardless of age
    """
    if not delete_all and minutes <= 0:
        raise ValueError("minutes must be a positive integer")

    with log(
        span="ctx.purge",
        delete_all=delete_all or None,
        minutes=minutes if not delete_all else None,
        source=source or None,
        status=status or None,
    ) as s:
        if store is None:
            store = _get_store()

        cutoff_ts = None if delete_all else (now_ts() - minutes * 60)
        all_meta = store.list_handles()

        to_delete: list[dict[str, Any]] = []
        for meta in all_meta:
            if cutoff_ts is not None and meta.get("created_at", 0) > cutoff_ts:
                continue
            if source and source.lower() not in (meta.get("source") or "").lower():
                continue
            if status and meta.get("status") != status:
                continue
            to_delete.append(meta)

        bytes_freed = sum(m.get("size_bytes", 0) for m in to_delete)
        deleted = 0

        for meta in to_delete:
            handle = meta["handle"]
            store.delete(handle)
            deleted += 1

        s.add("deleted", deleted)
        s.add("bytes_freed", bytes_freed)
        return {"deleted": deleted, "bytes_freed": bytes_freed}


__all__ = ["ctx_delete", "ctx_purge"]
