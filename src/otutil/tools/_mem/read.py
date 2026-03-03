"""Memory read functions."""
from __future__ import annotations

import builtins
from typing import Any

from ot.logging import LogSpan

from .content import _build_toc, _decode_sections, _tags_filter_sql, _topic_filter
from .db import _deserialize_meta, _deserialize_tags, _get_connection

_builtins_list = builtins.list

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

            # Increment access count
            conn.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id = ?",
                [row[0]],
            )
            conn.commit()

            # Update row with incremented access_count for accurate display
            row = (*row[:6], row[6] + 1, *row[7:])

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
        return _build_toc(sections, row[2].count("\n") + 1)

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


__all__ = [
    "_READ_COLUMNS",
    "_VALID_READ_MODES",
    "_format_read_row",
    "read",
    "read_batch",
]
