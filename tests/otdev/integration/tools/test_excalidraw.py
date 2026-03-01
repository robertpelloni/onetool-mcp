"""Integration tests for the whiteboard (excalidraw) tool pack.

These tests run against a live Playwright browser navigated to excalidraw.com.
They verify that the JS injection layer actually works end-to-end — bootstrap,
_batch_draw, _batch_erase, _patch_elements, align, and layout.

Prerequisites:
  - The `playwright` MCP server must be connected to the live proxy manager.
  - Network access to excalidraw.com and the ELK CDN is required for layout().

Skip behaviour:
  - All tests are skipped automatically when `playwright` is not in proxy.servers.

Run command:
  uv run pytest tests/otdev/integration/tools/test_excalidraw.py -m integration -v
"""

from __future__ import annotations

import json
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_live_elements() -> list[dict[str, Any]]:
    """Read all non-deleted, non-text elements from the live canvas."""
    import otdev.tools.excalidraw as exc

    result = exc._browser_evaluate_json("() => Array.from(window.__drawApi.read())")
    if not isinstance(result, list):
        return []
    return [e for e in result if not e.get("isDeleted") and e.get("type") != "text"]


def _find_by_id(elements: list[dict[str, Any]], id_: str) -> dict[str, Any] | None:
    return next((e for e in elements if e.get("id") == id_), None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def _require_playwright():
    """Skip the entire module if the playwright server is not connected."""
    from ot.proxy.manager import get_proxy_manager

    proxy = get_proxy_manager()
    if "playwright" not in proxy.servers:
        pytest.skip("playwright MCP server not connected — skipping whiteboard integration tests")


@pytest.fixture(autouse=True)
def _clean_canvas():
    """Open a fresh whiteboard before each test; close cleanly after the module."""
    from otdev.tools import excalidraw

    result = excalidraw.open()
    if "Error" in result:
        pytest.skip(f"whiteboard open() failed: {result}")
    yield
    # Best-effort cleanup — don't fail the test on teardown errors
    try:
        excalidraw.clear()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 1. Bootstrap
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestBootstrap:
    """Verify that the Excalidraw page loads and the JS API is injected."""

    def test_open_returns_ready(self) -> None:
        from otdev.tools import excalidraw

        result = excalidraw.open()
        assert result == "whiteboard ready", f"open() returned: {result!r}"

    def test_draw_api_present_in_browser(self) -> None:
        """After open(), __drawApi must be accessible from JS."""
        import otdev.tools.excalidraw as exc

        result = exc._browser_evaluate_json(
            "() => typeof window.__drawApi !== 'undefined' && window.__drawApi.backend === 'excalidraw'"
        )
        assert result is True, f"__drawApi not ready: {result!r}"

    def test_draw_elements_dict_present(self) -> None:
        """After open(), __drawElements must be an object (possibly empty)."""
        import otdev.tools.excalidraw as exc

        result = exc._browser_evaluate_json(
            "() => typeof window.__drawElements === 'object' && window.__drawElements !== null"
        )
        assert result is True, f"__drawElements not initialised: {result!r}"

    def test_batch_draw_function_present(self) -> None:
        """_batch_draw helper must be injected and callable."""
        import otdev.tools.excalidraw as exc

        result = exc._browser_evaluate_json(
            "() => typeof window._batch_draw === 'function'"
        )
        assert result is True, f"_batch_draw not injected: {result!r}"

    def test_batch_erase_function_present(self) -> None:
        import otdev.tools.excalidraw as exc

        result = exc._browser_evaluate_json(
            "() => typeof window._batch_erase === 'function'"
        )
        assert result is True, f"_batch_erase not injected: {result!r}"

    def test_patch_elements_function_present(self) -> None:
        import otdev.tools.excalidraw as exc

        result = exc._browser_evaluate_json(
            "() => typeof window._patch_elements === 'function'"
        )
        assert result is True, f"_patch_elements not injected: {result!r}"


# ---------------------------------------------------------------------------
# 2. draw() — shapes and edges
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestDraw:
    """Verify that draw() creates real elements in the Excalidraw canvas."""

    def test_draw_single_shape_creates_element(self) -> None:
        from otdev.tools import excalidraw

        result = excalidraw.draw(input='alpha["Alpha"]')
        assert "shape" in result, f"draw() returned: {result!r}"

        els = _read_live_elements()
        assert _find_by_id(els, "alpha") is not None, "shape 'alpha' not found in canvas"

    def test_draw_two_shapes_creates_two_elements(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='p["P"]; q["Q"]')
        els = _read_live_elements()
        assert _find_by_id(els, "p") is not None, "'p' not in canvas"
        assert _find_by_id(els, "q") is not None, "'q' not in canvas"

    def test_draw_edge_creates_arrow(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='a["A"]; b["B"]; a-->b')
        els = _read_live_elements()
        arrows = [e for e in els if e.get("type") == "arrow"]
        assert arrows, "no arrow element found in canvas after drawing edge"

    def test_draw_edge_id_matches_expected_pattern(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='src["Src"]; dst["Dst"]; src-->dst')
        els = _read_live_elements()
        edge_ids = [e.get("id", "") for e in els if e.get("type") == "arrow"]
        assert any("src" in eid and "dst" in eid for eid in edge_ids), (
            f"no edge with 'src' and 'dst' in ID; found: {edge_ids}"
        )

    def test_draw_shape_has_correct_label(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='mybox["Hello World"]')
        # Label is stored in the text child element — read all elements including text
        import otdev.tools.excalidraw as exc

        all_els = exc._browser_evaluate_json("() => Array.from(window.__drawApi.read())")
        text_els = [e for e in all_els if e.get("type") == "text" and e.get("containerId") == "mybox"]
        assert text_els, "no text element with containerId='mybox' found"
        assert text_els[0].get("text") == "Hello World", (
            f"label mismatch: {text_els[0].get('text')!r}"
        )

    def test_draw_incremental_adds_to_existing(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='first["First"]')
        excalidraw.draw(input='second["Second"]')
        els = _read_live_elements()
        assert _find_by_id(els, "first") is not None, "'first' gone after second draw"
        assert _find_by_id(els, "second") is not None, "'second' not drawn"


# ---------------------------------------------------------------------------
# 3. clear() and erase()
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestClearErase:
    """Verify that clear() and erase() remove elements from the live canvas."""

    def test_clear_empties_canvas(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='x["X"]; y["Y"]')
        assert _read_live_elements(), "pre-condition: canvas should have elements"

        excalidraw.clear()
        els = _read_live_elements()
        assert not els, f"canvas not empty after clear(); {len(els)} element(s) remain"

    def test_erase_removes_specific_shape(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='keep["Keep"]; gone["Gone"]')
        result = excalidraw.erase(ids=["gone"])
        assert "erased" in result, f"erase() returned: {result!r}"

        els = _read_live_elements()
        assert _find_by_id(els, "gone") is None, "'gone' still in canvas after erase"
        assert _find_by_id(els, "keep") is not None, "'keep' was accidentally removed"

    def test_erase_edge_removes_arrow(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='a["A"]; b["B"]; a-->b')
        arrows_before = [e for e in _read_live_elements() if e.get("type") == "arrow"]
        assert arrows_before, "pre-condition: expected an arrow"

        edge_id = arrows_before[0]["id"]
        excalidraw.erase(ids=[edge_id])

        arrows_after = [e for e in _read_live_elements() if e.get("type") == "arrow"]
        assert not arrows_after, f"arrow still present after erase: {arrows_after}"


# ---------------------------------------------------------------------------
# 4. style()
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestStyle:
    """Verify that style() propagates property changes to live canvas elements."""

    def test_style_changes_background_color(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='box["Box"]')
        excalidraw.style(ids=["box"], style="bc:#ff0000")

        els = _read_live_elements()
        box = _find_by_id(els, "box")
        assert box is not None, "'box' not in canvas"
        assert box.get("backgroundColor") == "#ff0000", (
            f"backgroundColor not updated; got {box.get('backgroundColor')!r}"
        )

    def test_style_changes_stroke_color(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='node["Node"]')
        excalidraw.style(ids=["node"], style="sc:#00ff00")

        els = _read_live_elements()
        node = _find_by_id(els, "node")
        assert node is not None
        assert node.get("strokeColor") == "#00ff00", (
            f"strokeColor not updated; got {node.get('strokeColor')!r}"
        )

    def test_style_changes_stroke_width(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='box["Box"]')
        excalidraw.style(ids=["box"], style="sw:4")

        els = _read_live_elements()
        box = _find_by_id(els, "box")
        assert box is not None
        assert box.get("strokeWidth") == 4, (
            f"strokeWidth not updated; got {box.get('strokeWidth')!r}"
        )


# ---------------------------------------------------------------------------
# 5. align()
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestAlign:
    """Verify that align() actually moves elements in the live canvas.

    These tests confirm the fix for the async setAppState() race — align() must
    use action.perform() so the selection is visible synchronously.
    """

    def test_align_top_moves_elements_to_same_y(self) -> None:
        from otdev.tools import excalidraw

        # Draw at deliberately different y positions
        excalidraw.draw(input='p["P"] x:50,y:200; q["Q"] x:300,y:50; r["R"] x:550,y:350')
        before = {e["id"]: e["y"] for e in _read_live_elements() if e["id"] in ("p", "q", "r")}
        assert len(before) == 3, f"pre-condition: expected 3 shapes; got {before}"
        assert len(set(before.values())) > 1, "pre-condition: shapes should start at different y"

        result = excalidraw.align(ids=["p", "q", "r"], axis="top")
        assert "aligned" in result, f"align() returned: {result!r}"

        after = {e["id"]: e["y"] for e in _read_live_elements() if e["id"] in ("p", "q", "r")}
        assert len(set(after.values())) == 1, (
            f"elements not top-aligned; y values after align: {after}"
        )

    def test_align_left_moves_elements_to_same_x(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='a["A"] x:100,y:50; b["B"] x:300,y:200; c["C"] x:500,y:100')
        before_x = {e["id"]: e["x"] for e in _read_live_elements() if e["id"] in ("a", "b", "c")}
        assert len(set(before_x.values())) > 1, "pre-condition: shapes should start at different x"

        excalidraw.align(ids=["a", "b", "c"], axis="left")

        after_x = {e["id"]: e["x"] for e in _read_live_elements() if e["id"] in ("a", "b", "c")}
        assert len(set(after_x.values())) == 1, (
            f"elements not left-aligned; x values after align: {after_x}"
        )

    def test_align_vcenter_moves_elements_to_same_center_y(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='x["X"] x:50,y:100; y["Y"] x:300,y:300')

        excalidraw.align(ids=["x", "y"], axis="vcenter")

        els = {e["id"]: e for e in _read_live_elements() if e["id"] in ("x", "y")}
        assert len(els) == 2
        cx = els["x"]["y"] + els["x"].get("height", 60) / 2
        cy = els["y"]["y"] + els["y"].get("height", 60) / 2
        assert abs(cx - cy) < 1, f"vcenter mismatch: centers are {cx} and {cy}"


# ---------------------------------------------------------------------------
# 6. layout() — arrows follow repositioned nodes
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestLayout:
    """Verify that layout() repositions nodes and recomputes arrow endpoints.

    After layout() runs, each arrow's x/y should be near its source node's
    exit point, not at the original absolute canvas position.
    """

    def test_layout_moves_nodes(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='a["A"]; b["B"]; c["C"]; a-->b; b-->c')
        before = {e["id"]: (e["x"], e["y"]) for e in _read_live_elements() if e.get("type") != "arrow"}

        result = excalidraw.layout(direction="RIGHT")
        assert "layout applied" in result, f"layout() returned: {result!r}"

        after = {e["id"]: (e["x"], e["y"]) for e in _read_live_elements() if e.get("type") != "arrow"}
        moved = {id_ for id_ in before if id_ in after and before[id_] != after[id_]}
        assert moved, "no nodes moved after layout()"

    def test_layout_arrow_near_source_exit_right(self) -> None:
        """After layout(RIGHT), each arrow's x should be near its source's right edge."""
        from otdev.tools import excalidraw

        excalidraw.draw(input='a["A"]; b["B"]; a-->b')
        result = excalidraw.layout(direction="RIGHT")
        assert "layout applied" in result, f"layout() returned: {result!r}"

        all_els = {e["id"]: e for e in _read_live_elements()}
        arrows = [e for e in all_els.values() if e.get("type") == "arrow"]
        assert arrows, "no arrow in canvas after layout"

        node_a = all_els.get("a")
        assert node_a is not None, "node 'a' not found after layout"

        # Arrow origin should be within a small tolerance of a's right-center exit
        arrow = arrows[0]
        expected_x = node_a["x"] + node_a.get("width", 160)
        expected_y = node_a["y"] + node_a.get("height", 60) / 2
        tol = 30  # pixels — layout gaps and edge gap offsets cause slight variance

        arrow_x, arrow_y = arrow["x"], arrow["y"]
        assert abs(arrow_x - expected_x) <= tol, (
            f"arrow x={arrow_x:.0f} too far from source exit x={expected_x:.0f} (tol={tol})"
        )
        assert abs(arrow_y - expected_y) <= tol, (
            f"arrow y={arrow_y:.0f} too far from source exit y={expected_y:.0f} (tol={tol})"
        )

    def test_layout_down_arrow_near_source_bottom(self) -> None:
        """After layout(DOWN), arrow y should be near source's bottom edge."""
        from otdev.tools import excalidraw

        excalidraw.draw(input='top["Top"]; bot["Bot"]; top-->bot')
        result = excalidraw.layout(direction="DOWN")
        assert "layout applied" in result

        all_els = {e["id"]: e for e in _read_live_elements()}
        arrows = [e for e in all_els.values() if e.get("type") == "arrow"]
        assert arrows, "no arrow after layout"

        node_top = all_els.get("top")
        assert node_top is not None

        expected_y = node_top["y"] + node_top.get("height", 60)
        arrow_y = arrows[0]["y"]
        tol = 30

        assert abs(arrow_y - expected_y) <= tol, (
            f"arrow y={arrow_y:.0f} too far from source bottom y={expected_y:.0f} (tol={tol})"
        )


# ---------------------------------------------------------------------------
# 7. DSL embed (hidden metadata element)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestDslEmbed:
    """Verify that the hidden __otDSL text element is written and readable."""

    def test_draw_embeds_dsl_element(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='node["Node"]')

        import otdev.tools.excalidraw as exc

        all_els: list[dict[str, Any]] = exc._browser_evaluate_json(
            "() => Array.from(window.__drawApi.read())"
        )
        dsl_el = next((e for e in all_els if e.get("id") == "__otDSL"), None)
        assert dsl_el is not None, "__otDSL element not found in canvas"
        assert "node" in dsl_el.get("text", ""), (
            f"__otDSL text does not contain 'node': {dsl_el.get('text')!r}"
        )

    def test_dsl_element_is_low_opacity(self) -> None:
        """The DSL element must be visually subtle (opacity < 100)."""
        from otdev.tools import excalidraw

        excalidraw.draw(input='x["X"]')

        import otdev.tools.excalidraw as exc

        all_els: list[dict[str, Any]] = exc._browser_evaluate_json(
            "() => Array.from(window.__drawApi.read())"
        )
        dsl_el = next((e for e in all_els if e.get("id") == "__otDSL"), None)
        assert dsl_el is not None
        assert dsl_el.get("opacity", 100) < 100, (
            f"__otDSL opacity should be < 100; got {dsl_el.get('opacity')}"
        )


# ---------------------------------------------------------------------------
# 8. Elbow arrow routing
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestElbowArrow:
    """Verify that at:elbow arrows are injected with elbowed=true and a 2-point seed path.

    Excalidraw re-routes the connector orthogonally when elbowed=true is set alongside
    valid startBinding/endBinding. The 2-point seed path provides initial geometry so
    the arrow is visible; Excalidraw then computes the L-shaped route itself.
    """

    def test_elbow_arrow_has_elbowed_flag(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='src["Source"] x:100,y:100; dst["Dest"] x:400,y:300; src --> dst {at:elbow}')
        els = _read_live_elements()
        arrows = [e for e in els if e.get("type") == "arrow"]
        assert arrows, "no arrow element after drawing elbow edge"
        arrow = arrows[0]
        assert arrow.get("elbowed") is True, (
            f"elbow arrow missing elbowed=true; got elbowed={arrow.get('elbowed')!r}"
        )

    def test_elbow_arrow_has_two_points(self) -> None:
        """Elbow arrows carry a 2-point seed path so the arrow is visible."""
        from otdev.tools import excalidraw

        excalidraw.draw(input='a["A"] x:50,y:50; b["B"] x:400,y:300; a --> b {at:elbow}')
        els = _read_live_elements()
        arrows = [e for e in els if e.get("type") == "arrow"]
        assert arrows, "no arrow element after drawing elbow edge"
        points = arrows[0].get("points", [])
        assert len(points) == 2, (
            f"elbow arrow should have 2 seed points; got {len(points)}: {points}"
        )
