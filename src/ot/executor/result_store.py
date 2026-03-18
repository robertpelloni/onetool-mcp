"""Large output result store for OneTool — thin wrapper over the ctx pack.

The ResultStore class provides a stable interface over the ctx flat-file backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StoredResult:
    """Result from storing large output."""

    handle: str
    total_lines: int
    size_bytes: int
    summary: str
    preview: str
    status: str = "ready"

    def to_dict(self) -> dict[str, Any]:
        """Convert to summary dictionary for MCP response."""
        return {
            "handle": self.handle,
            "total_lines": self.total_lines,
            "size_bytes": self.size_bytes,
            "summary": self.summary,
            "preview": self.preview,
            "status": self.status,
        }


@dataclass
class QueryResult:
    """Result from querying stored output."""

    content: str
    total_lines: int
    returned: int
    offset: int
    has_more: bool
    handle: str = ""
    limit: int = 100
    total_size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for MCP response."""
        end = self.offset + self.returned - 1
        pct = int((end / self.total_lines) * 100) if self.total_lines > 0 else 100
        result: dict[str, Any] = {
            "content": self.content,
            "total_lines": self.total_lines,
            "returned": self.returned,
            "offset": self.offset,
            "has_more": self.has_more,
            "progress": f"lines {self.offset}-{end} of {self.total_lines} ({pct}%)",
            "total_size_bytes": self.total_size_bytes,
        }
        if self.has_more and self.handle:
            next_offset = self.offset + self.returned
            result["next_query"] = (
                f"ctx.read('{self.handle}', offset={next_offset}, limit={self.limit})"
            )
        return result


@dataclass
class ResultStore:
    """Manages storage and retrieval of large tool outputs via the ctx backend."""

    def store(
        self,
        content: str,
        *,
        tool: str = "",
        preview_lines: int | None = None,
    ) -> StoredResult:
        """Store large output via ctx backend.

        Args:
            content: The output content to store
            tool: Name of the tool that generated this output
            preview_lines: Number of preview lines (default from config)

        Returns:
            StoredResult with handle and summary
        """
        from ot.config import get_config
        from ot.ctx.write import ctx_write

        config_obj = get_config()
        if preview_lines is None:
            preview_lines = config_obj.output.preview_lines

        write_result = ctx_write(content, source=tool)

        handle = write_result["handle"]
        total_lines = write_result["total_lines"]
        size_bytes = write_result["size_bytes"]

        # Build preview respecting preview_lines
        lines = content.splitlines()
        raw_preview = lines[:preview_lines]
        preview_max_chars = config_obj.output.preview_max_chars
        if preview_max_chars > 0:
            preview_lines_truncated = [
                line[:preview_max_chars] + "…" if len(line) > preview_max_chars else line
                for line in raw_preview
            ]
        else:
            preview_lines_truncated = raw_preview
        preview = "\n".join(preview_lines_truncated)

        summary = f"{total_lines} lines from {tool}" if tool else f"{total_lines} lines stored"

        return StoredResult(
            handle=handle,
            total_lines=total_lines,
            size_bytes=size_bytes,
            summary=summary,
            preview=preview,  # str
            status=write_result.get("status", "pending"),
        )

    def query(
        self,
        handle: str,
        *,
        offset: int = 1,
        limit: int = 100,
        search: str = "",
        fuzzy: bool = False,
        tail: int = 0,
        context: int = 0,
    ) -> QueryResult:
        """Query stored result via ctx backend.

        Args:
            handle: The result handle
            offset: Starting line (1-indexed)
            limit: Max lines to return
            search: Regex pattern or fuzzy query
            fuzzy: Use fuzzy matching
            tail: Return last N lines
            context: Context lines around search matches

        Returns:
            QueryResult with matching lines

        Raises:
            ValueError: If handle not found or expired
        """
        if search:
            if fuzzy:
                raise ValueError(
                    "fuzzy=True is no longer supported; "
                    "use ctx.ask() for natural-language queries or ctx.grep() for regex."
                )
            from ot.ctx.grep import ctx_grep
            result = ctx_grep(handle, search, context=context)
            if "error" in result:
                raise ValueError(result["error"])
            all_lines = result["content"].splitlines() if result["content"] else []
            total = len(all_lines)
            if tail > 0:
                offset = max(1, total - tail + 1)
                limit = tail
            start = offset - 1
            end = start + limit
            chunk = all_lines[start:end]
            return QueryResult(
                content="\n".join(chunk),
                total_lines=total,
                returned=len(chunk),
                offset=offset,
                has_more=end < total,
                handle=handle,
                limit=limit,
                total_size_bytes=0,
            )

        from ot.ctx.read import ctx_read
        result = ctx_read(handle, offset=offset, limit=limit, tail=tail)
        if "error" in result:
            raise ValueError(result["error"])

        return QueryResult(
            content=result["content"],
            total_lines=result["total_lines"],
            returned=result["returned"],
            offset=result["offset"],
            has_more=result["has_more"],
            handle=handle,
            limit=limit,
            total_size_bytes=result.get("total_size_bytes", 0),
        )

    def cleanup(self) -> int:
        """Delete expired entries from the ctx DB and compact it."""
        from ot.ctx.maintenance import ctx_purge
        result = ctx_purge()
        return int(result.get("deleted", 0))


# Global singleton instance
_store: ResultStore | None = None


def get_result_store() -> ResultStore:
    """Get or create the global result store instance."""
    global _store
    if _store is None:
        _store = ResultStore()
    return _store
