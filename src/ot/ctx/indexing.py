"""Indexing pipeline for the ctx pack.

Responsibilities:
- Insert chunks into both FTS5 tables (porter + trigram)
- Extract vocabulary: IDF-scored, stopword-filtered, top 40 terms
- Smart snippet extraction using FTS5 highlight() STX/ETX markers
- Optional embedding dispatch via ot_llm
"""
from __future__ import annotations

import math
import re
import struct
from typing import TYPE_CHECKING

from .chunking import Chunk, chunk_content

if TYPE_CHECKING:
    import sqlite3
from .db import delete_fts_for_handle

# ---------------------------------------------------------------------------
# Stopwords
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "do", "does", "for", "from", "had", "has", "have", "he", "her", "him",
    "his", "how", "i", "if", "in", "is", "it", "its", "me", "my", "no", "not",
    "of", "on", "or", "our", "s", "she", "so", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "those", "to", "too",
    "up", "us", "was", "we", "were", "what", "when", "where", "which", "while",
    "who", "will", "with", "would", "you", "your",
})

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_]{2,}")
_CAMEL_RE = re.compile(r"[a-z][A-Z]|[A-Z]{2}[a-z]|_[a-zA-Z]")

# STX/ETX used by FTS5 highlight() for match markers
_STX = "\x02"
_ETX = "\x03"

_SNIPPET_WINDOW = 300  # chars on each side of match position


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------


def build_index(
    handle: str,
    content: str,
    conn: sqlite3.Connection,
    *,
    embedding_model: str = "",
) -> None:
    """Full indexing pipeline for one handle.

    1. Chunk content
    2. Insert chunks into FTS5 tables
    3. Extract vocabulary
    4. Optionally dispatch embeddings
    5. Update results.status = 'ready'
    """
    # Mark as indexing
    conn.execute("UPDATE results SET status='indexing' WHERE handle=?", (handle,))
    conn.commit()

    try:
        chunks = chunk_content(content)

        # Clear any previous FTS5 data for this handle
        delete_fts_for_handle(conn, handle)

        # Insert chunks into both FTS5 tables
        for chunk in chunks:
            conn.execute(
                "INSERT INTO chunks(handle, chunk_idx, start_line, end_line, title, body)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (handle, chunk.chunk_idx, chunk.start_line, chunk.end_line, chunk.title, chunk.body),
            )
            conn.execute(
                "INSERT INTO chunks_trigram(handle, chunk_idx, start_line, end_line, title, body)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (handle, chunk.chunk_idx, chunk.start_line, chunk.end_line, chunk.title, chunk.body),
            )

        # Extract and store vocabulary
        vocab = _extract_vocabulary(content)
        conn.execute("DELETE FROM vocabulary WHERE handle=?", (handle,))
        conn.executemany(
            "INSERT INTO vocabulary(handle, term, score) VALUES (?, ?, ?)",
            [(handle, term, score) for term, score in vocab],
        )

        # Optional embeddings
        if embedding_model:
            _store_embeddings(handle, chunks, conn, embedding_model)

        conn.execute("UPDATE results SET status='ready' WHERE handle=?", (handle,))
        conn.commit()

    except Exception:
        conn.execute("UPDATE results SET status='failed' WHERE handle=?", (handle,))
        conn.commit()
        raise


# ---------------------------------------------------------------------------
# Vocabulary extraction
# ---------------------------------------------------------------------------


def _extract_vocabulary(content: str, top_n: int = 40) -> list[tuple[str, float]]:
    """Extract top IDF-scored vocabulary terms from content.

    Returns list of (term, score) sorted by score descending.
    Applies identifier bonus for camelCase, underscore terms, or length >= 12.
    """
    words = _WORD_RE.findall(content)
    words_lower = [w.lower() for w in words]

    # Filter stopwords
    filtered = [(w, wl) for w, wl in zip(words, words_lower, strict=False) if wl not in _STOPWORDS]

    if not filtered:
        return []

    # Document frequency (treating each 200-char window as a "document")
    doc_size = 200
    n_docs = max(1, len(content) // doc_size)
    doc_freq: dict[str, int] = {}

    for i in range(0, len(content), doc_size):
        doc_words = {w.lower() for w in _WORD_RE.findall(content[i: i + doc_size])}
        for w in doc_words:
            if w not in _STOPWORDS:
                doc_freq[w] = doc_freq.get(w, 0) + 1

    # Term frequency
    term_freq: dict[str, int] = {}
    for _, wl in filtered:
        term_freq[wl] = term_freq.get(wl, 0) + 1

    # Score: TF * IDF + identifier bonus
    scored: dict[str, float] = {}
    for wl, tf in term_freq.items():
        df = doc_freq.get(wl, 1)
        idf = math.log((n_docs + 1) / (df + 1)) + 1.0
        score = tf * idf

        # Bonus for identifiers: camelCase, underscore-containing, or long terms
        orig = next((w for w, wlow in filtered if wlow == wl), wl)
        if _CAMEL_RE.search(orig) or "_" in orig or len(orig) >= 12:
            score *= 1.5

        scored[wl] = score

    # Return top N
    sorted_terms = sorted(scored.items(), key=lambda x: x[1], reverse=True)
    return sorted_terms[:top_n]


# ---------------------------------------------------------------------------
# Smart snippet extraction
# ---------------------------------------------------------------------------


def positions_from_highlight(highlighted_text: str) -> list[int]:
    """Extract match positions from FTS5 highlight() output.

    FTS5 wraps matched tokens with STX (\\x02) before and ETX (\\x03) after.
    Returns list of character positions (mid-point of each match in the
    original text, with STX/ETX stripped).
    """
    positions = []
    clean = []
    i = 0
    pos_clean = 0

    while i < len(highlighted_text):
        ch = highlighted_text[i]
        if ch == _STX:
            # Find matching ETX
            j = highlighted_text.find(_ETX, i + 1)
            if j == -1:
                clean.append(highlighted_text[i:])
                break
            match_text = highlighted_text[i + 1: j]
            mid = pos_clean + len(match_text) // 2
            positions.append(mid)
            clean.append(match_text)
            pos_clean += len(match_text)
            i = j + 1
        elif ch == _ETX:
            i += 1
        else:
            clean.append(ch)
            pos_clean += 1
            i += 1

    return positions


def build_snippet(full_text: str, positions: list[int], window: int = _SNIPPET_WINDOW) -> str:
    """Build a snippet from match positions, merging overlapping windows.

    Returns a string of ±window chars around each position, joined by '…'
    when gaps exist between windows.
    """
    if not positions:
        return full_text[:window * 2]

    n = len(full_text)
    # Build windows
    windows: list[tuple[int, int]] = []
    for pos in positions:
        start = max(0, pos - window)
        end = min(n, pos + window)
        windows.append((start, end))

    # Sort and merge overlapping windows
    windows.sort()
    merged: list[tuple[int, int]] = []
    for start, end in windows:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    parts = []
    for start, end in merged:
        # Snap start forward: skip partial word at beginning of window
        if start > 0 and not full_text[start].isspace():
            ws = start
            while ws < end and not full_text[ws].isspace():
                ws += 1
            if ws < end:  # whitespace found — skip partial word + leading space
                while ws < end and full_text[ws].isspace():
                    ws += 1
                start = ws
        # Snap end forward: complete partial word at end of window
        if end < n and not full_text[end - 1].isspace():
            while end < n and not full_text[end].isspace():
                end += 1
        part = full_text[start:end].strip()
        if part:
            parts.append(part)

    return " … ".join(parts) if parts else full_text[:window * 2]


# ---------------------------------------------------------------------------
# Embeddings (optional)
# ---------------------------------------------------------------------------


def _store_embeddings(
    handle: str,
    chunks: list[Chunk],
    conn: sqlite3.Connection,
    embedding_model: str,
) -> None:
    """Generate and store embeddings for each chunk via ot_llm."""
    try:
        from pydantic import BaseModel, Field

        from ot.config import get_secret, get_tool_config
        from ottools.ot_llm import transform as llm_transform  # noqa: F401

        class _LlmConfig(BaseModel):
            base_url: str = Field(default="")
            model: str = Field(default="")

        llm_cfg = get_tool_config("ot_llm", _LlmConfig)
        api_key = get_secret("OPENAI_API_KEY")
        if not api_key or not llm_cfg.base_url:
            return

        import openai

        client = openai.OpenAI(
            api_key=api_key,
            base_url=llm_cfg.base_url or None,
        )

        for chunk in chunks:
            text = f"{chunk.title} {chunk.body}".strip()[:8191]
            resp = client.embeddings.create(model=embedding_model, input=[text])
            vec = resp.data[0].embedding
            blob = struct.pack(f"<{len(vec)}f", *vec)
            conn.execute(
                "INSERT OR REPLACE INTO chunk_embeddings(handle, chunk_idx, embedding)"
                " VALUES (?, ?, ?)",
                (handle, chunk.chunk_idx, blob),
            )
        conn.commit()
    except Exception:
        # Embeddings are optional — skip silently on any error
        pass


__all__ = [
    "_ETX",
    "_STX",
    "_extract_vocabulary",
    "build_index",
    "build_snippet",
    "positions_from_highlight",
]
