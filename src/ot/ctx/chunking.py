"""Content chunking for the ctx pack.

Two chunking strategies:
1. Markdown-aware: split on headings (#-####), keep code fences intact,
   breadcrumb titles, flush on horizontal rules (---)
2. Plain-text: split on blank lines; fallback to 20-line groups with 2-line
   overlap when paragraphs are too long.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Heading pattern: 1-4 hashes at line start
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)")
_HR_RE = re.compile(r"^(-{3,}|={3,}|\*{3,})\s*$")
_CODE_FENCE_RE = re.compile(r"^```")

_PLAIN_MAX_LINES = 20
_PLAIN_OVERLAP = 2


@dataclass
class Chunk:
    """A single chunk of content."""

    chunk_idx: int
    title: str          # breadcrumb title
    body: str           # chunk text
    start_line: int     # 1-indexed
    end_line: int       # 1-indexed inclusive


def chunk_content(content: str) -> list[Chunk]:
    """Split content into chunks using markdown-aware or plain-text strategy.

    Markdown detection: if the content has at least one heading (# … ####),
    the markdown chunker is used. Otherwise the plain-text chunker is used.
    """
    lines = content.splitlines()
    if _has_markdown_headings(lines):
        return _chunk_markdown(lines)
    return _chunk_plain(lines)


def _has_markdown_headings(lines: list[str]) -> bool:
    """Return True if the content appears to be markdown with headings."""
    return any(_HEADING_RE.match(line) for line in lines)


# ---------------------------------------------------------------------------
# Markdown chunker
# ---------------------------------------------------------------------------


def _chunk_markdown(lines: list[str]) -> list[Chunk]:
    """Split markdown into chunks at heading boundaries.

    Rules:
    - New chunk starts at each # / ## / ### / #### heading
    - Code fences keep content intact (no splitting inside fences)
    - Horizontal rules (---/===/***) flush the current chunk
    - Breadcrumb titles track heading hierarchy (H1 > H2 > H3)
    """
    chunks: list[Chunk] = []
    breadcrumbs: list[str] = [""] * 4  # indexed 0-3 for H1-H4

    current_lines: list[str] = []
    current_title = ""
    current_start = 1
    in_fence = False
    chunk_idx = 0

    def flush(end_line: int) -> None:
        nonlocal chunk_idx
        body = "\n".join(current_lines).strip()
        if body:
            chunks.append(Chunk(
                chunk_idx=chunk_idx,
                title=current_title,
                body=body,
                start_line=current_start,
                end_line=end_line,
            ))
            chunk_idx += 1

    for i, line in enumerate(lines, start=1):
        # Toggle code fence state
        if _CODE_FENCE_RE.match(line):
            in_fence = not in_fence
            current_lines.append(line)
            continue

        if in_fence:
            current_lines.append(line)
            continue

        # Horizontal rule — flush current chunk
        if _HR_RE.match(line):
            flush(i - 1)
            current_lines = []
            current_start = i + 1
            continue

        # Heading — flush and start new chunk
        m = _HEADING_RE.match(line)
        if m:
            flush(i - 1)
            level = len(m.group(1))  # 1-4
            heading_text = m.group(2).strip()

            # Update breadcrumb at this level, clear deeper levels
            breadcrumbs[level - 1] = heading_text
            for j in range(level, 4):
                breadcrumbs[j] = ""

            current_title = " > ".join(b for b in breadcrumbs if b)
            current_lines = [line]
            current_start = i
            continue

        current_lines.append(line)

    # Flush remaining content
    flush(len(lines))

    # If nothing was chunked (e.g. all headings, no body), create one chunk
    if not chunks and lines:
        body = "\n".join(lines).strip()
        chunks.append(Chunk(chunk_idx=0, title="", body=body, start_line=1, end_line=len(lines)))

    return chunks


# ---------------------------------------------------------------------------
# Plain-text chunker
# ---------------------------------------------------------------------------


def _chunk_plain(lines: list[str]) -> list[Chunk]:
    """Split plain text into chunks by blank lines.

    If a paragraph block exceeds _PLAIN_MAX_LINES, it is further split
    into fixed-size groups of _PLAIN_MAX_LINES with _PLAIN_OVERLAP overlap.
    """
    # First pass: split on blank lines
    paragraphs: list[tuple[int, list[str]]] = []  # (start_line, lines)
    current: list[str] = []
    current_start = 1

    for i, line in enumerate(lines, start=1):
        if line.strip() == "":
            if current:
                paragraphs.append((current_start, current))
                current = []
                current_start = i + 1
        else:
            if not current:
                current_start = i
            current.append(line)

    if current:
        paragraphs.append((current_start, current))

    # Second pass: split large paragraphs into fixed-size groups
    chunks: list[Chunk] = []
    chunk_idx = 0

    for para_start, para_lines in paragraphs:
        if len(para_lines) <= _PLAIN_MAX_LINES:
            body = "\n".join(para_lines).strip()
            if body:
                chunks.append(Chunk(
                    chunk_idx=chunk_idx,
                    title="",
                    body=body,
                    start_line=para_start,
                    end_line=para_start + len(para_lines) - 1,
                ))
                chunk_idx += 1
        else:
            # Fixed-size groups with overlap
            step = _PLAIN_MAX_LINES - _PLAIN_OVERLAP
            pos = 0
            while pos < len(para_lines):
                group = para_lines[pos: pos + _PLAIN_MAX_LINES]
                body = "\n".join(group).strip()
                if body:
                    start = para_start + pos
                    end = start + len(group) - 1
                    chunks.append(Chunk(
                        chunk_idx=chunk_idx,
                        title="",
                        body=body,
                        start_line=start,
                        end_line=end,
                    ))
                    chunk_idx += 1
                pos += step

    # Edge case: empty content
    if not chunks and lines:
        body = "\n".join(lines).strip()
        if body:
            chunks.append(Chunk(chunk_idx=0, title="", body=body, start_line=1, end_line=len(lines)))

    return chunks


__all__ = ["Chunk", "_chunk_markdown", "_chunk_plain", "chunk_content"]
