"""Live integration tests for Tavily search tool.

Requires TAVILY_API_KEY to be configured in tests/.onetool/secrets.yaml.
"""

from __future__ import annotations

import pytest

from .conftest import get_test_secret


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.api
@pytest.mark.tools
class TestTavilySearchLive:
    """Live integration tests for Tavily search."""

    @pytest.fixture(autouse=True)
    def require_api_key(self):
        # Integration tests require a real API key — they test live API behaviour.
        # Configure TAVILY_API_KEY in tests/.onetool/secrets.yaml before running.
        if not get_test_secret("TAVILY_API_KEY"):
            pytest.fail("TAVILY_API_KEY not configured in tests/.onetool/secrets.yaml")

    def test_search_returns_results(self):
        """Verify Tavily search returns non-error results."""
        from otutil.tools.tavily import search

        result = search(query="python async programming", max_results=3)

        assert isinstance(result, str)
        assert "Error" not in result or "TAVILY_API_KEY" not in result
        assert len(result) > 0

    def test_extract_returns_content(self):
        """Verify Tavily extract fetches page content."""
        from otutil.tools.tavily import extract

        result = extract(urls=["https://docs.python.org/3/library/asyncio.html"])

        assert isinstance(result, str)
        assert "Error" not in result or "TAVILY_API_KEY" not in result
        assert len(result) > 0
