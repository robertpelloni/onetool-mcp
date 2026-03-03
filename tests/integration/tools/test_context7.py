"""Live integration tests for Context7 tool.

Requires CONTEXT7_API_KEY to be configured.
"""

from __future__ import annotations

import pytest

from .conftest import get_test_secret


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.api
@pytest.mark.tools
class TestContext7Live:
    """Live integration tests for Context7 tool."""

    @pytest.fixture(autouse=True)
    def skip_if_unavailable(self):
        """Skip tests if Context7 is not available or API key not set."""
        if not get_test_secret("CONTEXT7_API_KEY"):
            pytest.fail("CONTEXT7_API_KEY not configured")

        try:
            from otdev.tools import context7  # noqa: F401
        except (ImportError, TypeError) as e:
            pytest.fail(f"context7 module not available: {e}")

    def test_search_live(self):
        """Verify Context7 library search works."""
        from otdev.tools.context7 import search

        result = search(query="fastapi", library_name="fastapi")

        assert "fastapi" in result.lower() or "Context7" in result
