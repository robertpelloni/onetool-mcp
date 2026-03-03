"""Read and TOC operations for the ctx pack."""
from __future__ import annotations

import re
from typing import Any

from ot.logging import LogSpan

from .db import _get_connection, get_content, is_expired

log = LogSpan

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)")


def ctx_read(
    handle: str,
    *,
    offset: int = 1,
    limit: int = 100,
    tail: int = 0,
    mode: str = "",
    db: Any = None,
) -> dict[str, Any]:
    """Return paginated raw content from a stored handle.

    Args:
        handle: Context store handle
        offset: 1-indexed starting line (default 1)
        limit: Max lines to return (default 100)
        tail: Return last N lines, overrides offset/limit
        mode: "toc" → return table of contents; "meta" → return metadata
        db: SQLite connection (uses shared connection if None)
    """
    with log(span="ctx.read", handle=handle, mode=mode or None) as s:
        if db is None:
            db = _get_connection()

        # Validate args
        if offset < 1:
            return {"error": f"offset must be >= 1 (1-indexed), got {offset}"}
        if limit < 1:
            return {"error": f"limit must be >= 1, got {limit}"}

        row = db.execute(
            "SELECT handle, source, size_bytes, total_lines, status, created_at, "
            "expires_at, access_count, is_file FROM results WHERE handle=?",
            (handle,),
        ).fetchone()

        if row is None:
            return {"error": f"Handle not found: {handle}"}

        if is_expired(row):
            return {"error": f"Handle has expired: {handle}"}

        # Increment access_count
        db.execute(
            "UPDATE results SET access_count = access_count + 1 WHERE handle=?",
            (handle,),
        )
        db.commit()

        # mode=meta
        if mode == "meta":
            from .db import ttl_remaining
            return {
                "handle": row["handle"],
                "source": row["source"],
                "size_bytes": row["size_bytes"],
                "total_lines": row["total_lines"],
                "status": row["status"],
                "created_at": row["created_at"],
                "access_count": row["access_count"] + 1,
                "ttl_remaining": int(ttl_remaining(row)),
            }

        # mode=toc
        if mode == "toc":
            return ctx_toc(handle, db=db)

        # Unknown mode
        if mode:
            return {"error": f"Invalid mode {mode!r}. Valid modes: 'toc', 'meta'"}

        # Raw content
        content = get_content(db, handle)
        if content is None:
            return {"error": f"Content not found for handle: {handle}"}

        lines = content.splitlines()
        total_lines = len(lines)

        if tail > 0:
            # tail overrides offset/limit
            actual_limit = min(tail, total_lines)
            start_idx = max(0, total_lines - actual_limit)
            end_idx = total_lines
            offset = start_idx + 1
            limit = actual_limit
        else:
            start_idx = offset - 1
            end_idx = start_idx + limit

        result_lines = lines[start_idx:end_idx]
        returned = len(result_lines)
        has_more = end_idx < total_lines
        end_line = offset + returned - 1
        if total_lines == 0:
            progress = "empty (0 lines)"
        else:
            pct = int((end_line / total_lines) * 100)
            progress = f"lines {offset}-{end_line} of {total_lines} ({pct}%)"

        result: dict[str, Any] = {
            "lines": result_lines,
            "total_lines": total_lines,
            "returned": returned,
            "offset": offset,
            "has_more": has_more,
            "progress": progress,
            "total_size_bytes": row["size_bytes"],
        }
        if has_more:
            next_offset = offset + returned
            result["next_query"] = f"ctx.read('{handle}', offset={next_offset}, limit={limit})"

        s.add("returned", returned)
        s.add("total_lines", total_lines)
        return result


def ctx_toc(
    handle: str,
    *,
    db: Any = None,
) -> dict[str, Any]:
    """Return a numbered section index for a handle.

    If the handle is ready, returns section list from the chunks table.
    If still pending/indexing, fast-paths on raw content headings.
    """
    with log(span="ctx.toc", handle=handle) as s:
        if db is None:
            db = _get_connection()

        row = db.execute(
            "SELECT status, source, size_bytes, total_lines FROM results WHERE handle=?",
            (handle,),
        ).fetchone()
        if row is None:
            return {"error": f"Handle not found: {handle}"}

        status = row["status"]

        if status == "ready":
            # Build TOC from chunks table
            chunks = db.execute(
                "SELECT chunk_idx, title, start_line, end_line FROM chunks WHERE handle=? ORDER BY chunk_idx",
                (handle,),
            ).fetchall()

            sections = [
                {
                    "section": i + 1,
                    "title": c["title"] or f"Section {i + 1}",
                    "start_line": c["start_line"],
                    "end_line": c["end_line"],
                }
                for i, c in enumerate(chunks)
            ]

            # Vocabulary hints
            vocab_rows = db.execute(
                "SELECT term FROM vocabulary WHERE handle=? ORDER BY score DESC LIMIT 10",
                (handle,),
            ).fetchall()
            vocab = [r["term"] for r in vocab_rows]

            s.add("sections", len(sections))
            return {
                "handle": handle,
                "sections": sections,
                "total_sections": len(sections),
                "vocabulary": vocab,
            }
        else:
            # Fast-path: parse headings from raw content
            content = get_content(db, handle)
            if content is None:
                return {"error": f"Content not found for handle: {handle}"}

            sections = []
            for i, line in enumerate(content.splitlines(), start=1):
                m = _HEADING_RE.match(line)
                if m:
                    sections.append({
                        "section": len(sections) + 1,
                        "title": m.group(2).strip(),
                        "start_line": i,
                        "end_line": i,  # approximate
                    })

            s.add("sections", len(sections))
            s.add("status", status)
            return {
                "handle": handle,
                "sections": sections,
                "total_sections": len(sections),
                "status": status,
                "note": "Indexing not complete — section boundaries are approximate",
            }


__all__ = ["ctx_read", "ctx_toc"]
