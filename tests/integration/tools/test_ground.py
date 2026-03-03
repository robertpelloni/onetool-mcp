"""Live integration tests for grounding search tool.

Requires GEMINI_API_KEY to be configured.
"""

from __future__ import annotations

import pytest

try:
    import google.genai  # noqa: F401
except ImportError:
    pytest.fail("google-genai not installed (install onetool-mcp[util])", pytrace=False)

from .conftest import get_test_secret


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.api
@pytest.mark.tools
class TestGroundingSearchLive:
    """Live integration tests for grounding search tool."""

    @pytest.fixture(autouse=True)
    def skip_if_no_api_key(self):
        """Skip tests if GEMINI_API_KEY is not set."""
        if not get_test_secret("GEMINI_API_KEY"):
            pytest.fail("GEMINI_API_KEY not configured")

    def test_search_live(self):
        """Verify grounding search returns a non-empty result."""
        from otutil.tools.ground import search

        result = search(query="what is python programming language")

        assert len(result) > 0
