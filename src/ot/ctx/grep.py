"""Regex line search for the ctx pack."""
from __future__ import annotations

import re
from typing import Any

from ot.logging import LogSpan

from .config import Config, _get_config
from .read import _truncate_line
from .store import HandleStore, _get_store, _resolve_handle, is_expired

log = LogSpan


def ctx_grep(
    handle: str,
    pattern: str,
    *,
    context: int = 0,
    store: HandleStore | None = None,
    config: Config | None = None,
) -> dict[str, Any]:
    """Regex line search with optional context lines and long-line truncation.

    Args:
        handle: Context store handle
        pattern: Regex pattern to search for
        context: Lines before/after each match (groups separated by '---')
        store: HandleStore instance (uses session default if not provided)
        config: Pack config (uses module default if not provided)
    """
    with log(span="ctx.grep", handle=handle) as s:
        if config is None:
            config = _get_config()
        if store is None:
            store = _get_store()

        try:
            handle = _resolve_handle(handle)
        except TypeError as e:
            return {"error": str(e)}

        if not pattern:
            return {"error": "Pattern must not be empty. Use ctx.read() to retrieve all content."}

        if not store.exists(handle):
            return {"error": f"Handle not found: {handle}"}

        try:
            meta = store.read_meta(handle)
        except (OSError, ValueError):
            return {"error": f"Handle not found: {handle}"}

        if is_expired(meta):
            return {"error": f"Handle has expired: {handle}"}

        try:
            content = store.read_content(handle)
        except OSError:
            return {"error": f"Content not found for handle: {handle}"}

        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return {"error": f"Invalid regex pattern: {e}"}

        lines = content.splitlines()
        max_chars = config.max_line_chars

        if context > 0:
            result_lines = _grep_with_context(lines, compiled, context, max_chars)
        else:
            result_lines = [
                _truncate_line(ln, max_chars)
                for ln in lines
                if compiled.search(ln)
            ]

        s.add("returned", len(result_lines))
        return {
            "handle": handle,
            "content": "\n".join(result_lines),
            "returned": len(result_lines),
        }


def _grep_with_context(
    lines: list[str],
    pattern: re.Pattern[str],
    context: int,
    max_chars: int,
) -> list[str]:
    """Return matching lines plus context, with '---' between non-contiguous groups."""
    total = len(lines)
    include: set[int] = set()
    for i, line in enumerate(lines):
        if pattern.search(line):
            for j in range(max(0, i - context), min(total, i + context + 1)):
                include.add(j)

    if not include:
        return []

    result: list[str] = []
    prev_idx: int | None = None
    for idx in sorted(include):
        if prev_idx is not None and idx > prev_idx + 1:
            result.append("---")
        result.append(_truncate_line(lines[idx], max_chars))
        prev_idx = idx
    return result


__all__ = ["ctx_grep"]
