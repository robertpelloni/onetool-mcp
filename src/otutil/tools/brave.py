"""Brave Search API tools.

Provides web search, local search, news search, image search, and video search
via the Brave Search API. Requires BRAVE_API_KEY secret in secrets.yaml.

API docs: https://api-dashboard.search.brave.com/app/documentation
Reference: https://github.com/brave/brave-search-mcp-server
"""

from __future__ import annotations

# Pack for dot notation: brave.search(), brave.news(), etc.
pack = "brave"

__all__ = ["image", "news", "search", "search_batch", "video"]

# Dependency declarations for CLI validation
__ot_requires__ = {
    "secrets": ["BRAVE_API_KEY"],
}

import re
from typing import Any

import httpx
from pydantic import BaseModel, Field

from ot.config import get_secret, get_tool_config
from ot.logging import LogSpan
from ot.utils import (
    batch_execute,
    format_batch_results,
    lazy_client,
    normalize_items,
)


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    timeout: float = Field(
        default=60.0,
        ge=1.0,
        le=300.0,
        description="Request timeout in seconds",
    )

BRAVE_API_BASE = "https://api.search.brave.com/res/v1"

# Truncation length for video descriptions (147 chars + "..." = 150 total)
VIDEO_DESC_MAX_LENGTH = 150

def _create_http_client() -> httpx.Client:
    """Create HTTP client for Brave API requests."""
    return httpx.Client(
        base_url=BRAVE_API_BASE,
        timeout=60.0,
        headers={"Accept": "application/json", "Accept-Encoding": "gzip"},
    )


# Thread-safe lazy client using SDK utility
_get_http_client = lazy_client(_create_http_client)


def _get_config() -> Config:
    """Get brave pack configuration."""
    return get_tool_config("brave", Config)


def _get_api_key() -> str:
    """Get Brave API key from secrets."""
    return get_secret("BRAVE_API_KEY") or ""


def _get_headers(api_key: str) -> dict[str, str]:
    """Get headers for Brave API requests.

    Args:
        api_key: Pre-fetched Brave API key
    """
    return {
        "X-Subscription-Token": api_key,
    }


def _make_request(
    endpoint: str,
    params: dict[str, Any],
    timeout: float | None = None,
) -> tuple[bool, dict[str, Any] | str]:
    """Make HTTP GET request to Brave API.

    Args:
        endpoint: API endpoint path (e.g., "/web/search")
        params: Query parameters
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, result). If success, result is parsed JSON dict.
        If failure, result is error message string.
    """
    api_key = _get_api_key()
    if not api_key:
        return False, "Error: BRAVE_API_KEY secret not configured"

    if timeout is None:
        timeout = _get_config().timeout

    with LogSpan(
        span="brave.request", endpoint=endpoint, query=params.get("q", "")
    ) as span:
        try:
            client = _get_http_client()
            if client is None:
                return False, "Error: HTTP client not initialized"
            response = client.get(
                endpoint,
                params=params,
                headers=_get_headers(api_key),
                timeout=timeout,
            )
            response.raise_for_status()

            result = response.json()
            span.add(status=response.status_code)
            return True, result

        except Exception as e:
            error_type = type(e).__name__
            span.add(error=f"{error_type}: {e}")

            if hasattr(e, "response"):
                status = getattr(e.response, "status_code", "unknown")
                text = getattr(e.response, "text", "")[:200]
                return False, f"HTTP error ({status}): {text}"
            return False, f"Request failed: {e}"


def _format_web_results(data: dict[str, Any]) -> str:
    """Format web search results for display."""
    lines: list[str] = []

    web = data.get("web", {})
    results = web.get("results", [])

    if not results:
        return "No results found."

    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        description = result.get("description", "")

        lines.append(f"{i}. {title}")
        lines.append(f"   {url}")
        if description:
            lines.append(f"   {description}")
        lines.append("")

    return "\n".join(lines)


def _format_news_results(data: dict[str, Any]) -> str:
    """Format news search results for display."""
    lines: list[str] = []

    results = data.get("results", [])

    if not results:
        return "No news results found."

    # Sort by page_age (ISO date string) most-recent first; items without it go last
    results = sorted(
        results,
        key=lambda r: r.get("page_age") or "",
        reverse=True,
    )

    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        source = result.get("meta_url", {}).get("hostname", "")
        age = result.get("age", "")
        breaking = result.get("breaking", False)

        prefix = "[BREAKING] " if breaking else ""
        lines.append(f"{i}. {prefix}{title}")
        if source:
            lines.append(f"   Source: {source} ({age})")
        lines.append(f"   {url}")
        lines.append("")

    return "\n".join(lines)



def _format_image_results(data: dict[str, Any]) -> str:
    """Format image search results for display."""
    lines: list[str] = []

    results = data.get("results", [])

    if not results:
        return "No image results found."

    for i, result in enumerate(results, 1):
        title = result.get("title", "") or "No title"
        url = result.get("url", "")
        source = result.get("source", "")
        props = result.get("properties", {})
        width = props.get("width", "")
        height = props.get("height", "")
        image_url = props.get("url", "")

        lines.append(f"{i}. {title}")
        if width and height:
            lines.append(f"   Size: {width}x{height}")
        if source:
            lines.append(f"   Source: {source}")
        if image_url:
            lines.append(f"   Image: {image_url}")
        lines.append(f"   {url}")
        lines.append("")

    return "\n".join(lines)


def _format_video_results(data: dict[str, Any]) -> str:
    """Format video search results for display."""
    lines: list[str] = []

    results = data.get("results", [])

    if not results:
        return "No video results found."

    for i, result in enumerate(results, 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        description = result.get("description", "")
        creator = result.get("meta_url", {}).get("hostname", "")
        duration = result.get("video", {}).get("duration", "")
        views = result.get("video", {}).get("views", "")

        lines.append(f"{i}. {title}")
        if creator:
            lines.append(f"   Channel: {creator}")
        if duration:
            lines.append(f"   Duration: {duration}")
        if views:
            lines.append(f"   Views: {views}")
        if description:
            if len(description) > VIDEO_DESC_MAX_LENGTH:
                description = description[: VIDEO_DESC_MAX_LENGTH - 3] + "..."
            lines.append(f"   {description}")
        lines.append(f"   {url}")
        lines.append("")

    return "\n".join(lines)


_DATE_RANGE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}to\d{4}-\d{2}-\d{2}$")
_FRESHNESS_VALUES = frozenset(["pd", "pw", "pm", "py"])
_SAFESEARCH_WEB_VALUES = frozenset(["off", "moderate", "strict"])
_SAFESEARCH_IMAGE_VALUES = frozenset(["off", "strict"])
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")


def _validate_freshness(freshness: str | None) -> str | None:
    """Validate freshness value. Returns error string or None if valid."""
    if freshness is None:
        return None
    if freshness in _FRESHNESS_VALUES or _DATE_RANGE_RE.match(freshness):
        return None
    return (
        f"Error: Invalid freshness '{freshness}'. "
        f"Use {sorted(_FRESHNESS_VALUES)} or YYYY-MM-DDtoYYYY-MM-DD"
    )


def _validate_safesearch(safesearch: str, valid_values: frozenset[str]) -> str | None:
    """Validate safesearch value. Returns error string or None if valid."""
    if safesearch in valid_values:
        return None
    return f"Error: Invalid safesearch '{safesearch}'. Use {sorted(valid_values)}"


def _validate_count(count: int) -> str | None:
    """Validate count is in range 1-20. Returns error string or None if valid."""
    if 1 <= count <= 20:
        return None
    return f"Error: count must be between 1 and 20 (got {count})"


def _validate_offset(offset: int) -> str | None:
    """Validate offset is in range 0-9. Returns error string or None if valid."""
    if 0 <= offset <= 9:
        return None
    return f"Error: offset must be between 0 and 9 (got {offset})"


def _validate_country(country: str) -> str | None:
    """Validate country is a 2-letter uppercase code. Returns error string or None if valid."""
    if _COUNTRY_RE.match(country):
        return None
    return f"Error: Invalid country '{country}'. Use a 2-letter uppercase country code (e.g. 'US', 'GB')"


def _clamp(value: int, min_val: int, max_val: int) -> int:
    """Clamp a value between min and max."""
    return min(max(value, min_val), max_val)


def _validate_query(query: str) -> str | None:
    """Validate query against Brave API limits.

    Returns None if valid, error message if invalid.
    """
    if not query or not query.strip():
        return "Error: Query cannot be empty"
    if len(query) > 400:
        return f"Error: Query exceeds 400 character limit ({len(query)} chars)"
    word_count = len(query.split())
    if word_count > 50:
        return f"Error: Query exceeds 50 word limit ({word_count} words)"
    return None


def search(
    *,
    query: str,
    count: int = 10,
    offset: int = 0,
    country: str = "US",
    search_lang: str = "en",
    safesearch: str = "moderate",
    freshness: str | None = None,
) -> str:
    """Search the web using Brave Search API.

    Args:
        query: Search query (max 400 chars, 50 words)
        count: Number of results to return (1-20, default: 10)
        offset: Pagination offset (0-9, default: 0)
        country: 2-letter country code for results (default: "US")
        search_lang: Language code for results (default: "en")
        safesearch: Content filter - "off", "moderate", "strict" (default: "moderate")
        freshness: Time filter - "pd" (day), "pw" (week), "pm" (month), "py" (year),
            or date range "YYYY-MM-DDtoYYYY-MM-DD" (e.g. "2024-01-01to2024-06-30")

    Returns:
        YAML flow style search results or error message

    Example:
        # Basic search
        brave.search(query="Python async best practices")

        # Recent results only
        brave.search(query="AI news", freshness="pw", count=5)
    """
    if error := _validate_query(query):
        return error
    if error := _validate_count(count):
        return error
    if error := _validate_offset(offset):
        return error
    if error := _validate_country(country):
        return error
    if error := _validate_safesearch(safesearch, _SAFESEARCH_WEB_VALUES):
        return error
    if error := _validate_freshness(freshness):
        return error

    params: dict[str, Any] = {
        "q": query,
        "count": count,
        "offset": offset,
        "country": country,
        "search_lang": search_lang,
        "safesearch": safesearch,
    }

    if freshness:
        params["freshness"] = freshness

    success, result = _make_request("/web/search", params)

    if not success:
        return str(result)

    return _format_web_results(result)  # type: ignore[arg-type]


def news(
    *,
    query: str,
    count: int = 10,
    offset: int = 0,
    country: str = "US",
    search_lang: str = "en",
    freshness: str | None = None,
) -> str:
    """Search news articles using Brave Search API.

    Uses the dedicated /news/search endpoint for better news results.
    Results are sorted by publication date, most recent first.

    Args:
        query: Search query for news
        count: Number of results (1-20, default: 10)
        offset: Pagination offset (0-9, default: 0)
        country: 2-letter country code (default: "US")
        search_lang: Language code (default: "en")
        freshness: Time filter - "pd" (day), "pw" (week), "pm" (month), "py" (year),
            or date range "YYYY-MM-DDtoYYYY-MM-DD" (e.g. "2024-01-01to2024-06-30")

    Returns:
        Formatted news results or error message

    Example:
        # Today's tech news
        brave.news(query="artificial intelligence", freshness="pd")

        # UK news
        brave.news(query="technology", country="GB", count=5)
    """
    if error := _validate_query(query):
        return error
    if error := _validate_count(count):
        return error
    if error := _validate_offset(offset):
        return error
    if error := _validate_country(country):
        return error
    if error := _validate_freshness(freshness):
        return error

    params: dict[str, Any] = {
        "q": query,
        "count": count,
        "offset": offset,
        "country": country,
        "search_lang": search_lang,
    }

    if freshness:
        params["freshness"] = freshness

    success, result = _make_request("/news/search", params)

    if not success:
        return str(result)
    return _format_news_results(result)  # type: ignore[arg-type]



def image(
    *,
    query: str,
    count: int = 10,
    country: str = "US",
    search_lang: str = "en",
    safesearch: str = "strict",
) -> str:
    """Search for images using Brave Search API.

    Uses the dedicated /images/search endpoint.

    Args:
        query: Search query for images
        count: Number of results (1-20, default: 10)
        country: 2-letter country code (default: "US")
        search_lang: Language code (default: "en")
        safesearch: Content filter - "off" or "strict" (default: "strict")

    Returns:
        Formatted image results with URLs, sizes, and sources

    Example:
        brave.image(query="Python programming logo")
        brave.image(query="architecture diagrams", count=5)
    """
    if error := _validate_query(query):
        return error
    if error := _validate_count(count):
        return error
    if error := _validate_country(country):
        return error
    if error := _validate_safesearch(safesearch, _SAFESEARCH_IMAGE_VALUES):
        return error

    params: dict[str, Any] = {
        "q": query,
        "count": count,
        "country": country,
        "search_lang": search_lang,
        "safesearch": safesearch,
    }

    success, result = _make_request("/images/search", params)

    if not success:
        return str(result)
    return _format_image_results(result)  # type: ignore[arg-type]


def video(
    *,
    query: str,
    count: int = 10,
    country: str = "US",
    search_lang: str = "en",
    freshness: str | None = None,
) -> str:
    """Search for videos using Brave Search API.

    Uses the dedicated /videos/search endpoint.

    Args:
        query: Search query for videos
        count: Number of results (1-20, default: 10)
        country: 2-letter country code (default: "US")
        search_lang: Language code (default: "en")
        freshness: Time filter - "pd" (day), "pw" (week), "pm" (month), "py" (year),
            or date range "YYYY-MM-DDtoYYYY-MM-DD" (e.g. "2024-01-01to2024-06-30")

    Returns:
        Formatted video results with titles, channels, durations, and URLs

    Example:
        brave.video(query="Python tutorial for beginners")
        brave.video(query="tech conference keynote", freshness="pm", count=5)
    """
    if error := _validate_query(query):
        return error
    if error := _validate_count(count):
        return error
    if error := _validate_country(country):
        return error
    if error := _validate_freshness(freshness):
        return error

    params: dict[str, Any] = {
        "q": query,
        "count": count,
        "country": country,
        "search_lang": search_lang,
    }

    if freshness:
        params["freshness"] = freshness

    success, result = _make_request("/videos/search", params)

    if not success:
        return str(result)
    return _format_video_results(result)  # type: ignore[arg-type]


def search_batch(
    *,
    queries: list[tuple[str, str] | str],
    count: int = 2,
    country: str = "US",
    search_lang: str = "en",
    safesearch: str = "moderate",
    freshness: str | None = None,
) -> str:
    """Execute multiple web searches concurrently and return combined results.

    Queries are executed in parallel using threads for better performance.

    Args:
        queries: List of queries. Each item can be:
                 - A string (query text, used as both query and label)
                 - A tuple of (query, label) for custom labeling
        count: Number of results per query (1-20, default: 2)
        country: 2-letter country code for results (default: "US")
        search_lang: Language code for results (default: "en")
        safesearch: Content filter - "off", "moderate", "strict" (default: "moderate")
        freshness: Time filter - "pd" (day), "pw" (week), "pm" (month), "py" (year),
            or date range "YYYY-MM-DDtoYYYY-MM-DD" (e.g. "2024-01-01to2024-06-30")

    Returns:
        Combined formatted results with labels

    Example:
        # Simple list of queries
        brave.search_batch(["scipy", "sqlalchemy", "jupyterlab"])

        # With custom labels
        brave.search_batch([
            ("current Gold price USD/oz today", "Gold (USD/oz)"),
            ("current Silver price USD/oz today", "Silver (USD/oz)"),
            ("current Copper price USD/lb today", "Copper (USD/lb)"),
        ])
    """
    if error := _validate_count(count):
        return error
    if error := _validate_safesearch(safesearch, _SAFESEARCH_WEB_VALUES):
        return error
    if error := _validate_freshness(freshness):
        return error

    normalized = normalize_items(queries)

    if not normalized:
        return "Error: No queries provided"

    # Fall back empty labels to query text
    normalized = [(q, label or q) for q, label in normalized]

    with LogSpan(span="brave.batch", query_count=len(normalized), count=count) as s:

        def _search_one(query: str, label: str) -> tuple[str, str]:
            """Execute a single search and return (label, result)."""
            result = search(
                query=query,
                count=count,
                country=country,
                search_lang=search_lang,
                safesearch=safesearch,
                freshness=freshness,
            )
            return label, result

        results = batch_execute(_search_one, normalized, max_workers=len(normalized))
        output = format_batch_results(results, normalized)
        s.add(outputLen=len(output))
        return output


