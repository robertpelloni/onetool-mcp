"""Search, grep, and slice operations for the ctx pack."""
from __future__ import annotations

import difflib
import re
from typing import Any

from ot.logging import LogSpan

from .db import _get_connection, get_content
from .indexing import (
    _ETX,
    _SNIPPET_WINDOW,
    _STX,
    build_snippet,
    positions_from_highlight,
)
from .read import _HEADING_RE

log = LogSpan


# ---------------------------------------------------------------------------
# ctx_search — three-layer BM25 search
# ---------------------------------------------------------------------------


def ctx_search(
    handle: str,
    queries: list[str],
    *,
    limit: int = 5,
    db: Any = None,
) -> dict[str, Any]:
    """BM25-ranked section search with three-layer fallback.

    Layers: Porter FTS5 → trigram FTS5 → Levenshtein correction.

    Args:
        handle: Context store handle
        queries: One or more search queries
        limit: Max results per query
        db: SQLite connection
    """
    with log(span="ctx.search", handle=handle, queries=len(queries)) as s:
        if db is None:
            db = _get_connection()

        row = db.execute(
            "SELECT status, size_bytes FROM results WHERE handle=?", (handle,)
        ).fetchone()
        if row is None:
            return {"error": f"Handle not found: {handle}"}

        status = row["status"]

        # Wait for indexing; scale timeout proportionally to content size
        if status in ("pending", "indexing"):
            from .write import _get_event
            ev = _get_event(handle)
            timeout = max(2.0, (row["size_bytes"] or 0) / 50_000)
            ready = ev.wait(timeout=timeout)
            if not ready:
                return {
                    "status": "indexing",
                    "retry_in": f"~{round(timeout)}s",
                    "message": "Indexing not complete. Try again shortly.",
                }
            # Re-check status after wait
            row = db.execute(
                "SELECT status FROM results WHERE handle=?", (handle,)
            ).fetchone()
            status = row["status"] if row else "failed"

        if status == "failed":
            return {
                "error": f"Handle indexing failed: {handle}",
                "hint": "ctx.purge(status='failed') to clean up, then ctx.write() again",
            }

        if status != "ready":
            return {
                "status": status,
                "message": "Handle is not ready for search.",
            }

        # Fetch vocabulary for hints on zero results
        vocab_rows = db.execute(
            "SELECT term FROM vocabulary WHERE handle=? ORDER BY score DESC LIMIT 15",
            (handle,),
        ).fetchall()
        vocabulary = [r["term"] for r in vocab_rows]

        results_by_query: dict[str, Any] = {}
        for query in queries:
            sections, match_layer = _search_query(db, handle, query, limit)
            results_by_query[query] = {
                "sections": sections,
                "matchLayer": match_layer,
            }
            if not sections:
                results_by_query[query]["vocabulary"] = vocabulary

        s.add("result_count", sum(len(v["sections"]) for v in results_by_query.values()))
        return {
            "handle": handle,
            "results": results_by_query,
        }


def _search_query(
    db: Any,
    handle: str,
    query: str,
    limit: int,
) -> tuple[list[dict[str, Any]], str]:
    """Execute three-layer search for a single query.

    Returns (sections, match_layer).
    """
    # Layer 1: Porter FTS5
    sections = _fts_search(db, handle, query, table="chunks", limit=limit)
    if sections:
        return sections, "porter"

    # Layer 2: Trigram FTS5
    sections = _fts_search(db, handle, query, table="chunks_trigram", limit=limit)
    if sections:
        return sections, "trigram"

    # Layer 3: Levenshtein correction
    corrected = _levenshtein_correct(db, handle, query)
    if corrected and corrected != query:
        sections = _fts_search(db, handle, corrected, table="chunks", limit=limit)
        if not sections:
            sections = _fts_search(db, handle, corrected, table="chunks_trigram", limit=limit)
        if sections:
            return sections, "fuzzy"

    return [], "none"


def _fts_search(
    db: Any,
    handle: str,
    query: str,
    table: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Execute FTS5 search against the specified table.

    Returns list of section dicts with title, snippet, score.
    """
    assert table in ("chunks", "chunks_trigram"), f"Unexpected FTS5 table: {table!r}"
    try:
        # Escape FTS5 query special characters for safety
        safe_query = _escape_fts5(query)
        rows = db.execute(
            f"""SELECT chunk_idx, title,
                   highlight({table}, 5, '\x02', '\x03') as highlighted,
                   bm25({table}) as score
            FROM {table}
            WHERE handle=? AND {table} MATCH ?
            ORDER BY bm25({table})
            LIMIT ?""",
            (handle, safe_query, limit),
        ).fetchall()
    except Exception:
        return []

    sections = []
    for r in rows:
        highlighted = r["highlighted"] or ""
        positions = positions_from_highlight(highlighted)
        # Get clean body for snippet generation
        clean_body = highlighted.replace(_STX, "").replace(_ETX, "")
        snippet = build_snippet(clean_body, positions, _SNIPPET_WINDOW)

        sections.append({
            "chunk_idx": r["chunk_idx"],
            "title": r["title"] or f"Section {r['chunk_idx'] + 1}",
            "snippet": snippet,
            "score": -r["score"],
        })
    return sections


_FTS5_STOPWORDS = frozenset([
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "on", "at",
    "by", "for", "with", "as", "from", "that", "this", "these", "those",
    "it", "its", "how", "what", "when", "where", "why", "who", "which",
])


def _escape_fts5(query: str) -> str:
    """Escape a user query for FTS5 MATCH clause.

    Single-word queries are passed through as-is. Multi-word queries with
    explicit FTS5 boolean operators are passed through unquoted. Natural-
    language multi-word queries are split into tokens, stopwords are stripped,
    and the remaining significant terms are joined with spaces (implicit AND)
    so that FTS5 matches documents containing all significant words rather
    than requiring them to appear consecutively as a phrase.
    """
    q = query.strip()
    if not q:
        return '""'
    # Remove characters that break FTS5 syntax
    q = re.sub(r'["\']', "", q)
    # Single token: pass through as-is
    if re.match(r'^[\w]+$', q):
        return q
    # Contains FTS5 boolean operators: pass through unquoted
    if re.search(r'\b(AND|OR|NOT)\b', q):
        return q
    # Multi-word natural language: strip stopwords, join significant terms
    tokens = [t for t in re.split(r'\W+', q) if t and t.lower() not in _FTS5_STOPWORDS]
    if not tokens:
        # All tokens were stopwords — fall back to first token to avoid empty query
        tokens = re.split(r'\W+', q)[:1]
    return " ".join(tokens)


def _levenshtein_correct(db: Any, handle: str, query: str) -> str | None:
    """Find the closest vocabulary term to the query by edit distance.

    Returns the corrected query or None if no close match found.
    Edit distance threshold: ≤ 2.
    """
    vocab_rows = db.execute(
        "SELECT term FROM vocabulary WHERE handle=? ORDER BY score DESC LIMIT 50",
        (handle,),
    ).fetchall()
    vocab = [r["term"] for r in vocab_rows]
    if not vocab:
        return None

    # Find closest match
    best_term = None
    best_dist = 3  # threshold

    query_lower = query.lower()
    for term in vocab:
        dist = _edit_distance(query_lower, term.lower())
        if dist < best_dist:
            best_dist = dist
            best_term = term

    return best_term


def _edit_distance(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    if abs(m - n) >= 3:
        return 3  # exceeds threshold; skip DP
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            tmp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = tmp
    return dp[n]


# ---------------------------------------------------------------------------
# ctx_grep — regex line search with context
# ---------------------------------------------------------------------------


def ctx_grep(
    handle: str,
    pattern: str,
    *,
    context: int = 0,
    fuzzy: bool = False,
    db: Any = None,
) -> dict[str, Any]:
    """Regex line search with optional context lines.

    Args:
        handle: Context store handle
        pattern: Regex pattern (or plain text if fuzzy=True)
        context: Lines before/after each match
        fuzzy: Use fuzzy matching (SequenceMatcher) instead of regex
        db: SQLite connection
    """
    with log(span="ctx.grep", handle=handle, fuzzy=fuzzy or None) as s:
        if db is None:
            db = _get_connection()

        row = db.execute(
            "SELECT handle, is_file FROM results WHERE handle=?", (handle,)
        ).fetchone()
        if row is None:
            return {"error": f"Handle not found: {handle}"}

        content = get_content(db, handle, is_file=row["is_file"])
        if content is None:
            return {"error": f"Content not found for handle: {handle}"}

        lines = content.splitlines()

        if fuzzy:
            matched_lines = _fuzzy_grep(lines, pattern)
            s.add("returned", len(matched_lines))
            return {"handle": handle, "content": "\n".join(matched_lines), "returned": len(matched_lines)}

        if not pattern:
            return {"error": "Pattern must not be empty. Use ctx.read() to retrieve all content."}

        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return {"error": f"Invalid regex pattern: {e}"}

        if context > 0:
            result_lines = _grep_with_context(lines, compiled, context)
        else:
            result_lines = [ln for ln in lines if compiled.search(ln)]

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
) -> list[str]:
    """Return matching lines plus context, with '---' between groups."""
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
        result.append(lines[idx])
        prev_idx = idx
    return result


def _fuzzy_grep(lines: list[str], query: str) -> list[str]:
    """Return lines sorted by fuzzy match score."""
    query_lower = query.lower()
    scored = []
    for line in lines:
        ratio = difflib.SequenceMatcher(None, query_lower, line.lower()).ratio()
        if ratio > 0.3:
            scored.append((ratio, line))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [line for _, line in scored]


# ---------------------------------------------------------------------------
# ctx_slice — section slicing
# ---------------------------------------------------------------------------


def ctx_slice(
    handle: str,
    select: int | str,
    *,
    db: Any = None,
) -> dict[str, Any]:
    """Extract content by section number, heading path, or line range.

    Args:
        handle: Context store handle
        select:
            - int: section number (1-indexed, from ctx.toc)
            - str "N:M": line range (1-indexed inclusive)
            - str: heading path substring match
        db: SQLite connection
    """
    with log(span="ctx.slice", handle=handle) as s:
        if db is None:
            db = _get_connection()

        row = db.execute(
            "SELECT status, is_file FROM results WHERE handle=?", (handle,)
        ).fetchone()
        if row is None:
            return {"error": f"Handle not found: {handle}"}

        content = get_content(db, handle, is_file=row["is_file"])
        if content is None:
            return {"error": f"Content not found for handle: {handle}"}

        lines = content.splitlines()

        # Line range: "N:M"
        if isinstance(select, str) and re.match(r"^\d+:\d+$", select):
            parts = select.split(":")
            start = max(1, int(parts[0]))
            end = min(len(lines), int(parts[1]))
            if start > end:
                return {"error": f"Invalid line range: {select}"}
            s.add("lines", end - start + 1)
            return {
                "handle": handle,
                "select": select,
                "content": "\n".join(lines[start - 1: end]),
                "start_line": start,
                "end_line": end,
            }

        # Section number or heading path — need chunk data
        if row["status"] == "ready":
            chunks = db.execute(
                "SELECT chunk_idx, title, start_line, end_line, body FROM chunks"
                " WHERE handle=? ORDER BY chunk_idx",
                (handle,),
            ).fetchall()

            if isinstance(select, int):
                idx = select - 1  # 0-indexed
                if idx < 0 or idx >= len(chunks):
                    return {"error": f"Section {select} not found (handle has {len(chunks)} sections)"}
                c = chunks[idx]
                s.add("lines", c["end_line"] - c["start_line"] + 1)
                return {
                    "handle": handle,
                    "section": select,
                    "title": c["title"],
                    "content": "\n".join(lines[c["start_line"] - 1: c["end_line"]]),
                    "start_line": c["start_line"],
                    "end_line": c["end_line"],
                }
            else:
                # Heading path substring search
                select_lower = str(select).lower()
                for i, c in enumerate(chunks):
                    if select_lower in (c["title"] or "").lower():
                        s.add("lines", c["end_line"] - c["start_line"] + 1)
                        return {
                            "handle": handle,
                            "section": i + 1,
                            "title": c["title"],
                            "content": "\n".join(lines[c["start_line"] - 1: c["end_line"]]),
                            "start_line": c["start_line"],
                            "end_line": c["end_line"],
                        }
                return {"error": f"Section not found matching: {select!r}"}
        else:
            # Not indexed yet — for int selectors we can't do much
            if isinstance(select, int):
                return {
                    "error": f"Handle is not indexed yet (status={row['status']}). Cannot slice by section number."
                }
            # String: try heading match in raw content
            select_lower = str(select).lower()
            for i, line in enumerate(lines, start=1):
                m = _HEADING_RE.match(line)
                if m and select_lower in m.group(2).lower():
                    return {
                        "handle": handle,
                        "title": m.group(2).strip(),
                        "content": line,
                        "start_line": i,
                        "end_line": i,
                        "note": "Indexing not complete — only the heading line returned",
                    }
            return {"error": f"Section not found matching: {select!r}"}


__all__ = [
    "_edit_distance",
    "_escape_fts5",
    "_fts_search",
    "_levenshtein_correct",
    "ctx_grep",
    "ctx_search",
    "ctx_slice",
]
