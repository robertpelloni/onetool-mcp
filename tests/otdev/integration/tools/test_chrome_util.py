"""Integration tests for the chrome_util (Chrome DevTools annotation) tool pack.

Verifies inject.js works end-to-end — injection, highlighting, scanning,
clearing, and guided workflow. Uses a data: URI page to avoid network deps.

Prerequisites:
  chrome-devtools MCP server configured in tests/.onetool/onetool.yaml.

Run:
  uv run pytest tests/otdev/integration/tools/test_chrome_util.py -m integration -v
"""

from __future__ import annotations

import contextlib

import pytest

from .conftest import require_server

pytestmark = [pytest.mark.integration, pytest.mark.tools]

_TEST_PAGE = (
    "data:text/html,"
    "<html><body>"
    "<h1 id='title'>Test Page</h1>"
    "<button id='btn-submit' class='btn primary'>Submit</button>"
    "<button id='btn-cancel' class='btn secondary'>Cancel</button>"
    "<input id='name-input' type='text' placeholder='Name' />"
    "<div id='content'><p class='info'>Hello world</p></div>"
    "</body></html>"
)


@pytest.fixture(scope="module", autouse=True)
def _browser_session():
    """Navigate to the test page once for the whole module; close page at end."""
    require_server("chrome-devtools")

    from ot.proxy.manager import get_proxy_manager

    proxy = get_proxy_manager()
    proxy.call_tool_sync("chrome-devtools", "navigate_page", {"url": _TEST_PAGE})
    yield
    with contextlib.suppress(Exception):
        proxy.call_tool_sync("chrome-devtools", "close_page", {})


@pytest.fixture(autouse=True)
def _clean_state():
    """Clear all annotations before and after each test."""
    from otdev.tools import chrome_util

    with contextlib.suppress(Exception):
        chrome_util.clear_annotations()
    yield
    with contextlib.suppress(Exception):
        chrome_util.clear_annotations()


class TestAnnotationLifecycle:
    """Full inject → highlight → scan → clear lifecycle."""

    def test_lifecycle(self) -> None:
        """inject, highlight, scan, and clear work end-to-end."""
        from otdev.tools import chrome_util

        # inject — idempotent
        inject = chrome_util.inject_annotations()
        assert inject["success"] is True and inject["ready"] is True
        assert chrome_util.inject_annotations()["success"] is True

        # highlight single element and multiple by class
        hl = chrome_util.highlight_element(selector="#title", label="Title")
        assert hl["success"] is True and hl["count"] == 1

        hl2 = chrome_util.highlight_element(selector=".btn", label="Buttons", color="blue")
        assert hl2["success"] is True and hl2["count"] == 2

        # scan — finds all annotations
        anns = chrome_util.scan_annotations()
        labels = {a.get("label") for a in anns}
        assert "Title" in labels and "Buttons" in labels

        # clear — removes all; scan returns empty
        cleared = chrome_util.clear_annotations()
        assert cleared["success"] is True and cleared["cleared"] >= 3
        assert chrome_util.scan_annotations() == []


class TestGuideUser:
    """guide_user highlights multiple steps; missing selectors handled gracefully."""

    def test_guide_and_edge_cases(self) -> None:
        """custom element_id preserved; missing selector returns count 0; guide_user works."""
        from otdev.tools import chrome_util

        # custom element_id is preserved in result
        hl = chrome_util.highlight_element(
            selector="#btn-submit", label="Submit Btn", element_id="custom-submit"
        )
        assert hl["success"] is True and "custom-submit" in hl["ids"]

        # no-match selector returns count 0
        assert chrome_util.highlight_element(selector="#nonexistent", label="Ghost")["count"] == 0

        # guide_user: 2 of 3 steps succeed (third selector is missing)
        result = chrome_util.guide_user(
            task="Fill and submit",
            steps=[
                {"selector": "#name-input", "label": "1. Enter name"},
                {"selector": "#btn-submit", "label": "2. Click submit", "color": "green"},
                {"selector": "#nonexistent", "label": "3. Missing step"},
            ],
        )
        assert result["task"] == "Fill and submit"
        assert result["total"] == 3
        assert result["highlighted"] >= 2
        assert result["results"][0]["success"] is True
        assert result["results"][1]["success"] is True
