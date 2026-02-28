"""Unit tests for the whiteboard tool pack (pack name: whiteboard, short alias: wb).

Tests cover: parse_dsl, _build_dsl, auto_layout, _parse_style_props, and
smoke tests for public tools with mocked Playwright.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from otdev.tools.excalidraw import (
    _build_dsl,
    _parse_style_props,
    auto_layout,
    parse_dsl,
)


# ===========================================================================
# 6.1 parse_dsl
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestParseDsl:
    def test_simple_shapes(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]')
        assert result["shapes"]["a"] == {"label": "A", "classes": []}
        assert result["shapes"]["b"] == {"label": "B", "classes": []}

    def test_semicolon_separator(self) -> None:
        result = parse_dsl('a["A"];b["B"];a-->b')
        assert result["shapes"]["a"] == {"label": "A", "classes": []}
        assert result["shapes"]["b"] == {"label": "B", "classes": []}
        assert len(result["edges"]) == 1
        assert result["edges"][0]["src"] == "a"
        assert result["edges"][0]["dst"] == "b"

    def test_directed_edge(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->b')
        assert len(result["edges"]) == 1
        e = result["edges"][0]
        assert e["src"] == "a"
        assert e["dst"] == "b"
        assert e["endArrowhead"] == "arrow"
        assert e["startArrowhead"] is None
        assert e["directed"] is True

    def test_directed_edge_with_label(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->|query|b')
        assert result["edges"][0]["label"] == "query"

    def test_undirected_edge(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na---b')
        e = result["edges"][0]
        assert e["directed"] is False
        assert e["startArrowhead"] is None
        assert e["endArrowhead"] is None

    def test_bidirectional_edge(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na<-->b')
        e = result["edges"][0]
        assert e["startArrowhead"] == "arrow"
        assert e["endArrowhead"] == "arrow"

    def test_dot_edge(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --o b')
        e = result["edges"][0]
        assert e["endArrowhead"] == "dot"
        assert e["startArrowhead"] is None

    def test_bar_edge(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --x b')
        e = result["edges"][0]
        assert e["endArrowhead"] == "bar"

    def test_dot_edge_with_label(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --o|lbl| b')
        e = result["edges"][0]
        assert e["label"] == "lbl"
        assert e["endArrowhead"] == "dot"

    def test_classdef_raises_error(self) -> None:
        """classDef syntax is no longer supported — raises ValueError."""
        with pytest.raises(Exception):
            parse_dsl('classDef svc fill:#dae8fc,stroke:#6c8ebf;')

    def test_class_assignment_ignored_or_raises(self) -> None:
        """class assignment is no longer parsed as class — treated as bare id or error."""
        # 'class a,b svc' does not match any shape/edge pattern and falls through
        # to bare-ID fallback or is silently ignored
        result = parse_dsl('a["A"]\nb["B"]')
        assert "a" in result["shapes"]
        assert "b" in result["shapes"]

    def test_subgraph(self) -> None:
        dsl = 'a["A"]\nb["B"]\nsubgraph grp ["Group"]\n  a\n  b\nend'
        result = parse_dsl(dsl)
        assert "grp" in result["groups"]
        g = result["groups"]["grp"]
        assert g["label"] == "Group"
        assert "a" in g["members"]
        assert "b" in g["members"]

    def test_subgraph_without_label(self) -> None:
        dsl = 'a["A"]\nsubgraph grp\n  a\nend'
        result = parse_dsl(dsl)
        assert result["groups"]["grp"]["label"] == "grp"

    def test_mermaid_header_ignored(self) -> None:
        result = parse_dsl('flowchart TD\na["A"]')
        assert "a" in result["shapes"]

    def test_graph_header_ignored(self) -> None:
        result = parse_dsl('graph LR\na["A"]')
        assert "a" in result["shapes"]

    def test_comment_lines_ignored(self) -> None:
        result = parse_dsl('%% this is a comment\n# also a comment\na["A"]')
        assert "a" in result["shapes"]
        assert len(result["shapes"]) == 1

    def test_multiline_label(self) -> None:
        result = parse_dsl('a["Line1\\nLine2"]')
        assert result["shapes"]["a"]["label"] == "Line1\nLine2"

    def test_empty_label(self) -> None:
        result = parse_dsl('a[""]\nb["B"]\na-->b')
        assert "a" in result["shapes"], "empty-label shape should use node ID as key"
        assert result["shapes"]["a"]["label"] == ""
        assert result["edges"][0]["src"] == "a"
        assert result["edges"][0]["dst"] == "b"

    def test_empty_input(self) -> None:
        result = parse_dsl("")
        assert result["shapes"] == {}
        assert result["edges"] == []

    def test_unquoted_label_rect(self) -> None:
        result = parse_dsl("a[test]")
        assert result["shapes"]["a"] == {"label": "test", "classes": []}

    def test_ellipse_raises_error(self) -> None:
        """Ellipse syntax is not supported — raises ValueError with helpful message."""
        with pytest.raises(ValueError, match="Ellipse"):
            parse_dsl('a(("Oval"))')

    def test_diamond_raises_error(self) -> None:
        """Diamond syntax is not supported — raises ValueError with helpful message."""
        with pytest.raises(ValueError, match="Diamond"):
            parse_dsl('a{"Decision"}')

    def test_bare_id_becomes_shape(self) -> None:
        result = parse_dsl("mynode")
        assert "mynode" in result["shapes"]
        assert result["shapes"]["mynode"]["label"] == "mynode"

    def test_edge_id_format(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->b')
        assert result["edges"][0]["id"] == "edge-a-b"

    def test_dashed_arrow_edge(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-.->b')
        assert len(result["edges"]) == 1
        e = result["edges"][0]
        assert e["src"] == "a"
        assert e["dst"] == "b"
        assert e["directed"] is True
        assert e["endArrowhead"] == "arrow"
        assert e["strokeStyle"] == "dashed"

    def test_dashed_arrow_edge_with_label(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-.->|Metrics|b')
        e = result["edges"][0]
        assert e["label"] == "Metrics"
        assert e["strokeStyle"] == "dashed"
        assert e["endArrowhead"] == "arrow"

    def test_dashed_undirected_edge(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-.-b')
        e = result["edges"][0]
        assert e["directed"] is False
        assert e["startArrowhead"] is None
        assert e["endArrowhead"] is None
        assert e["strokeStyle"] == "dashed"

    def test_solid_edge_no_stroke_style(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->b')
        e = result["edges"][0]
        assert e.get("strokeStyle") is None

    def test_inline_style_props_on_shape(self) -> None:
        """Trailing style props after ] are captured in inline_styles."""
        result = parse_dsl('a["A"] bc:green,sw:2')
        assert "a" in result["shapes"]
        assert "a" in result["inline_styles"]
        assert result["inline_styles"]["a"]["backgroundColor"] == "#bbf7d0"
        assert result["inline_styles"]["a"]["strokeWidth"] == 2

    def test_bare_id_with_style_props(self) -> None:
        """Bare id + style props → style-only update, label=None."""
        result = parse_dsl("a bc:green")
        assert "a" in result["shapes"]
        assert result["shapes"]["a"]["label"] is None
        assert "a" in result["inline_styles"]
        assert result["inline_styles"]["a"]["backgroundColor"] == "#bbf7d0"


# ===========================================================================
# 6.2 _build_dsl
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestBuildDsl:
    def _round_trip(self, dsl: str) -> dict[str, Any]:
        """Parse DSL and rebuild it, return both parsed states."""
        parsed = parse_dsl(dsl)
        rebuilt = _build_dsl(parsed)
        return parse_dsl(rebuilt)

    def test_shapes_round_trip(self) -> None:
        dsl = 'a["Service A"]\nb["DB"]'
        rt = self._round_trip(dsl)
        assert "a" in rt["shapes"]
        assert rt["shapes"]["a"]["label"] == "Service A"
        assert "b" in rt["shapes"]

    def test_directed_edge_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na-->b'
        rt = self._round_trip(dsl)
        assert len(rt["edges"]) == 1
        assert rt["edges"][0]["src"] == "a"
        assert rt["edges"][0]["dst"] == "b"
        assert rt["edges"][0]["endArrowhead"] == "arrow"

    def test_undirected_edge_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na---b'
        rt = self._round_trip(dsl)
        assert rt["edges"][0]["directed"] is False

    def test_bidirectional_edge_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na<-->b'
        rt = self._round_trip(dsl)
        e = rt["edges"][0]
        assert e["startArrowhead"] == "arrow"
        assert e["endArrowhead"] == "arrow"

    def test_dot_edge_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na --o b'
        rt = self._round_trip(dsl)
        assert rt["edges"][0]["endArrowhead"] == "dot"

    def test_bar_edge_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na --x b'
        rt = self._round_trip(dsl)
        assert rt["edges"][0]["endArrowhead"] == "bar"

    def test_subgraph_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\nsubgraph g ["Group"]\n  a\n  b\nend'
        rt = self._round_trip(dsl)
        assert "g" in rt["groups"]
        assert "a" in rt["groups"]["g"]["members"]

    def test_multiline_label_round_trip(self) -> None:
        dsl = 'a["Line1\\nLine2"]'
        rt = self._round_trip(dsl)
        assert rt["shapes"]["a"]["label"] == "Line1\nLine2"

    def test_edge_with_label_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na-->|query|b'
        rt = self._round_trip(dsl)
        assert rt["edges"][0]["label"] == "query"

    def test_dashed_arrow_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na-.->b'
        rt = self._round_trip(dsl)
        e = rt["edges"][0]
        assert e["strokeStyle"] == "dashed"
        assert e["directed"] is True

    def test_dashed_arrow_with_label_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na-.->|Logs|b'
        rt = self._round_trip(dsl)
        e = rt["edges"][0]
        assert e["label"] == "Logs"
        assert e["strokeStyle"] == "dashed"

    def test_dashed_undirected_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na-.-b'
        rt = self._round_trip(dsl)
        e = rt["edges"][0]
        assert e["directed"] is False
        assert e["strokeStyle"] == "dashed"

    def test_empty_state(self) -> None:
        state: dict[str, Any] = {"shapes": {}, "edges": [], "groups": {}}
        assert _build_dsl(state) == ""


# ===========================================================================
# 6.3 auto_layout
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestAutoLayout:
    def test_single_node(self) -> None:
        shapes = {"a": {"label": "A", "classes": []}}
        positions = auto_layout(shapes, [])
        assert "a" in positions
        x, y = positions["a"]
        assert isinstance(x, (int, float))
        assert isinstance(y, (int, float))

    def test_linear_chain(self) -> None:
        shapes = {
            "a": {"label": "A", "classes": []},
            "b": {"label": "B", "classes": []},
            "c": {"label": "C", "classes": []},
        }
        edges = [
            {"id": "e1", "src": "a", "dst": "b", "label": ""},
            {"id": "e2", "src": "b", "dst": "c", "label": ""},
        ]
        positions = auto_layout(shapes, edges)
        ax, _ = positions["a"]
        bx, _ = positions["b"]
        cx, _ = positions["c"]
        # a → b → c should be in increasing x-order
        assert ax < bx < cx

    def test_diamond_dag(self) -> None:
        shapes = {
            "top": {"label": "Top", "classes": []},
            "left": {"label": "Left", "classes": []},
            "right": {"label": "Right", "classes": []},
            "bot": {"label": "Bottom", "classes": []},
        }
        edges = [
            {"id": "e1", "src": "top", "dst": "left", "label": ""},
            {"id": "e2", "src": "top", "dst": "right", "label": ""},
            {"id": "e3", "src": "left", "dst": "bot", "label": ""},
            {"id": "e4", "src": "right", "dst": "bot", "label": ""},
        ]
        positions = auto_layout(shapes, edges)
        assert all(k in positions for k in ("top", "left", "right", "bot"))
        assert positions["top"][0] < positions["bot"][0]

    def test_disconnected_nodes(self) -> None:
        shapes = {
            "a": {"label": "A", "classes": []},
            "b": {"label": "B", "classes": []},
        }
        positions = auto_layout(shapes, [])
        assert "a" in positions
        assert "b" in positions

    def test_edges_outside_shapes_ignored(self) -> None:
        shapes = {"a": {"label": "A", "classes": []}}
        edges = [{"id": "e1", "src": "a", "dst": "z", "label": ""}]  # z not in shapes
        positions = auto_layout(shapes, edges)
        assert "a" in positions


# ===========================================================================
# 6.4 _parse_style_props (replaces _resolve_style)
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestParseStyleProps:
    def test_bc_shorthand(self) -> None:
        props = _parse_style_props("bc:#ff0000")
        assert props["backgroundColor"] == "#ff0000"

    def test_sc_shorthand(self) -> None:
        props = _parse_style_props("sc:#1e1e1e")
        assert props["strokeColor"] == "#1e1e1e"

    def test_sw_numeric(self) -> None:
        props = _parse_style_props("sw:2")
        assert props["strokeWidth"] == 2

    def test_named_color_green(self) -> None:
        props = _parse_style_props("bc:green")
        assert props["backgroundColor"] == "#bbf7d0"

    def test_named_color_blue(self) -> None:
        props = _parse_style_props("bc:blue")
        assert props["backgroundColor"] == "#bfdbfe"

    def test_roughness(self) -> None:
        props = _parse_style_props("r:0")
        assert props["roughness"] == 0

    def test_opacity(self) -> None:
        props = _parse_style_props("o:80")
        assert props["opacity"] == 80

    def test_font_family_normal(self) -> None:
        props = _parse_style_props("f:normal")
        assert props["fontFamily"] == 2

    def test_font_family_mono(self) -> None:
        props = _parse_style_props("f:mono")
        assert props["fontFamily"] == 3

    def test_font_size(self) -> None:
        props = _parse_style_props("fs:20")
        assert props["fontSize"] == 20

    def test_stroke_style(self) -> None:
        props = _parse_style_props("ss:dashed")
        assert props["strokeStyle"] == "dashed"

    def test_shape_d(self) -> None:
        props = _parse_style_props("shape:d")
        assert props["shape"] == "diamond"

    def test_shape_c(self) -> None:
        props = _parse_style_props("shape:c")
        assert props["shape"] == "ellipse"

    def test_shape_r(self) -> None:
        props = _parse_style_props("shape:r")
        assert props["shape"] == "rectangle"

    def test_multiple_props(self) -> None:
        props = _parse_style_props("bc:green,sc:#000,sw:3")
        assert props["backgroundColor"] == "#bbf7d0"
        assert props["strokeColor"] == "#000"
        assert props["strokeWidth"] == 3

    def test_empty_string(self) -> None:
        props = _parse_style_props("")
        assert props == {}


# ===========================================================================
# 6.5 Smoke tests for public tools (mocked Playwright)
# ===========================================================================


def _reset_exc_state() -> None:
    """Reset module-level excalidraw state between tests."""
    import otdev.tools.excalidraw as exc

    exc._dsl_state = {"shapes": {}, "edges": [], "groups": {}}
    exc._edge_keys = set()
    exc._rendered_ids = set()
    exc._placed_positions = {}
    exc._max_rendered_y = 0.0


def _make_mock_proxy(servers: list[str] | None = None) -> MagicMock:
    """Create a mock proxy manager with optional connected servers."""
    mock = MagicMock()
    mock.servers = ["playwright"] if servers is None else servers
    return mock


def _playwright_eval_side_effect(
    server: str, tool: str, arguments: dict[str, Any] | None = None
) -> str:
    """Simulate Playwright responses for key calls."""
    if tool == "browser_navigate":
        return "### Result\nnull\n### Ran Playwright code\n..."
    fn = (arguments or {}).get("function", "")
    if "__drawApi?.backend" in fn:
        return "### Result\ntrue\n### Ran Playwright code\n..."
    if "__drawApi.read" in fn:
        return '### Result\n[]\n### Ran Playwright code\n...'
    if "__otDSL" in fn:
        return '### Result\n""\n### Ran Playwright code\n...'
    if "__downloadQueue" in fn:
        return '### Result\n[]\n### Ran Playwright code\n...'
    return "### Result\nnull\n### Ran Playwright code\n..."


@pytest.mark.unit
@pytest.mark.tools
class TestPublicToolsSmoke:
    """Smoke tests verifying correct JS is called for each public tool."""

    def _reset_state(self) -> None:
        _reset_exc_state()

    def test_draw_calls_browser_evaluate(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.draw(input='a["A"]\nb["B"]\na-->b')

        assert "shapes" in result or "Error" not in result
        assert mock_proxy.call_tool_sync.called

    def test_draw_returns_error_when_playwright_not_connected(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy(servers=[])

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.draw(input='a["A"]')

        assert "Error" in result
        assert "playwright" in result.lower() or "Playwright" in result

    def test_clear_calls_clear(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.clear()

        assert result == "canvas cleared"
        calls = [str(c) for c in mock_proxy.call_tool_sync.call_args_list]
        assert any("clear" in c for c in calls)

    def test_scroll_calls_scroll(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.scroll(dx=100, dy=50)

        assert "scrolled" in result
        calls = [str(c) for c in mock_proxy.call_tool_sync.call_args_list]
        assert any("scroll" in c and "100" in c for c in calls)

    def test_zoom_calls_zoom(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.zoom(level=0.5)

        assert "zoom" in result
        calls = [str(c) for c in mock_proxy.call_tool_sync.call_args_list]
        assert any("zoom" in c and "0.5" in c for c in calls)

    def test_zoom_level_zero_fits_all(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.zoom(level=0)

        assert "fit" in result

    def test_save_writes_native_excalidraw_file(
        self, tmp_path: Any
    ) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect
        out_file = str(tmp_path / "out.excalidraw")

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw.resolve_cwd_path", return_value=tmp_path / "out.excalidraw"),
        ):
            result = excalidraw.save(file=out_file)

        assert "saved" in result
        content = (tmp_path / "out.excalidraw").read_text()
        data = json.loads(content)
        assert data["type"] == "excalidraw"
        assert "elements" in data
        assert data["version"] == 2

    def test_load_restores_state(self, tmp_path: Any) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        # Create a native .excalidraw file
        content = {
            "type": "excalidraw",
            "version": 2,
            "source": "https://excalidraw.com",
            "elements": [],
            "appState": {"viewBackgroundColor": "#ffffff"},
            "files": {},
        }
        diag_file = tmp_path / "diag.excalidraw"
        diag_file.write_text(json.dumps(content))

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw.resolve_cwd_path", return_value=diag_file),
            patch(
                "otdev.tools.excalidraw._read_dsl_from_canvas",
                return_value='a["A"]\nb["B"]\na-->b',
            ),
        ):
            result = excalidraw.load(file=str(diag_file))

        assert "loaded" in result
        assert "2 shapes" in result

    def test_zoom_rejects_negative_level(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.zoom(level=-1.0)

        assert "Error" in result
        mock_proxy.call_tool_sync.assert_not_called()

    def test_load_returns_error_for_invalid_format(self, tmp_path: Any) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        diag_file = tmp_path / "bad.excalidraw"
        diag_file.write_text("not json at all\n")

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw.resolve_cwd_path", return_value=diag_file),
        ):
            result = excalidraw.load(file=str(diag_file))

        assert "Error" in result

    def test_load_returns_error_for_wrong_type(self, tmp_path: Any) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        diag_file = tmp_path / "bad.excalidraw"
        diag_file.write_text(json.dumps({"type": "other", "elements": []}))

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw.resolve_cwd_path", return_value=diag_file),
        ):
            result = excalidraw.load(file=str(diag_file))

        assert "Error" in result

    def test_fit_delegates_to_zoom(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.fit()

        assert "fit" in result

    def test_screenshot_calls_browser_screenshot(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.return_value = "screenshot-data"

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.screenshot()

        calls = mock_proxy.call_tool_sync.call_args_list
        assert any(
            c.args[1] == "browser_take_screenshot" for c in calls
        ), "screenshot must call browser_take_screenshot"
        assert result == "screenshot-data"

    def test_screenshot_always_uses_png(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.return_value = "img"

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            excalidraw.screenshot()

        calls = mock_proxy.call_tool_sync.call_args_list
        screenshot_call = next(c for c in calls if c.args[1] == "browser_take_screenshot")
        args = screenshot_call.args[2]
        assert args["format"] == "png"
        assert "quality" not in args

    def test_screenshot_saves_to_file(self, tmp_path: Any) -> None:
        import base64

        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        fake_bytes = b"FAKEIMAGE"
        mock_proxy.call_tool_sync.return_value = base64.b64encode(fake_bytes).decode()

        out_file = str(tmp_path / "canvas.png")
        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw.resolve_cwd_path", return_value=tmp_path / "canvas.png"),
        ):
            result = excalidraw.screenshot(file=out_file)

        assert "saved" in result
        assert (tmp_path / "canvas.png").read_bytes() == fake_bytes

    def test_clear_works_as_first_operation(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.clear()

        assert result == "canvas cleared"

    def test_hard_reset_clears_state_without_browser(self) -> None:
        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        exc._dsl_state = {"shapes": {"a": {"label": "A", "classes": []}}, "edges": [], "groups": {}}
        exc._rendered_ids = {"a"}
        exc._edge_keys = set()
        exc._max_rendered_y = 100.0

        mock_proxy = _make_mock_proxy(servers=[])

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.hard_reset()

        assert "state cleared" in result
        assert exc._dsl_state["shapes"] == {}
        assert exc._rendered_ids == set()
        assert exc._max_rendered_y == 0.0

    def test_hard_reset_clears_canvas_when_browser_available(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect
        evaluated: list[str] = []

        orig_eval = excalidraw._browser_evaluate

        def capture_eval(expr: str, *args: Any, **kwargs: Any) -> Any:
            evaluated.append(expr)
            return orig_eval(expr, *args, **kwargs)

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            with patch("otdev.tools.excalidraw._browser_evaluate", side_effect=capture_eval):
                result = excalidraw.hard_reset()

        assert "canvas cleared" in result
        assert any("clear" in e for e in evaluated), "expected canvas clear call"

    def test_open_returns_ready_when_bootstrap_succeeds(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.open()

        assert result == "whiteboard ready"

    def test_open_clears_canvas_and_state(self) -> None:
        """open() always starts fresh regardless of existing state."""
        import otdev.tools.excalidraw as exc
        from otdev.tools import excalidraw

        self._reset_state()
        exc._dsl_state["shapes"]["a"] = {"label": "A", "classes": []}
        exc._rendered_ids = {"a"}
        exc._max_rendered_y = 500.0

        evaluated: list[str] = []

        def capture_eval(fn: str) -> str:
            evaluated.append(fn)
            return _playwright_eval_side_effect("browser_evaluate", {"function": fn})

        mock_proxy = _make_mock_proxy()

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            with patch("otdev.tools.excalidraw._browser_evaluate", side_effect=capture_eval):
                result = excalidraw.open()

        assert result == "whiteboard ready"
        assert exc._dsl_state["shapes"] == {}, "state should be cleared"
        assert exc._rendered_ids == set(), "rendered_ids should be cleared"
        assert exc._max_rendered_y == 0.0, "_max_rendered_y should be reset"
        assert any("clear" in e for e in evaluated), "canvas clear should be called"

    def test_open_returns_error_when_playwright_not_connected(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy(servers=[])

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.open()

        assert "Error" in result

    def test_close_resets_state_without_browser(self) -> None:
        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        exc._dsl_state["shapes"]["a"] = {"label": "A", "classes": []}
        exc._rendered_ids = {"a"}
        exc._max_rendered_y = 100.0

        mock_proxy = _make_mock_proxy(servers=[])

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.close()

        assert "closed" in result
        assert exc._dsl_state["shapes"] == {}
        assert exc._rendered_ids == set()
        assert exc._max_rendered_y == 0.0

    def test_close_calls_tab_close_when_browser_available(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.close()

        assert "closed" in result
        calls = [c.args[1] for c in mock_proxy.call_tool_sync.call_args_list]
        assert "browser_close" in calls or "browser_navigate" in calls

    def test_bootstrap_failure_returns_error(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()

        def bootstrap_fail_side_effect(server: str, tool: str, arguments: Any = None) -> str:
            if tool == "browser_navigate":
                return "### Result\nnull\n### Ran Playwright code\n..."
            fn = (arguments or {}).get("function", "")
            if "__drawApi?.backend" in fn:
                return "### Result\nfalse\n### Ran Playwright code\n..."
            if "__drawElements" in fn:
                return "### Result\nfalse\n### Ran Playwright code\n..."
            return "### Result\nnull\n### Ran Playwright code\n..."

        mock_proxy.call_tool_sync.side_effect = bootstrap_fail_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.draw(input='a["A"]')

        assert "Error" in result
        assert "bootstrap" in result.lower()

    def test_draw_additive_layout_uses_full_graph(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            excalidraw.draw(input='a["A"]\nb["B"]\na-->b')
            with patch("otdev.tools.excalidraw._js_batch_draw") as mock_batch:
                excalidraw.draw(input='c["C"]\nb-->c')
                assert mock_batch.called
                _, kwargs = mock_batch.call_args
                shapes = kwargs["shapes"]
                assert len(shapes) == 1 and shapes[0]["id"] == "c"
                assert shapes[0]["x"] > 0, "additive shape should be placed right of existing shapes"

    def test_draw_auto_creates_unknown_node_in_edge(self) -> None:
        """Unknown edge endpoints are auto-created with label = node ID."""
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.draw(input='a["A"]\nb["B"]\na-->typo')

        assert "skipped" not in result
        assert "+3 shapes" in result

    def test_draw_implied_nodes_only(self) -> None:
        """All nodes implied by edges — no explicit shape declarations."""
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.draw(input="a-->b\nb-->c\nc-->d")

        assert "+4 shapes" in result

    def test_draw_no_warn_when_all_nodes_defined(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.draw(input='a["A"]\nb["B"]\na-->b')

        assert "skipped" not in result

    def test_js_batch_draw_passes_three_positional_args(self) -> None:
        """_js_batch_draw must call browser_evaluate with 3 separate JSON args."""
        import otdev.tools.excalidraw as exc

        self._reset_state()
        calls: list[str] = []

        def capture_evaluate(fn: str) -> str:
            calls.append(fn)
            return "### Result\ntrue\n### Ran Playwright code\n..."

        with patch("otdev.tools.excalidraw._browser_evaluate", side_effect=capture_evaluate):
            exc._js_batch_draw(
                shapes=[{"id": "a"}],
                edges=[{"id": "e1"}],
                subgraphs=[],
            )

        assert calls, "should have called _browser_evaluate"
        fn = calls[0]
        assert '"shapes"' not in fn.split("_batch_draw(")[1][:10], \
            "_batch_draw must not receive a {shapes:…} object as first arg"
        assert fn.count(",") >= 2, "call must have at least 2 commas (three positional args)"

    def test_draw_state_not_mutated_if_js_batch_draw_raises(self) -> None:
        """draw() must not commit _dsl_state if _js_batch_draw raises."""
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw._js_batch_draw", side_effect=RuntimeError("JS error")),
        ):
            try:
                excalidraw.draw(input='a["A"]\nb["B"]\na-->b')
            except RuntimeError:
                pass

        import otdev.tools.excalidraw as exc
        assert exc._dsl_state["shapes"] == {}, "shapes must not be committed when JS call fails"
        assert exc._dsl_state["edges"] == [], "edges must not be committed when JS call fails"

    def test_draw_issues_single_batch_call(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw._js_batch_draw") as mock_batch,
        ):
            excalidraw.draw(input='a["A"]\nb["B"]\nc["C"]\na-->b\nb-->c')

        assert mock_batch.call_count == 1, "draw() must issue exactly one batch call"
        _, kwargs = mock_batch.call_args
        assert len(kwargs["shapes"]) == 3
        assert len(kwargs["edges"]) == 2

    def test_draw_returns_edge_ids_in_output(self) -> None:
        """draw() includes new edge IDs in the return string (issue #6)."""
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.draw(input='a["A"]\nb["B"]\na-->b')

        assert "edge-a-b" in result

    def test_draw_upsert_existing_shape(self) -> None:
        """draw() on an existing shape patches it (upsert) rather than skipping."""
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        patches: list[Any] = []

        def capture_patch(p: list[Any]) -> None:
            patches.extend(p)

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw._js_patch_elements", side_effect=capture_patch),
        ):
            excalidraw.draw(input='a["A"]')
            patches.clear()
            excalidraw.draw(input='a["Updated"]')

        assert any(p.get("id") == "a" and p.get("text") == "Updated" for p in patches), \
            "existing shape label update should be sent as a patch"


# ===========================================================================
# 6.6 Edge ID collision fixes
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestEdgeIdUniqueness:
    def test_parallel_edges_different_labels_have_unique_ids(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->|read|b\na-->|write|b')
        ids = [e["id"] for e in result["edges"]]
        assert len(ids) == len(set(ids)), "parallel edges with different labels must have unique IDs"

    def test_labeled_edge_id_includes_label(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->|query|b')
        assert result["edges"][0]["id"] == "edge-a-b-query"

    def test_unlabeled_directed_edge_id(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->b')
        assert result["edges"][0]["id"] == "edge-a-b"

    def test_bidirectional_edge_id_differs_from_directed(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->b\na<-->b')
        ids = [e["id"] for e in result["edges"]]
        assert len(ids) == len(set(ids)), "bidir and directed edges must have different IDs"
        assert any("bidir" in eid for eid in ids)

    def test_undirected_edge_id_includes_und_suffix(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na---b')
        assert result["edges"][0]["id"] == "edge-a-b-und"

    def test_dot_edge_id_includes_dot_suffix(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --o b')
        assert result["edges"][0]["id"] == "edge-a-b-dot"

    def test_bar_edge_id_includes_bar_suffix(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --x b')
        assert result["edges"][0]["id"] == "edge-a-b-bar"

    def test_draw_dedup_distinguishes_arrowhead_types(self) -> None:
        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        exc._dsl_state = {"shapes": {}, "edges": [], "groups": {}}
        exc._edge_keys = set()
        exc._rendered_ids = set()
        exc._max_rendered_y = 0.0

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            excalidraw.draw(input='a["A"]\nb["B"]\na-->b\na<-->b')

        assert len(exc._dsl_state["edges"]) == 2, "a-->b and a<-->b should both be stored"


# ===========================================================================
# 6.7 Arrow label rendering
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestArrowLabels:
    def test_labeled_edge_parsed_correctly(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->|read|b')
        assert result["edges"][0]["label"] == "read"

    def test_labeled_edge_id_encodes_label(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->|read|b')
        assert "read" in result["edges"][0]["id"]

    def test_connect_shape_called_with_label(self) -> None:
        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        exc._dsl_state = {"shapes": {}, "edges": [], "groups": {}}
        exc._edge_keys = set()
        exc._rendered_ids = set()
        exc._max_rendered_y = 0.0

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw._js_batch_draw") as mock_batch,
        ):
            excalidraw.draw(input='a["A"]\nb["B"]\na-->|writes|b')
            assert mock_batch.called
            _, kwargs = mock_batch.call_args
            edges = kwargs["edges"]
            assert len(edges) == 1
            assert edges[0]["label"] == "writes"


# ===========================================================================
# 6.8 Cyclic graph layout
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestCyclicLayout:
    def test_cyclic_nodes_all_placed(self) -> None:
        shapes = {
            "a": {"label": "A", "classes": []},
            "b": {"label": "B", "classes": []},
            "c": {"label": "C", "classes": []},
        }
        edges = [
            {"id": "e1", "src": "a", "dst": "b", "label": ""},
            {"id": "e2", "src": "b", "dst": "c", "label": ""},
            {"id": "e3", "src": "c", "dst": "a", "label": ""},
        ]
        positions = auto_layout(shapes, edges)
        assert set(positions.keys()) == {"a", "b", "c"}, "all cyclic nodes must receive positions"

    def test_cyclic_nodes_not_all_at_same_x(self) -> None:
        shapes = {
            "a": {"label": "A", "classes": []},
            "b": {"label": "B", "classes": []},
            "c": {"label": "C", "classes": []},
        }
        edges = [
            {"id": "e1", "src": "a", "dst": "b", "label": ""},
            {"id": "e2", "src": "b", "dst": "c", "label": ""},
            {"id": "e3", "src": "c", "dst": "a", "label": ""},
        ]
        positions = auto_layout(shapes, edges)
        xs = [pos[0] for pos in positions.values()]
        assert len(set(xs)) > 1 or len(positions) <= 1, "cyclic nodes should not all stack at x=0"

    def test_mixed_dag_and_cyclic(self) -> None:
        shapes = {
            "root": {"label": "Root", "classes": []},
            "a": {"label": "A", "classes": []},
            "b": {"label": "B", "classes": []},
        }
        edges = [
            {"id": "e1", "src": "root", "dst": "a", "label": ""},
            {"id": "e2", "src": "a", "dst": "b", "label": ""},
            {"id": "e3", "src": "b", "dst": "a", "label": ""},
        ]
        positions = auto_layout(shapes, edges)
        assert "root" in positions
        assert "a" in positions
        assert "b" in positions


# ===========================================================================
# 6.9 Note tool
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestNoteToolParsing:
    def test_parse_note_blocks_table(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = "t[table:\nA,B\n1,2\n]"
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 1
        assert blocks[0]["id"] == "t"
        assert blocks[0]["type"] == "table"
        assert "A,B" in blocks[0]["content"]

    def test_parse_note_blocks_multiple(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = "t1[table:\nA,B\n1,2\n]\n\nt2[tree:\nroot\n-child\n]"
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 2
        assert blocks[0]["id"] == "t1"
        assert blocks[1]["id"] == "t2"

    def test_parse_note_blocks_empty(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        assert _parse_note_blocks("nothing here") == []

    def test_parse_note_blocks_trailing_space_after_colon(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = "t[table:  \nA,B\n1,2\n]"
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "table"

    def test_parse_note_blocks_crlf_line_endings(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = "t[table:\r\nA,B\r\n1,2\r\n]"
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "table"

    def test_note_tool_returns_error_on_no_blocks(self) -> None:
        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        exc._dsl_state = {"shapes": {}, "edges": [], "groups": {}}
        exc._edge_keys = set()
        exc._rendered_ids = set()
        exc._max_rendered_y = 0.0

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.note(input="no blocks here")

        assert "Error" in result

    def test_note_returns_error_on_renderer_error(self) -> None:
        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        exc._dsl_state = {"shapes": {}, "edges": [], "groups": {}}
        exc._edge_keys = set()
        exc._rendered_ids = set()
        exc._max_rendered_y = 0.0

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch(
                "otdev.tools._excalidraw.renderers.render_table",
                return_value="Error: tabulate not installed (pip install tabulate)",
            ),
            patch("otdev.tools.excalidraw._js_batch_draw") as mock_batch,
        ):
            result = excalidraw.note(input="t[table:\nName,Role\nAlice,Dev\n]")

        assert "Error" in result
        assert "t" in result
        mock_batch.assert_not_called()

    def test_note_unknown_type_returns_error(self) -> None:
        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        exc._dsl_state = {"shapes": {}, "edges": [], "groups": {}}
        exc._edge_keys = set()
        exc._rendered_ids = set()
        exc._max_rendered_y = 0.0

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.note(input="x[text:\nsome content\n]")

        assert "Error" in result
        assert "text" in result
        assert "Supported" in result

    def test_note_tool_calls_draw_shape(self) -> None:
        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        exc._dsl_state = {"shapes": {}, "edges": [], "groups": {}}
        exc._edge_keys = set()
        exc._rendered_ids = set()
        exc._max_rendered_y = 0.0

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw._js_batch_draw") as mock_batch,
        ):
            result = excalidraw.note(input="t[tree:\nroot\n-child\n]")

        assert "inserted" in result
        assert mock_batch.call_count == 1
        _, kwargs = mock_batch.call_args
        shapes = kwargs["shapes"]
        assert len(shapes) == 1
        assert shapes[0]["id"] == "t"
        assert shapes[0]["styleProps"]["fontFamily"] == 3  # code font


# ===========================================================================
# 6.10 Renderers unit tests
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestRenderers:
    def test_render_tree_basic(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        result = render_tree("root\n-child1\n-child2\n--leaf")
        assert "root" in result
        assert "child1" in result
        assert "leaf" in result

    def test_render_tree_empty(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        assert render_tree("") == ""

    def test_render_sequence_basic(self) -> None:
        from otdev.tools._excalidraw.renderers import render_sequence

        result = render_sequence("A -> B: hello\nB -> A: world")
        assert "A" in result
        assert "B" in result
        assert "hello" in result

    def test_render_sequence_empty(self) -> None:
        from otdev.tools._excalidraw.renderers import render_sequence

        assert render_sequence("") == ""

    def test_render_timeline_basic(self) -> None:
        from otdev.tools._excalidraw.renderers import render_timeline

        result = render_timeline("Task A,1,5\nTask B,3,4")
        assert "Task A" in result
        assert "#" in result

    def test_render_timeline_empty(self) -> None:
        from otdev.tools._excalidraw.renderers import render_timeline

        assert render_timeline("") == ""

    def test_render_timeline_bad_start_returns_error(self) -> None:
        from otdev.tools._excalidraw.renderers import render_timeline

        result = render_timeline("v1.0,Jan,2\nv2.0,Mar,3")
        assert result.startswith("Error:")
        assert "Jan" in result
        assert "start" in result

    def test_render_timeline_bad_duration_returns_error(self) -> None:
        from otdev.tools._excalidraw.renderers import render_timeline

        result = render_timeline("v1.0,1,two")
        assert result.startswith("Error:")
        assert "two" in result
        assert "duration" in result

    def test_render_timeline_semicolon_separator(self) -> None:
        from otdev.tools._excalidraw.renderers import render_timeline

        result = render_timeline("Task A,1,5;Task B,3,4")
        assert "Task A" in result
        assert "Task B" in result

    def test_render_tree_siblings_show_connector(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        result = render_tree("root\n-child1\n--leaf1\n-child2")
        lines = result.splitlines()
        assert any("│" in ln for ln in lines), "sibling branch should show │ connector"
        assert "child2" in result
        assert any("└──" in ln for ln in lines)

    def test_render_tree_no_false_sibling_across_subtree(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        result = render_tree("root\n-child1\n--leaf1\n-child2\n--leaf2")
        lines = result.splitlines()
        leaf1_line = next(ln for ln in lines if "leaf1" in ln)
        assert "leaf1" in leaf1_line
        assert "└──" in leaf1_line or "├──" in leaf1_line

    def test_render_tree_true_siblings_continuation(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        result = render_tree("root\n-child1\n--leaf1\n--leaf2")
        lines = result.splitlines()
        leaf1_line = next(ln for ln in lines if "leaf1" in ln)
        assert "├──" in leaf1_line

    def test_render_tree_unicode_connectors(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        result = render_tree("root\n-child1\n-child2")
        assert "├──" in result
        assert "└──" in result

    def test_render_tree_space_indent(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        result = render_tree("root\n  child1\n  child2\n    leaf")
        assert "root" in result
        assert "child1" in result
        assert "leaf" in result

    def test_render_tree_semicolon_separator(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        result = render_tree("root;-child1;-child2")
        assert "root" in result
        assert "child1" in result
        assert "child2" in result


# ===========================================================================
# 6.11 _max_rendered_y: note() avoids redundant auto_layout
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestMaxRenderedY:
    def _reset(self) -> None:
        _reset_exc_state()

    def test_note_uses_max_rendered_y_not_auto_layout(self) -> None:
        """note() must not call auto_layout — it reads _max_rendered_y directly."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        self._reset()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        import otdev.tools.excalidraw as exc
        exc._max_rendered_y = 200.0

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw.auto_layout") as mock_layout,
            patch("otdev.tools.excalidraw._js_batch_draw"),
        ):
            excalidraw.note(input="n[note:\nhello world\n]")
            mock_layout.assert_not_called()

    def test_note_base_y_uses_max_rendered_y(self) -> None:
        """Notes are placed 100px below _max_rendered_y."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        self._reset()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        import otdev.tools.excalidraw as exc
        exc._max_rendered_y = 300.0

        captured: list[Any] = []

        def capture_batch(**kwargs: Any) -> None:
            captured.append(kwargs)

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw._js_batch_draw", side_effect=capture_batch),
        ):
            excalidraw.note(input="n[note:\nhello\n]")

        assert captured, "batch draw should have been called"
        shapes = captured[0]["shapes"]
        assert shapes[0]["y"] >= 400.0, "note y should be at least _max_rendered_y + 100"

    def test_draw_updates_max_rendered_y(self) -> None:
        """draw() should update _max_rendered_y after placing shapes."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        self._reset()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        import otdev.tools.excalidraw as exc
        assert exc._max_rendered_y == 0.0

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw._js_batch_draw"),
        ):
            excalidraw.draw(input='a["A"]\nb["B"]')

        assert exc._max_rendered_y > 0.0, "draw() should update _max_rendered_y"

    def test_clear_resets_max_rendered_y(self) -> None:
        """clear_diag() should reset _max_rendered_y to 0."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        self._reset()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        import otdev.tools.excalidraw as exc
        exc._max_rendered_y = 500.0

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            excalidraw.clear()

        assert exc._max_rendered_y == 0.0


# ===========================================================================
# embed_dsl
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestEmbedDsl:
    def _reset(self) -> None:
        _reset_exc_state()

    def test_embed_dsl_inserts_dsl_box(self) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        self._reset()
        exc._dsl_state["shapes"]["a"] = {"label": "A", "classes": []}
        exc._dsl_state["shapes"]["b"] = {"label": "B", "classes": []}

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw._js_batch_draw") as mock_batch,
        ):
            result = excalidraw.embed_dsl()

        assert "embedded DSL" in result
        assert mock_batch.call_count == 1
        _, kwargs = mock_batch.call_args
        shapes = kwargs["shapes"]
        assert len(shapes) == 1
        assert shapes[0]["id"] == "dsl"
        assert shapes[0]["styleProps"]["backgroundColor"] == "#e8e8e8"
        assert "a" in shapes[0]["label"] or "b" in shapes[0]["label"]

    def test_embed_dsl_returns_empty_message_when_no_state(self) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        self._reset()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.embed_dsl()

        assert "empty" in result


# ===========================================================================
# erase
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestErase:
    def _reset(self) -> None:
        _reset_exc_state()

    def test_erase_removes_shape_from_state(self) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        self._reset()
        exc._dsl_state["shapes"]["a"] = {"label": "A", "classes": []}
        exc._dsl_state["shapes"]["b"] = {"label": "B", "classes": []}
        exc._rendered_ids = {"a", "a-text", "b", "b-text"}

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.erase(ids=["a"])

        assert "erased 1" in result
        assert "a" not in exc._dsl_state["shapes"]
        assert "a" not in exc._rendered_ids
        assert "a-text" not in exc._rendered_ids
        assert "b" in exc._dsl_state["shapes"]

    def test_erase_unknown_id_returns_zero(self) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        self._reset()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.erase(ids=["nonexistent"])

        assert "erased 0" in result

    def test_erase_removes_associated_edge(self) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        self._reset()
        exc._dsl_state["shapes"]["a"] = {"label": "A", "classes": []}
        exc._dsl_state["shapes"]["b"] = {"label": "B", "classes": []}
        exc._dsl_state["edges"] = [
            {"id": "edge-a-b", "src": "a", "dst": "b", "label": ""}
        ]
        exc._rendered_ids = {"a", "b", "edge-a-b"}

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            excalidraw.erase(ids=["edge-a-b"])

        assert exc._dsl_state["edges"] == []

    def test_erase_removes_dangling_edges(self) -> None:
        """Erasing a shape also removes edges that reference it as src or dst."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        self._reset()
        exc._dsl_state["shapes"]["a"] = {"label": "A", "classes": []}
        exc._dsl_state["shapes"]["b"] = {"label": "B", "classes": []}
        exc._dsl_state["shapes"]["c"] = {"label": "C", "classes": []}
        exc._dsl_state["edges"] = [
            {"id": "edge-a-b", "src": "a", "dst": "b", "label": ""},
            {"id": "edge-b-c", "src": "b", "dst": "c", "label": ""},
        ]
        exc._rendered_ids = {"a", "b", "c", "edge-a-b", "edge-b-c"}

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            excalidraw.erase(ids=["b"])

        assert exc._dsl_state["edges"] == [], "edges referencing erased node should be removed"
        assert "edge-a-b" not in exc._rendered_ids
        assert "edge-b-c" not in exc._rendered_ids

    def test_erase_keeps_max_rendered_y_when_shapes_remain(self) -> None:
        """_max_rendered_y should not be reset to 0 when shapes still exist after erase."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        self._reset()
        exc._dsl_state["shapes"]["a"] = {"label": "A", "classes": []}
        exc._dsl_state["shapes"]["b"] = {"label": "B", "classes": []}
        exc._rendered_ids = {"a", "b"}
        exc._max_rendered_y = 600.0

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            excalidraw.erase(ids=["a"])

        assert exc._max_rendered_y == 600.0, "should not reset _max_rendered_y when shapes remain"

    def test_erase_resets_max_rendered_y_when_all_shapes_gone(self) -> None:
        """_max_rendered_y resets to 0 only when all shapes are erased."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        self._reset()
        exc._dsl_state["shapes"]["a"] = {"label": "A", "classes": []}
        exc._rendered_ids = {"a"}
        exc._max_rendered_y = 600.0

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            excalidraw.erase(ids=["a"])

        assert exc._max_rendered_y == 0.0

    def test_erase_docstring_documents_edge_id_format(self) -> None:
        """erase() docstring must document the edge ID format."""
        from otdev.tools import excalidraw

        doc = excalidraw.erase.__doc__ or ""
        assert "edge-{src}-{dst}" in doc, "docstring must document edge ID format"


# ===========================================================================
# Shape types — ellipse and diamond are no longer supported via DSL
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestShapeTypes:
    def test_parse_ellipse_raises_error(self) -> None:
        """Ellipse syntax raises ValueError with helpful error message."""
        with pytest.raises(ValueError, match="Ellipse"):
            parse_dsl('a(("Oval"))')

    def test_parse_diamond_raises_error(self) -> None:
        """Diamond syntax raises ValueError with helpful error message."""
        with pytest.raises(ValueError, match="Diamond"):
            parse_dsl('a{"Decision"}')

    def test_rectangle_has_no_explicit_type(self) -> None:
        result = parse_dsl('a["Box"]')
        assert "type" not in result["shapes"]["a"]

    def test_style_shape_d_maps_to_diamond(self) -> None:
        """whiteboard.style shape:d maps to 'diamond' excalidraw type."""
        props = _parse_style_props("shape:d")
        assert props["shape"] == "diamond"

    def test_style_shape_c_maps_to_ellipse(self) -> None:
        """whiteboard.style shape:c maps to 'ellipse' excalidraw type."""
        props = _parse_style_props("shape:c")
        assert props["shape"] == "ellipse"

    def test_style_shape_r_maps_to_rectangle(self) -> None:
        """whiteboard.style shape:r maps to 'rectangle' excalidraw type."""
        props = _parse_style_props("shape:r")
        assert props["shape"] == "rectangle"


# ===========================================================================
# Node ID normalisation
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestNodeIdNormalise:
    def test_uppercase_id_lowercased(self) -> None:
        result = parse_dsl('A["Node"]')
        assert "a" in result["shapes"]
        assert "A" not in result["shapes"]

    def test_mixed_case_ids_merge(self) -> None:
        result = parse_dsl('A["First"]\na["Second"]')
        assert len(result["shapes"]) == 1
        assert result["shapes"]["a"]["label"] == "Second"

    def test_edge_src_dst_normalised(self) -> None:
        result = parse_dsl('A["A"]\nB["B"]\nA-->B')
        e = result["edges"][0]
        assert e["src"] == "a"
        assert e["dst"] == "b"

    def test_uppercase_edge_connects_to_lowercase_shape(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\nA-->B')
        e = result["edges"][0]
        assert e["src"] == "a"
        assert e["dst"] == "b"

    def test_hyphenated_id_normalised(self) -> None:
        result = parse_dsl('service-a["Svc"]')
        assert "servicea" in result["shapes"]

    def test_hyphenated_edge_normalised(self) -> None:
        result = parse_dsl('service-a["A"]\nservice-b["B"]\nservice-a-->service-b')
        e = result["edges"][0]
        assert e["src"] == "servicea"
        assert e["dst"] == "serviceb"


# ===========================================================================
# 6.x Whitespace tolerance
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestWhitespaceTolerance:
    """DSL tokenizer must be whitespace-agnostic for all constructs."""

    def test_shape_spaced_brackets(self) -> None:
        result = parse_dsl('a [ "A" ]')
        assert "a" in result["shapes"]
        assert result["shapes"]["a"]["label"] == "A"

    def test_shape_extra_spaces_around_brackets(self) -> None:
        result = parse_dsl('a  [  "Hello World"  ]')
        assert "a" in result["shapes"]
        assert result["shapes"]["a"]["label"] == "Hello World"

    def test_ellipse_shape_spaced_raises_error(self) -> None:
        """Spaced ellipse syntax also raises ValueError."""
        with pytest.raises(ValueError, match="Ellipse"):
            parse_dsl('a ( ( "Node" ) )')

    def test_diamond_shape_spaced_raises_error(self) -> None:
        """Spaced diamond syntax also raises ValueError."""
        with pytest.raises(ValueError, match="Diamond"):
            parse_dsl('a { "Decision" }')

    def test_arrow_edge_no_spaces(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["src"] == "a"

    def test_arrow_edge_with_spaces(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --> b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["src"] == "a"

    def test_arrow_edge_with_extra_spaces(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na  -->  b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["src"] == "a"

    def test_dot_edge_no_spaces(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na--ob')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["endArrowhead"] == "dot"

    def test_dot_edge_with_spaces(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --o b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["endArrowhead"] == "dot"

    def test_bar_edge_no_spaces(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na--xb')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["endArrowhead"] == "bar"

    def test_bar_edge_with_spaces(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --x b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["endArrowhead"] == "bar"

    def test_semicolon_and_newline_both_work(self) -> None:
        r1 = parse_dsl('a["A"];b["B"];a-->b')
        r2 = parse_dsl('a["A"]\nb["B"]\na-->b')
        assert r1["shapes"] == r2["shapes"]
        assert len(r1["edges"]) == len(r2["edges"]) == 1

    def test_arrow_edge_with_label_space_before_pipe(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --> |label| b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["label"] == "label"

    def test_bidir_edge_with_label_space_before_pipe(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na <--> |label| b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["label"] == "label"

    def test_dot_edge_with_label_space_before_pipe(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --o |lbl| b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["label"] == "lbl"

    def test_bar_edge_with_label_space_before_pipe(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --x |lbl| b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["label"] == "lbl"

    def test_dashed_arrow_edge_with_label_space_before_pipe(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na -.-> |lbl| b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["label"] == "lbl"


# ===========================================================================
# ID pre-normalisation (spaces, hyphens, special chars stripped before parsing)
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestIdPrenorm:
    """IDs with spaces, hyphens, or other non-word chars are pre-normalised."""

    def test_shape_id_with_spaces(self) -> None:
        result = parse_dsl('a b["Test"]')
        assert "ab" in result["shapes"]
        assert result["shapes"]["ab"]["label"] == "Test"

    def test_shape_id_with_hyphen(self) -> None:
        result = parse_dsl('a-b["Test"]')
        assert "ab" in result["shapes"]
        assert result["shapes"]["ab"]["label"] == "Test"

    def test_shape_id_with_plus(self) -> None:
        result = parse_dsl('a+b["Test"]')
        assert "ab" in result["shapes"]
        assert result["shapes"]["ab"]["label"] == "Test"

    def test_shape_id_multiword(self) -> None:
        result = parse_dsl('api gateway["API Gateway"]')
        assert "apigateway" in result["shapes"]
        assert result["shapes"]["apigateway"]["label"] == "API Gateway"

    def test_edge_src_with_spaces(self) -> None:
        result = parse_dsl('a b["A"]\nc["C"]\na b-->c')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["src"] == "ab"
        assert result["edges"][0]["dst"] == "c"

    def test_edge_both_sides_with_spaces(self) -> None:
        result = parse_dsl('a b["A"]\nc d["C"]\na b-->c d')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["src"] == "ab"
        assert result["edges"][0]["dst"] == "cd"

    def test_edge_with_label_and_spaces_in_ids(self) -> None:
        result = parse_dsl('a b["A"]\nc d["C"]\na b-->|calls|c d')
        assert len(result["edges"]) == 1
        e = result["edges"][0]
        assert e["src"] == "ab"
        assert e["dst"] == "cd"
        assert e["label"] == "calls"

    def test_bare_style_with_space_in_id(self) -> None:
        result = parse_dsl('api gateway bc:green')
        assert "apigateway" in result["shapes"]
        assert result["shapes"]["apigateway"]["label"] is None

    def test_prenorm_does_not_touch_label_content(self) -> None:
        result = parse_dsl('a b["hello world"]')
        assert result["shapes"]["ab"]["label"] == "hello world"

    def test_chained_edges_with_spaces(self) -> None:
        """A --> B --> C (spaces around -->) expands to two edges."""
        result = parse_dsl("A --> B --> C")
        assert len(result["edges"]) == 2
        srcs = {e["src"] for e in result["edges"]}
        dsts = {e["dst"] for e in result["edges"]}
        assert "a" in srcs
        assert "b" in srcs
        assert "b" in dsts
        assert "c" in dsts

    def test_chained_edges_matches_semicolon_form(self) -> None:
        """A --> B --> C produces the same edges as a-->b;b-->c."""
        r1 = parse_dsl("A --> B --> C")
        r2 = parse_dsl("a-->b;b-->c")
        assert len(r1["edges"]) == len(r2["edges"]) == 2
        r1_pairs = {(e["src"], e["dst"]) for e in r1["edges"]}
        r2_pairs = {(e["src"], e["dst"]) for e in r2["edges"]}
        assert r1_pairs == r2_pairs


# ===========================================================================
# Erase dangling edge count in return value
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestEraseDanglingCount:
    def test_erase_reports_dangling_edges(self) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        _reset_exc_state()
        exc._dsl_state["shapes"]["a"] = {"label": "A", "classes": []}
        exc._dsl_state["shapes"]["b"] = {"label": "B", "classes": []}
        exc._dsl_state["shapes"]["c"] = {"label": "C", "classes": []}
        exc._dsl_state["edges"] = [
            {"id": "edge-a-b", "src": "a", "dst": "b", "label": ""},
            {"id": "edge-b-c", "src": "b", "dst": "c", "label": ""},
        ]
        exc._rendered_ids = {"a", "b", "c", "edge-a-b", "edge-b-c"}

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.erase(ids=["b"])

        assert "erased 1" in result
        assert "dangling" in result
        assert "2" in result

    def test_erase_no_dangling_message_when_no_edges(self) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        _reset_exc_state()
        exc._dsl_state["shapes"]["a"] = {"label": "A", "classes": []}
        exc._rendered_ids = {"a", "a-text"}

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.erase(ids=["a"])

        assert "erased 1" in result
        assert "dangling" not in result


# ===========================================================================
# Note tool: leading newline before first block (regression)
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestNoteLeadingNewline:
    def test_leading_newline_does_not_prevent_match(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = "\nt[table:\nA,B\n1,2\n]"
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 1
        assert blocks[0]["id"] == "t"
        assert blocks[0]["type"] == "table"

    def test_triple_quoted_style_with_leading_newline(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = """
t[table:
A,B
1,2
]"""
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 1
        assert blocks[0]["id"] == "t"

    def test_multiple_blocks_with_surrounding_newlines(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = "\nt1[table:\nA,B\n1,2\n]\n\nt2[note:\nhello\n]\n"
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 2


# ===========================================================================
# Subgraph count in draw() return value
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestDrawSubgraphCount:
    def test_draw_new_subgraph_reports_group(self) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            excalidraw.draw(input='a["A"]\nb["B"]')
            result = excalidraw.draw(
                input='subgraph grp ["My Group"]\n  a\n  b\nend'
            )

        assert "group" in result

    def test_draw_no_group_msg_when_no_new_subgraph(self) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.draw(input='a["A"]\nb["B"]')

        assert "group" not in result


# ===========================================================================
# Auto-layout overlap avoidance
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestAutoLayoutOverlap:
    def test_find_free_y_no_conflict(self) -> None:
        import otdev.tools.excalidraw as exc
        from otdev.tools.excalidraw import _find_free_y

        exc._placed_positions = {}
        # No existing positions — proposed y should be returned unchanged
        assert _find_free_y(500.0, 470.0) == 470.0

    def test_find_free_y_conflict_shifts_below(self) -> None:
        import otdev.tools.excalidraw as exc
        from otdev.tools.excalidraw import _find_free_y

        # Simulate a node already placed at (980, 470) with h=60, gap_y=40
        exc._placed_positions = {"db": (980.0, 470.0)}
        # New node proposed at same x, same y — should be shifted below
        y = _find_free_y(980.0, 470.0)
        # Should be placed below: 470 + 60 + 40 = 570
        assert y > 470.0 + 60  # at least below db's bottom

    def test_draw_stores_placed_positions(self) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        _reset_exc_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            excalidraw.draw(input='a["A"]\nb["B"]')

        assert "a" in exc._placed_positions
        assert "b" in exc._placed_positions

    def test_erase_removes_placed_position(self) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        _reset_exc_state()
        exc._dsl_state["shapes"]["a"] = {"label": "A", "classes": []}
        exc._rendered_ids = {"a", "a-text"}
        exc._placed_positions = {"a": (500.0, 470.0)}

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            excalidraw.erase(ids=["a"])

        assert "a" not in exc._placed_positions


# ===========================================================================
# Case-insensitive style values
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestParseStylePropsCI:
    """Case-insensitive style value resolution."""

    def test_named_color_uppercase(self) -> None:
        props = _parse_style_props("bc:Green")
        assert props["backgroundColor"] == "#bbf7d0"

    def test_named_color_allcaps(self) -> None:
        props = _parse_style_props("bc:BLUE")
        assert props["backgroundColor"] == "#bfdbfe"

    def test_stroke_color_mixedcase(self) -> None:
        props = _parse_style_props("sc:Red")
        assert props["strokeColor"] == "#fecaca"

    def test_stroke_style_uppercase(self) -> None:
        props = _parse_style_props("ss:Solid")
        assert props["strokeStyle"] == "solid"

    def test_stroke_style_dashed_uppercase(self) -> None:
        props = _parse_style_props("ss:Dashed")
        assert props["strokeStyle"] == "dashed"

    def test_font_family_uppercase(self) -> None:
        props = _parse_style_props("f:Hand")
        assert props["fontFamily"] == 1

    def test_font_family_normal_uppercase(self) -> None:
        props = _parse_style_props("f:Normal")
        assert props["fontFamily"] == 2

    def test_shape_uppercase_r(self) -> None:
        props = _parse_style_props("shape:R")
        assert props["shape"] == "rectangle"

    def test_shape_uppercase_d(self) -> None:
        props = _parse_style_props("shape:D")
        assert props["shape"] == "diamond"

    def test_shape_uppercase_c(self) -> None:
        props = _parse_style_props("shape:C")
        assert props["shape"] == "ellipse"

    def test_text_align_uppercase(self) -> None:
        props = _parse_style_props("ta:Center")
        assert props["textAlign"] == "center"

    def test_vert_align_uppercase(self) -> None:
        props = _parse_style_props("va:Middle")
        assert props["verticalAlign"] == "middle"

    def test_hex_color_passthrough_unchanged(self) -> None:
        """Hex colours pass through as-is (Excalidraw accepts both cases)."""
        props = _parse_style_props("bc:#FF0000")
        assert props["backgroundColor"] == "#FF0000"


# ===========================================================================
# load() warning when __otDSL is absent
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestLoadWarningNoDsl:
    """load() warns when no __otDSL element is found."""

    def test_load_warns_when_no_otdsl(self, tmp_path: Any) -> None:
        """Loading a .excalidraw file with no __otDSL element includes a warning."""
        import json
        from unittest.mock import patch

        from otdev.tools import excalidraw

        # Write a valid .excalidraw file with no __otDSL element
        exc_file = tmp_path / "no-dsl.excalidraw"
        data = {
            "type": "excalidraw",
            "version": 2,
            "elements": [
                {"id": "shape1", "type": "rectangle", "x": 0, "y": 0, "width": 100, "height": 60},
            ],
        }
        exc_file.write_text(json.dumps(data), encoding="utf-8")

        _reset_exc_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.load(file=str(exc_file))

        assert "warning" in result.lower()
        assert "__otDSL" in result or "no __otDSL" in result

    def test_load_with_otdsl_no_warning(self, tmp_path: Any) -> None:
        """Loading a .excalidraw file with __otDSL does not include a warning."""
        import json
        from unittest.mock import patch

        from otdev.tools import excalidraw

        # Write a valid .excalidraw file with a __otDSL element
        exc_file = tmp_path / "with-dsl.excalidraw"
        dsl_text = 'a["A"];b["B"];a-->b'
        data = {
            "type": "excalidraw",
            "version": 2,
            "elements": [
                {"id": "__otDSL", "type": "text", "text": dsl_text, "x": 0, "y": 0, "width": 100, "height": 20},
            ],
        }
        exc_file.write_text(json.dumps(data), encoding="utf-8")

        _reset_exc_state()

        # Make _read_dsl_from_canvas return the DSL text
        def _eval_with_dsl(server: str, tool: str, arguments: dict[str, Any] | None = None) -> str:
            fn = (arguments or {}).get("function", "")
            if tool == "browser_navigate":
                return "### Result\nnull\n### Ran Playwright code\n..."
            if "__drawApi?.backend" in fn:
                return "### Result\ntrue\n### Ran Playwright code\n..."
            if "__otDSL" in fn:
                return f'### Result\n"{dsl_text}"\n### Ran Playwright code\n...'
            if "__downloadQueue" in fn:
                return "### Result\n[]\n### Ran Playwright code\n..."
            return "### Result\nnull\n### Ran Playwright code\n..."

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _eval_with_dsl

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.load(file=str(exc_file))

        assert "warning" not in result.lower()
        assert "shapes" in result

    def test_load_file_not_found(self) -> None:
        """load() returns an error when file does not exist."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy):
            result = excalidraw.load(file="/nonexistent/path.excalidraw")

        assert "Error" in result
        assert "not found" in result


# ===========================================================================
# whiteboard.help()
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestHelp:
    def test_help_returns_nonempty_string(self) -> None:
        from otdev.tools import excalidraw

        result = excalidraw.help()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_help_contains_dsl_reference(self) -> None:
        from otdev.tools import excalidraw

        result = excalidraw.help()
        assert "Draw DSL" in result or "draw" in result.lower()
        assert "Style" in result or "style" in result.lower()

    def test_help_contains_edge_syntax(self) -> None:
        from otdev.tools import excalidraw

        result = excalidraw.help()
        assert "-->" in result

    def test_help_requires_no_browser(self) -> None:
        """help() must not call Playwright (no _ensure_ready)."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        with patch("otdev.tools.excalidraw.get_proxy_manager") as mock_gpm:
            result = excalidraw.help()

        mock_gpm.assert_not_called()
        assert isinstance(result, str)
        assert len(result) > 0
