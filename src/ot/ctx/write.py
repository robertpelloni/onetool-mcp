"""Write and append operations for the ctx pack."""
from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

from ot.logging import LogSpan

from .chunking import _has_markdown_headings
from .config import Config, _get_config
from .db import (
    _get_connection,
    _open_connection,
    expires_at,
    get_db_path,
    now_ts,
)

log = LogSpan

# ---------------------------------------------------------------------------
# threading.Event registry: handle → Event signalled when indexing completes
# ---------------------------------------------------------------------------

_events: dict[str, threading.Event] = {}
_events_lock = threading.Lock()


def _get_event(handle: str) -> threading.Event:
    """Get or create a threading.Event for a handle."""
    with _events_lock:
        if handle not in _events:
            _events[handle] = threading.Event()
        return _events[handle]


def _set_event(handle: str) -> None:
    """Signal the event for a handle (indexing done or failed)."""
    with _events_lock:
        ev = _events.get(handle)
    if ev is not None:
        ev.set()


def _remove_event(handle: str) -> None:
    """Remove event from registry (on delete/flush)."""
    with _events_lock:
        _events.pop(handle, None)


# ---------------------------------------------------------------------------
# Abstract generation (synchronous)
# ---------------------------------------------------------------------------

_ABSTRACT_PROMPT = (
    "In 1-2 sentences, describe what this content is about. "
    "Be specific: name the subject, tool, topic, or purpose. "
    "Do not start with 'This content' or 'This document'."
)
_ABSTRACT_PREVIEW_BYTES = 4000
_ABSTRACT_FALLBACK_CHARS = 500


def _generate_abstract(content: str) -> str:
    """Return a short abstract: LLM-generated if available, else first 500 chars."""
    try:
        from ottools.ot_llm import transform as llm_transform

        result = llm_transform(data=content[:_ABSTRACT_PREVIEW_BYTES], prompt=_ABSTRACT_PROMPT)
        if isinstance(result, str) and result.strip():
            return result.strip()
    except Exception:
        pass
    # Fallback: first 500 chars, truncated at last whitespace boundary
    raw = content[:_ABSTRACT_FALLBACK_CHARS].strip()
    if len(content) > _ABSTRACT_FALLBACK_CHARS:
        boundary = raw.rfind(" ")
        if boundary > 0:
            raw = raw[:boundary]
        raw += "…"
    return raw


# ---------------------------------------------------------------------------
# Background indexing thread
# ---------------------------------------------------------------------------


def _indexing_worker(
    handle: str,
    content: str,
    db_path: Path,
    embedding_model: str,
) -> None:
    """Background thread: build FTS5 index and vocabulary."""
    from .indexing import build_index

    conn = _open_connection(db_path)
    try:
        build_index(handle, content, conn, embedding_model=embedding_model)
    except Exception:
        pass  # status already set to 'failed' inside build_index
    finally:
        conn.close()
        _set_event(handle)


# ---------------------------------------------------------------------------
# ctx_write
# ---------------------------------------------------------------------------


def ctx_write(
    content: str,
    *,
    source: str = "",
    intent: str = "",
    db: Any = None,
    config: Config | None = None,
) -> dict[str, Any]:
    """Write content to the context store and begin background indexing.

    Returns a handle + preview in ~1ms. Indexing runs asynchronously.

    Args:
        content: Text content to store.
        source: Optional label for the content origin (e.g. tool name or URL).
        intent: Optional extraction prompt. When non-empty, ``ot_llm`` is called
            immediately to synthesise a focused answer from ``content``. The
            response dict will include an ``"answer"`` key (str) on success, or
            ``"answer_error"`` (str) if ``ot_llm`` is not installed or fails.
        db: SQLite connection (uses module default if not provided).
        config: Pack config (uses module default if not provided).
    """
    with log(span="ctx.write", source=source or None) as s:
        if config is None:
            config = _get_config()
        if db is None:
            db = _get_connection()

        handle = uuid.uuid4().hex[:8]
        size_bytes = len(content.encode("utf-8"))
        lines = content.splitlines()
        total_lines = len(lines)
        content_type = "markdown" if _has_markdown_headings(lines) else "text"
        created = now_ts()
        exp = expires_at(config.ttl)

        # Determine if content should be stored as a file pointer
        is_file = 0
        body = content
        if size_bytes > config.max_inline_bytes:
            # Store to file
            store_path = get_db_path().parent / f"ctx-{handle}.txt"
            store_path.write_text(content, encoding="utf-8")
            body = str(store_path)
            is_file = 1

        # Insert results row
        db.execute(
            """INSERT INTO results(handle, source, size_bytes, total_lines, status,
                                   created_at, expires_at, is_file)
               VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)""",
            (handle, source, size_bytes, total_lines, created, exp, is_file),
        )
        # Insert content row
        db.execute(
            "INSERT INTO content(handle, body) VALUES (?, ?)",
            (handle, body),
        )
        db.commit()

        # Generate abstract synchronously (LLM if available, else first 500 chars)
        abstract = _generate_abstract(content)
        db.execute(
            "UPDATE results SET meta=json_set(COALESCE(meta, '{}'), '$.abstract', ?) WHERE handle=?",
            (abstract, handle),
        )
        db.commit()

        # Create event (initially unset)
        _get_event(handle)

        # Spawn daemon indexing thread
        db_path = get_db_path()
        thread = threading.Thread(
            target=_indexing_worker,
            args=(handle, content, db_path, config.embedding_model),
            daemon=True,
        )
        thread.start()

        # Preview: first 5 non-empty lines
        preview = [ln for ln in lines if ln.strip()][:5]

        result: dict[str, Any] = {
            "handle": handle,
            "source": source,
            "size_bytes": size_bytes,
            "total_lines": total_lines,
            "content_type": content_type,
            "abstract": abstract,
            "preview": preview,
            "status": "pending",
            "usage": {
                "page": f"ctx.read('{handle}')",
                "search": f"ctx.search('{handle}', queries=['your query'])",
                "toc": f"ctx.toc('{handle}')",
                "grep": f"ctx.grep('{handle}', pattern='pattern')",
                "tail": f"ctx.read('{handle}', tail=20)",
            },
        }

        # Intent fast-path: call ot_llm if intent given
        if intent:
            result.update(_run_intent(content, intent))

        s.add("handle", handle)
        s.add("size_bytes", size_bytes)
        s.add("total_lines", total_lines)
        return result


def _run_intent(content: str, intent: str) -> dict[str, Any]:
    """Call ot_llm.transform for the intent fast-path."""
    try:
        from ottools.ot_llm import transform as llm_transform

        answer = llm_transform(data=content, prompt=intent)
        return {"answer": answer}
    except ImportError:
        return {"answer_error": "ot_llm is not installed; install the ot_llm pack to use intent"}
    except Exception as e:
        return {"answer_error": f"ot_llm transform failed: {e}"}


# ---------------------------------------------------------------------------
# ctx_append
# ---------------------------------------------------------------------------


def ctx_append(
    handle: str,
    content: str,
    *,
    db: Any = None,
    config: Config | None = None,
) -> dict[str, Any]:
    """Append content to an existing handle and re-trigger indexing.

    Args:
        handle: Context store handle to append to.
        content: Text content to append. Concatenated to existing body.
        db: SQLite connection (uses module default if not provided).
        config: Pack config (uses module default if not provided).
    """
    with log(span="ctx.append", handle=handle) as s:
        if config is None:
            config = _get_config()
        if db is None:
            db = _get_connection()

        row = db.execute(
            "SELECT handle, is_file, size_bytes FROM results WHERE handle=?",
            (handle,),
        ).fetchone()
        if row is None:
            return {"error": f"Handle not found: {handle}"}

        existing_body_row = db.execute(
            "SELECT body FROM content WHERE handle=?", (handle,)
        ).fetchone()
        if existing_body_row is None:
            return {"error": f"Content not found for handle: {handle}"}

        # Load existing content
        if row["is_file"]:
            try:
                existing = Path(existing_body_row["body"]).read_text(encoding="utf-8")
            except OSError:
                existing = ""
        else:
            existing = existing_body_row["body"]

        combined = existing + "\n" + content
        new_size = len(combined.encode("utf-8"))
        new_lines = len(combined.splitlines())

        # Determine if file pointer needed
        is_file = 0
        new_body = combined
        if new_size > config.max_inline_bytes:
            store_path = get_db_path().parent / f"ctx-{handle}.txt"
            store_path.write_text(combined, encoding="utf-8")
            new_body = str(store_path)
            is_file = 1

        # Update content and reset status
        db.execute(
            "UPDATE content SET body=? WHERE handle=?", (new_body, handle)
        )
        db.execute(
            "UPDATE results SET size_bytes=?, total_lines=?, status='pending', is_file=? WHERE handle=?",
            (new_size, new_lines, is_file, handle),
        )
        db.commit()

        # Regenerate abstract synchronously (content changed)
        abstract = _generate_abstract(combined)
        db.execute(
            "UPDATE results SET meta=json_set(COALESCE(meta, '{}'), '$.abstract', ?) WHERE handle=?",
            (abstract, handle),
        )
        db.commit()

        # Reset event (clear old signal)
        with _events_lock:
            ev = _events.get(handle)
        if ev is not None:
            ev.clear()
        else:
            _get_event(handle)

        # Respawn indexing thread
        db_path = get_db_path()
        thread = threading.Thread(
            target=_indexing_worker,
            args=(handle, combined, db_path, config.embedding_model),
            daemon=True,
        )
        thread.start()

        s.add("size_bytes", new_size)
        s.add("total_lines", new_lines)
        return {
            "handle": handle,
            "status": "pending",
            "abstract": abstract,
            "size_bytes": new_size,
            "total_lines": new_lines,
        }


__all__ = [
    "ctx_append",
    "ctx_write",
]
