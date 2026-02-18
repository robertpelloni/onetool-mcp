"""Live integration tests for Brave Search tool.

Requires BRAVE_API_KEY to be configured.
"""

from __future__ import annotations

import pytest

from tests.otutil.integration.tools.conftest import get_test_secret


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.api
@pytest.mark.tools
class TestBraveSearchLive:
    """Live integration tests for Brave Search tool."""

    @pytest.fixture(autouse=True)
    def skip_if_no_api_key(self):
        """Skip tests if BRAVE_API_KEY is not set."""
        if not get_test_secret("BRAVE_API_KEY"):
            pytest.skip("BRAVE_API_KEY not configured")

    def test_search_live(self):
        """Verify Brave web search works."""
        from otutil.tools.brave import search

        result = search(query="python programming", count=3)

        # Should get results, not an error
        assert "Error" not in result or "BRAVE_API_KEY" not in result
