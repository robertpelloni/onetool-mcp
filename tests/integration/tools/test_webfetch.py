"""Live integration tests for web fetch tool.

Requires trafilatura to be installed.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestWebFetchLive:
    """Live integration tests for web fetch tool."""

    @pytest.fixture(autouse=True)
    def require_trafilatura(self):
        """Skip if trafilatura is not installed."""
        pytest.importorskip("trafilatura", reason="trafilatura not installed ([dev] extra)")

    def test_fetch_live(self):
        """Verify web fetch works with a real URL."""
        from otdev.tools.webfetch import fetch

        result = fetch(
            url="https://github.com/about",
            output_format="text",
            timeout=15.0,
            use_cache=False,
        )

        assert "GitHub" in result or "github" in result.lower() or len(result) > 100
