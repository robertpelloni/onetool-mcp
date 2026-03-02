"""Integration tests for the play_util (Playwright annotation) tool pack.

These tests run against a live Playwright browser. They verify that inject.js
actually works end-to-end — injection, highlighting, scanning, clearing, and
guided workflow highlights.

Focus: browser-side inject.js behavior, NOT Python logic (covered by unit tests).

Prerequisites:
  - The `playwright` MCP server must be connected to the live proxy manager.

Run command:
  uv run pytest tests/otdev/integration/tools/test_play_util.py -m integration -v
"""

from __future__ import annotations

import contextlib

import pytest

from ot.proxy import get_proxy_manager

# A minimal HTML page with known elements for annotation testing.
# Using data: URI avoids network dependency.
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _navigate_test_page():
    """Navigate to a simple test page before each test; clear after."""
    proxy = get_proxy_manager()
    proxy.call_tool_sync("playwright", "browser_navigate", {"url": _TEST_PAGE})
    yield
    with contextlib.suppress(Exception):
        from otdev.tools import play_util
        play_util.clear_annotations()


# ---------------------------------------------------------------------------
# 1. inject + highlight + scan + clear lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestAnnotationLifecycle:
    """Verify the full inject → highlight → scan → clear lifecycle."""

    def test_inject_highlight_scan_clear(self) -> None:
        from otdev.tools import play_util

        # Inject — should succeed and report ready
        inject_result = play_util.inject_annotations()
        assert inject_result["success"] is True, f"inject failed: {inject_result}"
        assert inject_result["ready"] is True

        # Idempotent re-inject
        inject2 = play_util.inject_annotations()
        assert inject2["success"] is True, "re-inject should succeed"

        # Highlight a single element by ID
        hl = play_util.highlight_element(selector="#title", label="Page Title")
        assert hl["success"] is True, f"highlight failed: {hl}"
        assert hl["count"] == 1, f"expected 1 match, got {hl['count']}"
        assert len(hl["ids"]) == 1

        # Highlight multiple elements by class
        hl2 = play_util.highlight_element(
            selector=".btn", label="Buttons", color="blue"
        )
        assert hl2["success"] is True, f"highlight .btn failed: {hl2}"
        assert hl2["count"] == 2, f"expected 2 buttons, got {hl2['count']}"

        # Scan — should find all 3 annotations (1 title + 2 buttons)
        annotations = play_util.scan_annotations()
        assert len(annotations) >= 3, (
            f"expected >= 3 annotations, got {len(annotations)}: {annotations}"
        )
        labels = {a.get("label") for a in annotations}
        assert "Page Title" in labels, f"'Page Title' not in scanned labels: {labels}"
        assert "Buttons" in labels, f"'Buttons' not in scanned labels: {labels}"

        # Clear — should remove all
        clear = play_util.clear_annotations()
        assert clear["success"] is True, f"clear failed: {clear}"
        assert clear["cleared"] >= 3, f"expected >= 3 cleared, got {clear['cleared']}"

        # Scan after clear — should be empty
        after_clear = play_util.scan_annotations()
        assert len(after_clear) == 0, (
            f"annotations remain after clear: {after_clear}"
        )


# ---------------------------------------------------------------------------
# 2. highlight with custom element_id and no-match selector
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestHighlightEdgeCases:
    """Verify highlight handles custom IDs and missing selectors."""

    def test_custom_id_and_no_match(self) -> None:
        from otdev.tools import play_util

        # Custom element_id
        hl = play_util.highlight_element(
            selector="#btn-submit",
            label="Submit Btn",
            element_id="custom-submit",
        )
        assert hl["success"] is True, f"highlight with custom id failed: {hl}"
        assert "custom-submit" in hl["ids"], f"custom id not in result: {hl['ids']}"

        # No-match selector — should return count 0
        hl_miss = play_util.highlight_element(
            selector="#nonexistent-element", label="Ghost"
        )
        assert hl_miss.get("count", 0) == 0, (
            f"expected 0 matches for missing selector: {hl_miss}"
        )


# ---------------------------------------------------------------------------
# 3. guide_user — multi-step workflow highlights
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestGuideUser:
    """Verify guide_user highlights multiple steps at once."""

    def test_guide_user_workflow(self) -> None:
        from otdev.tools import play_util

        result = play_util.guide_user(
            task="Fill and submit form",
            steps=[
                {"selector": "#name-input", "label": "1. Enter name"},
                {"selector": "#btn-submit", "label": "2. Click submit", "color": "green"},
                {"selector": "#nonexistent", "label": "3. Missing step"},
            ],
        )

        assert result["task"] == "Fill and submit form"
        assert result["total"] == 3
        # Two of three steps should succeed (the third selector doesn't exist)
        assert result["highlighted"] >= 2, (
            f"expected >= 2 highlighted, got {result['highlighted']}: {result['results']}"
        )

        # Verify per-step results
        step_results = result["results"]
        assert step_results[0]["success"] is True, f"step 0 failed: {step_results[0]}"
        assert step_results[1]["success"] is True, f"step 1 failed: {step_results[1]}"

        # Scan should show the successful annotations
        annotations = play_util.scan_annotations()
        labels = {a.get("label") for a in annotations}
        assert "1. Enter name" in labels
        assert "2. Click submit" in labels
