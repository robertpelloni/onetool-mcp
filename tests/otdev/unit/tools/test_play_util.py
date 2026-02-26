"""Unit tests for play_util tool pack.

Tests the play_util public API: inject_annotations, highlight_element,
scan_annotations, clear_annotations, and guide_user. Verifies that all calls
route to the "playwright" server with the "browser_evaluate" tool.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from otdev.tools import play_util

# Ready state returned by _ensure_injected check call
_READY = json.dumps({"ready": True, "version": "2.0.0"})


# =============================================================================
# Module Structure
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestPlaywrightUtilPack:
    def test_pack_name(self):
        assert play_util.pack == "play_util"

    def test_all_exports(self):
        assert set(play_util.__all__) == {
            "inject_annotations",
            "highlight_element",
            "scan_annotations",
            "clear_annotations",
            "guide_user",
        }

    def test_functions_exist(self):
        for name in play_util.__all__:
            assert callable(getattr(play_util, name))


# =============================================================================
# Helpers
# =============================================================================


def _pw_wrap(value: str) -> str:
    """Wrap a value in Playwright browser_evaluate markdown format."""
    return (
        f"### Result\n{value}\n"
        f"### Ran Playwright code\n```js\nawait page.evaluate(...);\n```"
    )


def _assert_routed_to_playwright(mock_proxy_manager):
    """Assert the last call went to playwright/browser_evaluate."""
    call_args = mock_proxy_manager.call_tool_sync.call_args
    assert call_args[0][0] == "playwright"
    assert call_args[0][1] == "browser_evaluate"


# =============================================================================
# inject_annotations
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestInjectAnnotations:
    def test_server_not_connected(self, mock_proxy_manager):
        mock_proxy_manager.servers = []
        result = play_util.inject_annotations()
        assert result["success"] is False
        assert "error" in result

    def test_already_injected(self, mock_proxy_manager):
        state = json.dumps({"ready": True, "version": "2.0.0"})
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.return_value = state
        result = play_util.inject_annotations()
        assert result["success"] is True
        assert result["version"] == "2.0.0"
        assert mock_proxy_manager.call_tool_sync.call_count == 1

    def test_fresh_injection(self, mock_proxy_manager):
        not_ready = json.dumps({"ready": False, "version": None})
        ready = json.dumps({"ready": True, "version": "2.0.0"})
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.side_effect = [not_ready, "undefined", ready]
        with patch("otdev._inject_base.get_inject_script", return_value="// inject.js"):
            result = play_util.inject_annotations()
            assert result["success"] is True
            assert result["version"] == "2.0.0"
            # check + inject + verify = 3 calls
            assert mock_proxy_manager.call_tool_sync.call_count == 3

    def test_already_injected_with_playwright_wrapper(self, mock_proxy_manager):
        wrapped = _pw_wrap('{"ready":true,"version":"2.0.0"}')
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.return_value = wrapped
        result = play_util.inject_annotations()
        assert result["success"] is True
        assert result["version"] == "2.0.0"

    def test_routes_to_playwright(self, mock_proxy_manager):
        state = json.dumps({"ready": True, "version": "2.0.0"})
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.return_value = state
        play_util.inject_annotations()
        _assert_routed_to_playwright(mock_proxy_manager)


# =============================================================================
# highlight_element
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestHighlightElement:
    def test_server_not_connected(self, mock_proxy_manager):
        mock_proxy_manager.servers = []
        result = play_util.highlight_element(selector=".btn", label="Click")
        assert result["success"] is False
        assert result["count"] == 0

    def test_successful_highlight(self, mock_proxy_manager):
        response = json.dumps({"success": True, "count": 1, "ids": ["ann-1"]})
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.side_effect = [_READY, response]
        result = play_util.highlight_element(selector=".btn", label="Click")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["ids"] == ["ann-1"]

    def test_custom_color(self, mock_proxy_manager):
        response = json.dumps({"success": True, "count": 1, "ids": ["ann-1"]})
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.side_effect = [_READY, response]
        result = play_util.highlight_element(selector="a", label="Link", color="blue")
        assert result["success"] is True

    def test_custom_element_id(self, mock_proxy_manager):
        response = json.dumps({"success": True, "count": 1, "ids": ["my-id"]})
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.side_effect = [_READY, response]
        result = play_util.highlight_element(
            selector="input", label="Field", element_id="my-id"
        )
        assert result["ids"] == ["my-id"]

    def test_no_matching_elements(self, mock_proxy_manager):
        response = json.dumps({"success": False, "count": 0, "ids": [], "error": "No elements match selector"})
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.return_value = response
        result = play_util.highlight_element(selector=".nonexistent", label="Test")
        assert result["success"] is False
        assert result["count"] == 0

    def test_playwright_wrapped_response(self, mock_proxy_manager):
        ready_wrapped = _pw_wrap('{"ready":true,"version":"2.0.0"}')
        wrapped = _pw_wrap('{"success":true,"count":2,"ids":["a","b"]}')
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.side_effect = [ready_wrapped, wrapped]
        result = play_util.highlight_element(selector="button", label="Go")
        assert result["success"] is True
        assert result["count"] == 2

    def test_routes_to_playwright(self, mock_proxy_manager):
        response = json.dumps({"success": True, "count": 1, "ids": ["ann-1"]})
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.return_value = response
        play_util.highlight_element(selector=".btn", label="Click")
        _assert_routed_to_playwright(mock_proxy_manager)
        args_dict = mock_proxy_manager.call_tool_sync.call_args[0][2]
        assert "function" in args_dict
        assert args_dict["function"].startswith("() => { return ")


# =============================================================================
# scan_annotations
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestScanAnnotations:
    def test_server_not_connected(self, mock_proxy_manager):
        mock_proxy_manager.servers = []
        result = play_util.scan_annotations()
        assert result == []

    def test_returns_annotations(self, mock_proxy_manager):
        annotations = [{"id": "ann-1", "label": "Test", "selector": ".btn"}]
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.side_effect = [_READY, json.dumps(annotations)]
        result = play_util.scan_annotations()
        assert len(result) == 1
        assert result[0]["id"] == "ann-1"

    def test_empty_annotations(self, mock_proxy_manager):
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.return_value = json.dumps([])
        result = play_util.scan_annotations()
        assert result == []

    def test_playwright_wrapped_response(self, mock_proxy_manager):
        annotations = [{"id": "ann-1", "label": "Test"}]
        ready_wrapped = _pw_wrap('{"ready":true,"version":"2.0.0"}')
        wrapped = _pw_wrap(json.dumps(annotations))
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.side_effect = [ready_wrapped, wrapped]
        result = play_util.scan_annotations()
        assert len(result) == 1
        assert result[0]["id"] == "ann-1"

    def test_routes_to_playwright(self, mock_proxy_manager):
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.return_value = json.dumps([])
        play_util.scan_annotations()
        _assert_routed_to_playwright(mock_proxy_manager)


# =============================================================================
# clear_annotations
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestClearAnnotations:
    def test_server_not_connected(self, mock_proxy_manager):
        mock_proxy_manager.servers = []
        result = play_util.clear_annotations()
        assert result["success"] is False

    def test_successful_clear(self, mock_proxy_manager):
        response = json.dumps({"success": True, "cleared": 3})
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.return_value = response
        result = play_util.clear_annotations()
        assert result["success"] is True
        assert result["cleared"] == 3

    def test_playwright_wrapped_response(self, mock_proxy_manager):
        wrapped = _pw_wrap('{"success":true,"cleared":3}')
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.return_value = wrapped
        result = play_util.clear_annotations()
        assert result["success"] is True
        assert result["cleared"] == 3

    def test_routes_to_playwright(self, mock_proxy_manager):
        response = json.dumps({"success": True, "cleared": 0})
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.return_value = response
        play_util.clear_annotations()
        mock_proxy_manager.call_tool_sync.assert_called_once()
        _assert_routed_to_playwright(mock_proxy_manager)
        args_dict = mock_proxy_manager.call_tool_sync.call_args[0][2]
        assert "function" in args_dict
        assert args_dict["function"].startswith("() => {")


# =============================================================================
# guide_user
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestGuideUser:
    def test_server_not_connected(self, mock_proxy_manager):
        mock_proxy_manager.servers = []
        result = play_util.guide_user(
            task="Test", steps=[{"selector": ".a", "label": "A"}]
        )
        assert result["highlighted"] == 0
        assert "error" in result

    def test_successful_guide(self, mock_proxy_manager):
        step_result = json.dumps({"success": True, "count": 1, "ids": ["guide-0"]})
        mock_proxy_manager.servers = ["playwright"]
        # ready check + 2 step calls
        mock_proxy_manager.call_tool_sync.side_effect = [_READY, step_result, step_result]
        result = play_util.guide_user(
            task="Fill form",
            steps=[
                {"selector": "input[name='name']", "label": "Enter name"},
                {"selector": "button[type='submit']", "label": "Submit"},
            ],
        )
        assert result["task"] == "Fill form"
        assert result["total"] == 2
        assert result["highlighted"] == 2
        assert len(result["results"]) == 2

    def test_single_step(self, mock_proxy_manager):
        step_result = json.dumps({"success": True, "count": 1, "ids": ["guide-0"]})
        mock_proxy_manager.servers = ["playwright"]
        # ready check + 1 step call
        mock_proxy_manager.call_tool_sync.side_effect = [_READY, step_result]
        result = play_util.guide_user(
            task="Click button",
            steps=[{"selector": "button", "label": "Press me"}],
        )
        assert result["total"] == 1
        assert result["highlighted"] == 1

    def test_step_with_custom_color(self, mock_proxy_manager):
        step_result = json.dumps({"success": True, "count": 1, "ids": ["guide-0"]})
        mock_proxy_manager.servers = ["playwright"]
        # ready check + 1 step call
        mock_proxy_manager.call_tool_sync.side_effect = [_READY, step_result]
        result = play_util.guide_user(
            task="Highlight",
            steps=[{"selector": ".a", "label": "A", "color": "red"}],
        )
        assert result["highlighted"] == 1

    def test_routes_to_playwright(self, mock_proxy_manager):
        step_result = json.dumps({"success": True, "count": 1, "ids": ["guide-0"]})
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.return_value = step_result
        play_util.guide_user(
            task="Test",
            steps=[{"selector": ".btn", "label": "Click"}],
        )
        _assert_routed_to_playwright(mock_proxy_manager)
