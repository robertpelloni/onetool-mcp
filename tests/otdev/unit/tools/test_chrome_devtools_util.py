"""Unit tests for chrome_devtools_util and playwright_util tool packs.

Tests the shared _inject_base logic via the chrome_devtools_util pack,
plus pack structure for both packs.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from otdev.tools import chrome_devtools_util, playwright_util
from otdev._inject_base import _check_server, _exec_js, _extract_result


# =============================================================================
# Module Structure
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestChromeDevtoolsUtilPack:
    def test_pack_name(self):
        assert chrome_devtools_util.pack == "chrome_devtools_util"

    def test_all_exports(self):
        assert set(chrome_devtools_util.__all__) == {
            "inject_annotations",
            "highlight_element",
            "scan_annotations",
            "clear_annotations",
            "guide_user",
        }

    def test_functions_exist(self):
        for name in chrome_devtools_util.__all__:
            assert callable(getattr(chrome_devtools_util, name))


@pytest.mark.unit
@pytest.mark.tools
class TestPlaywrightUtilPack:
    def test_pack_name(self):
        assert playwright_util.pack == "playwright_util"

    def test_all_exports(self):
        assert set(playwright_util.__all__) == {
            "inject_annotations",
            "highlight_element",
            "scan_annotations",
            "clear_annotations",
            "guide_user",
        }

    def test_functions_exist(self):
        for name in playwright_util.__all__:
            assert callable(getattr(playwright_util, name))


# =============================================================================
# Result Extraction
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestExtractResult:
    def test_raw_json_passthrough(self):
        """Raw JSON string (e.g. DevTools) passes through unchanged."""
        raw = '{"ready":true,"version":"2.0.0"}'
        assert _extract_result(raw) == raw

    def test_playwright_markdown_wrapper(self):
        """Playwright markdown wrapper is stripped to just the value."""
        raw = (
            '### Result\n'
            '{"ready":true,"version":"2.0.0"}\n'
            '### Ran Playwright code\n'
            '```js\nawait page.evaluate(...);\n```'
        )
        assert _extract_result(raw) == '{"ready":true,"version":"2.0.0"}'

    def test_playwright_quoted_string(self):
        """Playwright JSON.stringify result with quotes is extracted."""
        raw = (
            '### Result\n'
            '"{\\\"a\\\":1}"\n'
            '### Ran Playwright code\n'
            '```js\n...\n```'
        )
        result = _extract_result(raw)
        assert result == '"{\\\"a\\\":1}"'

    def test_devtools_json_fence(self):
        """DevTools markdown wrapper with json code fence is extracted."""
        raw = (
            '# evaluate_script response\n'
            'Script ran on page and returned:\n'
            '```json\n'
            '{"ready":true,"version":"2.0.0"}\n'
            '```'
        )
        assert _extract_result(raw) == '{"ready":true,"version":"2.0.0"}'

    def test_empty_string(self):
        assert _extract_result("") == ""


# =============================================================================
# Server Connectivity
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestCheckServer:
    def test_connected_server_returns_none(self, mock_proxy_manager):
        mock_proxy_manager.servers = ["chrome-devtools"]
        assert _check_server("chrome-devtools") is None

    def test_disconnected_server_returns_error(self, mock_proxy_manager):
        mock_proxy_manager.servers = []
        err = _check_server("chrome-devtools")
        assert err is not None
        assert "not connected" in err


# =============================================================================
# inject_annotations
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestInjectAnnotations:
    def test_server_not_connected(self, mock_proxy_manager):
        mock_proxy_manager.servers = []
        result = chrome_devtools_util.inject_annotations()
        assert result["success"] is False
        assert "error" in result

    def test_already_injected(self, mock_proxy_manager):
        state = json.dumps({"ready": True, "version": "2.0.0"})
        mock_proxy_manager.servers = ["chrome-devtools"]
        mock_proxy_manager.call_tool_sync.return_value = state
        result = chrome_devtools_util.inject_annotations()
        assert result["success"] is True
        assert result["version"] == "2.0.0"
        # Should only call once (check), not inject
        assert mock_proxy_manager.call_tool_sync.call_count == 1

    def test_fresh_injection(self, mock_proxy_manager):
        not_ready = json.dumps({"ready": False, "version": None})
        ready = json.dumps({"ready": True, "version": "2.0.0"})
        mock_proxy_manager.servers = ["chrome-devtools"]
        mock_proxy_manager.call_tool_sync.side_effect = [not_ready, "undefined", ready]
        with patch("otdev._inject_base.get_inject_script", return_value="// inject.js"):
            result = chrome_devtools_util.inject_annotations()
            assert result["success"] is True
            assert result["version"] == "2.0.0"
            # check + inject + verify = 3 calls
            assert mock_proxy_manager.call_tool_sync.call_count == 3


# =============================================================================
# highlight_element
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestHighlightElement:
    def test_server_not_connected(self, mock_proxy_manager):
        mock_proxy_manager.servers = []
        result = chrome_devtools_util.highlight_element(selector=".btn", label="Click")
        assert result["success"] is False
        assert result["count"] == 0

    def test_successful_highlight(self, mock_proxy_manager):
        response = json.dumps({"success": True, "count": 1, "ids": ["ann-1"]})
        mock_proxy_manager.servers = ["chrome-devtools"]
        mock_proxy_manager.call_tool_sync.return_value = response
        result = chrome_devtools_util.highlight_element(selector=".btn", label="Click")
        assert result["success"] is True
        assert result["count"] == 1

    def test_passes_function_parameter(self, mock_proxy_manager):
        """Verify _eval_js wraps expressions as arrow functions with 'function' key."""
        response = json.dumps({"success": True, "count": 1, "ids": ["ann-1"]})
        mock_proxy_manager.servers = ["chrome-devtools"]
        mock_proxy_manager.call_tool_sync.return_value = response
        chrome_devtools_util.highlight_element(selector=".btn", label="Click")
        call_args = mock_proxy_manager.call_tool_sync.call_args
        assert call_args[0][0] == "chrome-devtools"
        assert call_args[0][1] == "evaluate_script"
        args_dict = call_args[0][2]
        assert "function" in args_dict
        assert "expression" not in args_dict
        assert args_dict["function"].startswith("() => { return ")

    def test_no_matching_elements(self, mock_proxy_manager):
        response = json.dumps({"success": False, "count": 0, "ids": [], "error": "No elements match selector"})
        mock_proxy_manager.servers = ["chrome-devtools"]
        mock_proxy_manager.call_tool_sync.return_value = response
        result = chrome_devtools_util.highlight_element(selector=".nonexistent", label="Test")
        assert result["success"] is False
        assert result["count"] == 0


# =============================================================================
# scan_annotations
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestScanAnnotations:
    def test_server_not_connected(self, mock_proxy_manager):
        mock_proxy_manager.servers = []
        result = chrome_devtools_util.scan_annotations()
        assert result == []

    def test_returns_annotations(self, mock_proxy_manager):
        annotations = [{"id": "ann-1", "label": "Test", "selector": ".btn"}]
        mock_proxy_manager.servers = ["chrome-devtools"]
        mock_proxy_manager.call_tool_sync.return_value = json.dumps(annotations)
        result = chrome_devtools_util.scan_annotations()
        assert len(result) == 1
        assert result[0]["id"] == "ann-1"

    def test_empty_annotations(self, mock_proxy_manager):
        mock_proxy_manager.servers = ["chrome-devtools"]
        mock_proxy_manager.call_tool_sync.return_value = json.dumps([])
        result = chrome_devtools_util.scan_annotations()
        assert result == []


# =============================================================================
# clear_annotations
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestClearAnnotations:
    def test_server_not_connected(self, mock_proxy_manager):
        mock_proxy_manager.servers = []
        result = chrome_devtools_util.clear_annotations()
        assert result["success"] is False

    def test_successful_clear(self, mock_proxy_manager):
        response = json.dumps({"success": True, "cleared": 3})
        mock_proxy_manager.servers = ["chrome-devtools"]
        mock_proxy_manager.call_tool_sync.return_value = response
        result = chrome_devtools_util.clear_annotations()
        assert result["success"] is True
        assert result["cleared"] == 3


# =============================================================================
# guide_user
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestGuideUser:
    def test_server_not_connected(self, mock_proxy_manager):
        mock_proxy_manager.servers = []
        result = chrome_devtools_util.guide_user(
            task="Test", steps=[{"selector": ".a", "label": "A"}]
        )
        assert result["highlighted"] == 0
        assert "error" in result

    def test_successful_guide(self, mock_proxy_manager):
        step_result = json.dumps({"success": True, "count": 1, "ids": ["guide-0"]})
        mock_proxy_manager.servers = ["chrome-devtools"]
        mock_proxy_manager.call_tool_sync.return_value = step_result
        result = chrome_devtools_util.guide_user(
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


# =============================================================================
# Markdown-wrapped responses (integration-style)
# =============================================================================


def _devtools_wrap(value: str) -> str:
    """Wrap a value in DevTools evaluate_script markdown format."""
    return (
        f"# evaluate_script response\n"
        f"Script ran on page and returned:\n"
        f"```json\n{value}\n```"
    )


def _playwright_wrap(value: str) -> str:
    """Wrap a value in Playwright browser_evaluate markdown format."""
    return (
        f"### Result\n{value}\n"
        f"### Ran Playwright code\n```js\nawait page.evaluate(...);\n```"
    )


@pytest.mark.unit
@pytest.mark.tools
class TestDevtoolsWrappedResponses:
    """Verify functions correctly parse DevTools markdown-wrapped responses."""

    def test_highlight_with_devtools_wrapper(self, mock_proxy_manager):
        wrapped = _devtools_wrap('{"success":true,"count":1,"ids":["ann-1"]}')
        mock_proxy_manager.servers = ["chrome-devtools"]
        mock_proxy_manager.call_tool_sync.return_value = wrapped
        result = chrome_devtools_util.highlight_element(selector=".btn", label="Click")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["ids"] == ["ann-1"]

    def test_scan_with_devtools_wrapper(self, mock_proxy_manager):
        annotations = [{"id": "ann-1", "label": "Test"}]
        wrapped = _devtools_wrap(json.dumps(annotations))
        mock_proxy_manager.servers = ["chrome-devtools"]
        mock_proxy_manager.call_tool_sync.return_value = wrapped
        result = chrome_devtools_util.scan_annotations()
        assert len(result) == 1
        assert result[0]["id"] == "ann-1"

    def test_inject_already_ready_with_devtools_wrapper(self, mock_proxy_manager):
        wrapped = _devtools_wrap('{"ready":true,"version":"2.0.0"}')
        mock_proxy_manager.servers = ["chrome-devtools"]
        mock_proxy_manager.call_tool_sync.return_value = wrapped
        result = chrome_devtools_util.inject_annotations()
        assert result["success"] is True
        assert result["version"] == "2.0.0"


@pytest.mark.unit
@pytest.mark.tools
class TestPlaywrightWrappedResponses:
    """Verify functions correctly parse Playwright markdown-wrapped responses."""

    def test_highlight_with_playwright_wrapper(self, mock_proxy_manager):
        wrapped = _playwright_wrap('{"success":true,"count":2,"ids":["a","b"]}')
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.return_value = wrapped
        result = playwright_util.highlight_element(selector="button", label="Go")
        assert result["success"] is True
        assert result["count"] == 2

    def test_clear_with_playwright_wrapper(self, mock_proxy_manager):
        wrapped = _playwright_wrap('{"success":true,"cleared":3}')
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.return_value = wrapped
        result = playwright_util.clear_annotations()
        assert result["success"] is True
        assert result["cleared"] == 3


# =============================================================================
# _exec_js
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestExecJs:
    def test_wraps_script_without_return(self, mock_proxy_manager):
        """_exec_js wraps script as () => { <script> } (no return keyword)."""
        mock_proxy_manager.call_tool_sync.return_value = "undefined"
        _exec_js("chrome-devtools", "evaluate_script", "console.log('hi')")
        call_args = mock_proxy_manager.call_tool_sync.call_args
        fn = call_args[0][2]["function"]
        assert fn.startswith("() => {")
        assert "return" not in fn
        assert "console.log('hi')" in fn

    def test_extracts_result_from_wrapped_response(self, mock_proxy_manager):
        """_exec_js applies _extract_result to the response."""
        wrapped = _playwright_wrap("undefined")
        mock_proxy_manager.call_tool_sync.return_value = wrapped
        result = _exec_js("playwright", "browser_evaluate", "void 0")
        assert result == "undefined"


# =============================================================================
# Playwright pack uses different server
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestPlaywrightRouting:
    def test_calls_playwright_server(self, mock_proxy_manager):
        response = json.dumps({"success": True, "cleared": 0})
        mock_proxy_manager.servers = ["playwright"]
        mock_proxy_manager.call_tool_sync.return_value = response
        playwright_util.clear_annotations()
        mock_proxy_manager.call_tool_sync.assert_called_once()
        call_args = mock_proxy_manager.call_tool_sync.call_args
        assert call_args[0][0] == "playwright"
        assert call_args[0][1] == "browser_evaluate"
        # Verify function parameter format
        args_dict = call_args[0][2]
        assert "function" in args_dict
        assert args_dict["function"].startswith("() => {")
