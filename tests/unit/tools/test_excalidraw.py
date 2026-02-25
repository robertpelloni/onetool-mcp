"""Unit tests for the wb (whiteboard) tool pack.

Tests cover: parse_dsl, _build_dsl, auto_layout, _resolve_style, and
smoke tests for public tools with mocked Playwright.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from otdev.tools.excalidraw import (
    _build_dsl,
    _parse_style_props,
    _resolve_style,
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

    def test_classdef(self) -> None:
        result = parse_dsl('classDef svc fill:#dae8fc,stroke:#6c8ebf;')
        assert "svc" in result["classes"]
        assert result["classes"]["svc"]["fill"] == "#dae8fc"
        assert result["classes"]["svc"]["stroke"] == "#6c8ebf"

    def test_class_assignment(self) -> None:
        result = parse_dsl(
            'a["A"]\nb["B"]\n'
            'classDef svc fill:#fff;\n'
            'class a,b svc'
        )
        assert "svc" in result["shapes"]["a"]["classes"]
        assert "svc" in result["shapes"]["b"]["classes"]

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

    def test_classdef_round_trip(self) -> None:
        dsl = 'a["A"]\nclassDef svc fill:#fff,stroke:#000;\nclass a svc'
        rt = self._round_trip(dsl)
        assert "svc" in rt["classes"]
        assert "svc" in rt["shapes"]["a"]["classes"]

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
        state: dict[str, Any] = {"shapes": {}, "classes": {}, "edges": [], "groups": {}}
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
        # top should be at layer 0, bot at layer 2
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
# 6.4 _resolve_style
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestResolveStyle:
    def test_defaults_when_no_classes(self) -> None:
        shape: dict[str, Any] = {"label": "A", "classes": []}
        style = _resolve_style(shape, {})
        assert style["backgroundColor"] == "#ffffff"
        assert style["strokeColor"] == "#1e1e1e"
        assert style["strokeWidth"] == 2
        assert style["color"] == "#1e1e1e"

    def test_fill_maps_to_background(self) -> None:
        classes = {"svc": {"fill": "#dae8fc"}}
        shape: dict[str, Any] = {"label": "A", "classes": ["svc"]}
        style = _resolve_style(shape, classes)
        assert style["backgroundColor"] == "#dae8fc"

    def test_stroke_maps_to_stroke_color(self) -> None:
        classes = {"svc": {"stroke": "#6c8ebf"}}
        shape: dict[str, Any] = {"label": "A", "classes": ["svc"]}
        style = _resolve_style(shape, classes)
        assert style["strokeColor"] == "#6c8ebf"

    def test_color_maps_to_text_color(self) -> None:
        classes = {"svc": {"color": "#ff0000"}}
        shape: dict[str, Any] = {"label": "A", "classes": ["svc"]}
        style = _resolve_style(shape, classes)
        assert style["color"] == "#ff0000"

    def test_stroke_width(self) -> None:
        classes = {"thick": {"stroke-width": "4"}}
        shape: dict[str, Any] = {"label": "A", "classes": ["thick"]}
        style = _resolve_style(shape, classes)
        assert style["strokeWidth"] == 4

    def test_stroke_style(self) -> None:
        classes = {"dashed": {"stroke-style": "dashed"}}
        shape: dict[str, Any] = {"label": "A", "classes": ["dashed"]}
        style = _resolve_style(shape, classes)
        assert style["strokeStyle"] == "dashed"

    def test_roughness(self) -> None:
        classes = {"smooth": {"roughness": "0"}}
        shape: dict[str, Any] = {"label": "A", "classes": ["smooth"]}
        style = _resolve_style(shape, classes)
        assert style["roughness"] == 0

    def test_edges_sharp(self) -> None:
        classes = {"sharp": {"edges": "sharp"}}
        shape: dict[str, Any] = {"label": "A", "classes": ["sharp"]}
        style = _resolve_style(shape, classes)
        assert style["roundness"] is None

    def test_edges_round(self) -> None:
        classes = {"rounded": {"edges": "round"}}
        shape: dict[str, Any] = {"label": "A", "classes": ["rounded"]}
        style = _resolve_style(shape, classes)
        assert style["roundness"] == {"type": 3}

    def test_font_family_normal(self) -> None:
        classes = {"f": {"font-family": "normal"}}
        shape: dict[str, Any] = {"label": "A", "classes": ["f"]}
        style = _resolve_style(shape, classes)
        assert style["fontFamily"] == 2

    def test_font_size_named(self) -> None:
        classes = {"f": {"font-size": "L"}}
        shape: dict[str, Any] = {"label": "A", "classes": ["f"]}
        style = _resolve_style(shape, classes)
        assert style["fontSize"] == 28

    def test_text_align(self) -> None:
        classes = {"la": {"text-align": "left"}}
        shape: dict[str, Any] = {"label": "A", "classes": ["la"]}
        style = _resolve_style(shape, classes)
        assert style["textAlign"] == "left"

    def test_opacity(self) -> None:
        classes = {"op": {"opacity": "80"}}
        shape: dict[str, Any] = {"label": "A", "classes": ["op"]}
        style = _resolve_style(shape, classes)
        assert style["opacity"] == 80

    def test_multiple_classes_merge(self) -> None:
        classes = {
            "base": {"fill": "#fff", "stroke": "#000"},
            "highlight": {"fill": "#ff0"},
        }
        shape: dict[str, Any] = {"label": "A", "classes": ["base", "highlight"]}
        style = _resolve_style(shape, classes)
        assert style["backgroundColor"] == "#ff0"
        assert style["strokeColor"] == "#000"

    def test_unknown_class_ignored(self) -> None:
        shape: dict[str, Any] = {"label": "A", "classes": ["nonexistent"]}
        style = _resolve_style(shape, {})
        assert style["backgroundColor"] == "#ffffff"


# ===========================================================================
# 6.5 Smoke tests for public tools (mocked Playwright)
# ===========================================================================


def _reset_exc_state() -> None:
    """Reset module-level excalidraw state between tests."""
    import otdev.tools.excalidraw as exc

    exc._dsl_state = {"shapes": {}, "classes": {}, "edges": [], "groups": {}}
    exc._edge_keys = set()
    exc._rendered_ids = set()
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
        # browser_evaluate should have been called (bootstrap check + shapes)
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
        # Verify __drawApi.clear() was called
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

    def test_save_calls_read_and_writes_file(
        self, tmp_path: Any
    ) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect
        out_file = str(tmp_path / "out.md")

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw.resolve_cwd_path", return_value=tmp_path / "out.md"),
        ):
            result = excalidraw.save(file=out_file)

        assert "saved" in result
        content = (tmp_path / "out.md").read_text()
        assert "[dsl]" in content
        assert "[scene]" in content

    def test_load_restores_state(self, tmp_path: Any) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        # Create a minimal saved diagram file in new [dsl]/[scene] format
        content = (
            "[dsl]\n"
            'a["A"]\n'
            'b["B"]\n'
            "a-->b\n"
            "[scene]\n"
            '[{"id": "a", "x": 0, "y": 0, "w": 160, "h": 60}]\n'
        )
        diag_file = tmp_path / "diag.exc"
        diag_file.write_text(content)

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw.resolve_cwd_path", return_value=diag_file),
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

    def test_load_returns_error_for_missing_dsl_block(self, tmp_path: Any) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        diag_file = tmp_path / "bad.wb"
        diag_file.write_text("no dsl block here\n")

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw.resolve_cwd_path", return_value=diag_file),
        ):
            result = excalidraw.load(file=str(diag_file))

        assert "Error" in result
        assert "[dsl]" in result

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
        exc._dsl_state = {"shapes": {"a": {"label": "A", "classes": []}}, "classes": {}, "edges": [], "groups": {}}
        exc._rendered_ids = {"a"}
        exc._edge_keys = set()
        exc._max_rendered_y = 100.0

        # No Playwright server — should still reset Python state
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
        assert "browser_tab_close" in calls or "browser_navigate" in calls

    def test_bootstrap_failure_returns_error(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_proxy = _make_mock_proxy()

        def bootstrap_fail_side_effect(server: str, tool: str, arguments: Any = None) -> str:
            if tool == "browser_navigate":
                return "### Result\nnull\n### Ran Playwright code\n..."
            fn = (arguments or {}).get("function", "")
            if "__drawApi?.backend" in fn:
                # Not ready — force a navigate + bootstrap attempt
                return "### Result\nfalse\n### Ran Playwright code\n..."
            # bootstrap.js contains `window.__drawElements` — simulate fiber-not-found
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
            # Add c connected to b — c should land at layer 2, not layer 0
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

        # "typo" is auto-created as a shape with label "typo"
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
        """_js_batch_draw must call browser_evaluate with 3 separate JSON args, not 1 object."""
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
        # Must pass three separate args, not a single {shapes:…} object
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
        exc._dsl_state = {"shapes": {}, "classes": {}, "edges": [], "groups": {}}
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
        exc._dsl_state = {"shapes": {}, "classes": {}, "edges": [], "groups": {}}
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
        # With 3 cyclic nodes, grid fallback assigns them to different layers,
        # so not all should have the same x (cols=2 → at least two distinct x values)
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
            {"id": "e3", "src": "b", "dst": "a", "label": ""},  # cycle between a and b
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

    def test_note_tool_returns_error_on_no_blocks(self) -> None:
        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        exc._dsl_state = {"shapes": {}, "classes": {}, "edges": [], "groups": {}}
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
        exc._dsl_state = {"shapes": {}, "classes": {}, "edges": [], "groups": {}}
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
        assert "t" in result  # block id included
        mock_batch.assert_not_called()  # no shape was inserted on canvas

    def test_note_unknown_type_returns_error(self) -> None:
        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        exc._dsl_state = {"shapes": {}, "classes": {}, "edges": [], "groups": {}}
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
        exc._dsl_state = {"shapes": {}, "classes": {}, "edges": [], "groups": {}}
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

        # Two siblings under root — first should show "│   " continuation line
        result = render_tree("root\n-child1\n--leaf1\n-child2")
        lines = result.splitlines()
        # child1 has a sibling (child2) so leaf1 should be under a continued branch
        assert any("│" in ln for ln in lines), "sibling branch should show │ connector"
        # child2 is the last child so it uses └──
        assert "child2" in result
        assert any("└──" in ln for ln in lines)

    def test_render_tree_no_false_sibling_across_subtree(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        # leaf1 and leaf2 are NOT siblings (they belong to different parents)
        result = render_tree("root\n-child1\n--leaf1\n-child2\n--leaf2")
        lines = result.splitlines()
        leaf1_line = next(ln for ln in lines if "leaf1" in ln)
        # leaf1 is last under child1, so no │ continuation in its prefix
        assert "leaf1" in leaf1_line
        assert "└──" in leaf1_line or "├──" in leaf1_line

    def test_render_tree_true_siblings_continuation(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        # leaf1 and leaf2 ARE siblings (same parent child1)
        result = render_tree("root\n-child1\n--leaf1\n--leaf2")
        lines = result.splitlines()
        leaf1_line = next(ln for ln in lines if "leaf1" in ln)
        # leaf1 has a sibling (leaf2) — rendered with ├── connector
        assert "├──" in leaf1_line

    def test_render_tree_unicode_connectors(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        result = render_tree("root\n-child1\n-child2")
        assert "├──" in result   # first child uses ├──
        assert "└──" in result   # last child uses └──

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
        exc._max_rendered_y = 200.0  # simulate existing canvas content

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


# ===========================================================================
# Shape types (ellipse, diamond)
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestShapeTypes:
    def test_parse_ellipse(self) -> None:
        result = parse_dsl('a(("Oval"))')
        assert "a" in result["shapes"]
        assert result["shapes"]["a"]["label"] == "Oval"
        assert result["shapes"]["a"]["type"] == "ellipse"

    def test_parse_diamond(self) -> None:
        result = parse_dsl('a{"Decision"}')
        assert "a" in result["shapes"]
        assert result["shapes"]["a"]["label"] == "Decision"
        assert result["shapes"]["a"]["type"] == "diamond"

    def test_rectangle_has_no_explicit_type(self) -> None:
        result = parse_dsl('a["Box"]')
        assert "type" not in result["shapes"]["a"]

    def test_build_dsl_round_trips_ellipse(self) -> None:
        result = parse_dsl('a(("Oval"))')
        dsl = _build_dsl({"shapes": result["shapes"], "classes": {}, "edges": [], "groups": {}})
        assert '(("Oval"))' in dsl

    def test_build_dsl_round_trips_diamond(self) -> None:
        result = parse_dsl('a{"Decision"}')
        dsl = _build_dsl({"shapes": result["shapes"], "classes": {}, "edges": [], "groups": {}})
        assert '{"Decision"}' in dsl

    def test_draw_passes_ellipse_shape_type(self) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        import otdev.tools.excalidraw as exc
        exc._dsl_state = {"shapes": {}, "classes": {}, "edges": [], "groups": {}}
        exc._rendered_ids = set()
        exc._edge_keys = set()
        exc._max_rendered_y = 0.0

        mock_proxy = _make_mock_proxy()
        mock_proxy.call_tool_sync.side_effect = _playwright_eval_side_effect

        with (
            patch("otdev.tools.excalidraw.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.excalidraw._js_batch_draw") as mock_batch,
        ):
            excalidraw.draw(input='a(("Node"))')

        _, kwargs = mock_batch.call_args
        assert kwargs["shapes"][0]["shape"] == "ellipse"


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
        # A and a both normalise to 'a'; second declaration overwrites
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

    def test_class_assignment_normalised(self) -> None:
        result = parse_dsl(
            'A["A"]\nclassDef svc fill:#fff;\nclass A svc'
        )
        assert "svc" in result["shapes"]["a"]["classes"]
