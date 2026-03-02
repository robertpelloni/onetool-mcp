"""Integration tests for the whiteboard (excalidraw) tool pack.

These tests run against a live Playwright browser navigated to excalidraw.com.
They verify that the JS injection layer actually works end-to-end — bootstrap,
_batch_draw, _batch_erase, _patch_elements, align, and layout.

Focus: Excalidraw browser integration, NOT Python logic (covered by unit tests).

Prerequisites:
  - The `playwright` MCP server must be connected to the live proxy manager.
  - Network access to excalidraw.com and the ELK CDN is required for layout().

Run command:
  uv run pytest tests/otdev/integration/tools/test_excalidraw.py -m integration -v
"""

from __future__ import annotations

import contextlib
import re
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_scene_positions(scene_text: str) -> dict[str, tuple[int, int]]:
    """Extract {id: (x, y)} from a full-detail read_scene() output.

    Only parses lines in the Shapes: and Edges: sections (indented lines),
    not headers like ``Scene: N shapes, M edges``.
    """
    positions: dict[str, tuple[int, int]] = {}
    for line in scene_text.splitlines():
        # Only look at indented element lines (shapes/edges start with 2+ spaces)
        if not line.startswith("  "):
            continue
        stripped = line.strip()
        if not stripped:
            continue
        id_match = re.match(r"(\S+)", stripped)
        pos_match = re.search(r"x:(-?\d+),y:(-?\d+)", stripped)
        if id_match and pos_match:
            positions[id_match.group(1)] = (
                int(pos_match.group(1)),
                int(pos_match.group(2)),
            )
    return positions


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_canvas():
    """Open a fresh whiteboard before each test; close cleanly after the module."""
    from otdev.tools import excalidraw

    result = excalidraw.open()
    if "Error" in result:
        pytest.fail(f"whiteboard open() failed: {result}")
    yield
    # Best-effort cleanup — don't fail the test on teardown errors
    with contextlib.suppress(Exception):
        excalidraw.clear()


# ---------------------------------------------------------------------------
# 1. Bootstrap — verify JS API injection
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestBootstrap:
    """Verify that the Excalidraw page loads and the JS API is injected."""

    def test_bootstrap_js_api(self) -> None:
        """open() returns ready and all 5 JS functions are present."""
        import otdev.tools.excalidraw as exc

        result = exc.open()
        assert result == "whiteboard ready", f"open() returned: {result!r}"

        # Check all injected JS functions
        check_js = """() => {
            const fns = ['__drawApi', '__drawElements', '_batch_draw', '_batch_erase', '_patch_elements'];
            const missing = fns.filter(f => typeof window[f] === 'undefined' || (typeof window[f] !== 'function' && typeof window[f] !== 'object'));
            return missing;
        }"""
        missing = exc._browser_evaluate_json(check_js)
        assert missing == [], f"Missing JS functions: {missing}"


# ---------------------------------------------------------------------------
# 2. draw() — shapes, labels, edges, incremental
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestDrawShapesAndLabels:
    """Verify draw() creates elements with correct labels, edges, and incremental behavior."""

    def test_draw_shapes_and_labels(self) -> None:
        from otdev.tools import excalidraw

        # Single shape with label
        result = excalidraw.draw(input='alpha["Alpha"]')
        assert "shape" in result, f"draw() returned: {result!r}"
        scene = excalidraw.read_scene()
        assert "alpha" in scene, "shape 'alpha' not found in canvas"
        assert '"Alpha"' in scene, "label 'Alpha' not found in scene"

        # Two more shapes
        excalidraw.draw(input='p["P"]; q["Q"]')
        scene = excalidraw.read_scene()
        assert "p" in scene, "'p' not in canvas"
        assert "q" in scene, "'q' not in canvas"

        # Incremental — first shapes still present
        assert "alpha" in scene, "'alpha' gone after second draw"


# ---------------------------------------------------------------------------
# 3. draw() — edges
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestDrawEdges:
    """Verify draw() creates arrows with correct bindings and elbow routing."""

    def test_draw_edges(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='src["Src"]; dst["Dst"]; src-->dst')

        # Edge exists
        scene_min = excalidraw.read_scene(info="min")
        assert "1 edges" in scene_min, f"no edge found: {scene_min}"

        # Edge line contains src and dst
        scene = excalidraw.read_scene()
        assert "Edges:" in scene, f"no Edges section: {scene}"
        edges_section = scene.split("Edges:")[1]
        assert "src" in edges_section and "dst" in edges_section, (
            f"edge line missing src/dst: {edges_section}"
        )

        # Elbow arrow has at:elbow flag
        excalidraw.draw(input='a["A"] x:100,y:300; b["B"] x:400,y:500; a --> b {at:elbow}')
        scene_full = excalidraw.read_scene(info="full")
        edges_full = scene_full.split("Edges:")[1] if "Edges:" in scene_full else ""
        assert "at:elbow" in edges_full, (
            f"elbow arrow missing at:elbow in scene: {edges_full}"
        )


# ---------------------------------------------------------------------------
# 4. clear() and erase()
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestClearAndErase:
    """Verify clear() and erase() remove elements from the live canvas."""

    def test_clear_and_erase(self) -> None:
        from otdev.tools import excalidraw

        # Draw shapes and an edge
        excalidraw.draw(input='keep["Keep"]; gone["Gone"]; a["A"]; b["B"]; a-->b')
        scene_before = excalidraw.read_scene(info="min")
        assert "0 shapes" not in scene_before, "pre-condition: canvas should have elements"

        # Erase specific shape — others remain
        result = excalidraw.erase(ids=["gone"])
        assert "erased" in result, f"erase() returned: {result!r}"
        scene = excalidraw.read_scene()
        assert "gone" not in scene, "'gone' still in canvas after erase"
        assert "keep" in scene, "'keep' was accidentally removed"

        # Erase edge by id
        full_scene = excalidraw.read_scene()
        edges_section = full_scene.split("Edges:")[1] if "Edges:" in full_scene else ""
        edge_id_match = re.match(r"\s*(\S+)", edges_section.strip())
        assert edge_id_match, f"could not parse edge id from: {edges_section}"
        edge_id = edge_id_match.group(1)

        excalidraw.erase(ids=[edge_id])
        scene_after = excalidraw.read_scene(info="min")
        assert "0 edges" in scene_after, f"arrow still present after erase: {scene_after}"

        # Clear empties canvas
        excalidraw.clear()
        scene_cleared = excalidraw.read_scene(info="min")
        assert "0 shapes, 0 edges" in scene_cleared, (
            f"canvas not empty after clear(): {scene_cleared}"
        )


# ---------------------------------------------------------------------------
# 5. style()
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestStyle:
    """Verify style() propagates property changes to live canvas elements."""

    def test_style_properties(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='box["Box"]')

        # Background colour
        excalidraw.style(ids=["box"], style="bc:#ff0000")
        scene = excalidraw.read_scene()
        box_line = next((ln for ln in scene.splitlines() if ln.strip().startswith("box")), None)
        assert box_line is not None, f"'box' not in scene: {scene}"
        assert "bc:#ff0000" in box_line, f"backgroundColor not updated: {box_line}"

        # Stroke colour
        excalidraw.style(ids=["box"], style="sc:#00ff00")
        scene = excalidraw.read_scene()
        box_line = next((ln for ln in scene.splitlines() if ln.strip().startswith("box")), None)
        assert "sc:#00ff00" in box_line, f"strokeColor not updated: {box_line}"

        # Stroke width (needs full detail)
        excalidraw.style(ids=["box"], style="sw:4")
        scene = excalidraw.read_scene(info="full")
        box_line = next((ln for ln in scene.splitlines() if ln.strip().startswith("box")), None)
        assert "sw:4" in box_line, f"strokeWidth not updated: {box_line}"


# ---------------------------------------------------------------------------
# 6. align()
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestAlign:
    """Verify align() actually moves elements in the live canvas."""

    def test_align_top_and_left(self) -> None:
        from otdev.tools import excalidraw

        # Top alignment — all y values should match
        excalidraw.draw(input='p["P"] x:50,y:200; q["Q"] x:300,y:50; r["R"] x:550,y:350')
        before = _parse_scene_positions(excalidraw.read_scene(info="full"))
        assert len({v[1] for k, v in before.items() if k in ("p", "q", "r")}) > 1, (
            "pre-condition: shapes should start at different y"
        )

        result = excalidraw.align(ids=["p", "q", "r"], axis="top")
        assert "aligned" in result, f"align() returned: {result!r}"

        after = _parse_scene_positions(excalidraw.read_scene(info="full"))
        y_values = {after[k][1] for k in ("p", "q", "r") if k in after}
        assert len(y_values) == 1, f"elements not top-aligned; y values: {after}"

        # Left alignment — redraw with different x positions
        excalidraw.clear()
        excalidraw.draw(input='a["A"] x:100,y:50; b["B"] x:300,y:200; c["C"] x:500,y:100')
        excalidraw.align(ids=["a", "b", "c"], axis="left")

        after2 = _parse_scene_positions(excalidraw.read_scene(info="full"))
        x_values = {after2[k][0] for k in ("a", "b", "c") if k in after2}
        assert len(x_values) == 1, f"elements not left-aligned; x values: {after2}"


# ---------------------------------------------------------------------------
# 7. layout()
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestLayout:
    """Verify layout() repositions nodes and recomputes arrow endpoints."""

    def test_layout_moves_nodes(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='a["A"]; b["B"]; c["C"]; a-->b; b-->c')
        before = _parse_scene_positions(excalidraw.read_scene(info="full"))

        result = excalidraw.layout(direction="RIGHT")
        assert "layout applied" in result, f"layout() returned: {result!r}"

        after = _parse_scene_positions(excalidraw.read_scene(info="full"))
        shape_ids = {k for k in before if k in after and k in ("a", "b", "c")}
        moved = {id_ for id_ in shape_ids if before[id_] != after[id_]}
        assert moved, "no nodes moved after layout()"

        # After RIGHT layout, nodes should be ordered left-to-right: a.x < b.x < c.x
        assert after["a"][0] < after["b"][0], (
            f"a.x ({after['a'][0]}) should be < b.x ({after['b'][0]}) after RIGHT layout"
        )
        assert after["b"][0] < after["c"][0], (
            f"b.x ({after['b'][0]}) should be < c.x ({after['c'][0]}) after RIGHT layout"
        )


# ---------------------------------------------------------------------------
# 8. Elbow arrow seed path (raw JS — verifies browser-side geometry)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestElbowArrowPoints:
    """Verify elbow arrows carry a 2-point seed path in the live canvas."""

    def test_elbow_arrow_has_two_points(self) -> None:
        from otdev.tools import excalidraw

        excalidraw.draw(input='a["A"] x:50,y:50; b["B"] x:400,y:300; a --> b {at:elbow}')

        import otdev.tools.excalidraw as exc

        all_els: list[dict[str, Any]] = exc._browser_evaluate_json(
            "() => Array.from(window.__drawApi.read())"
        )
        arrows = [e for e in all_els if e.get("type") == "arrow" and not e.get("isDeleted")]
        assert arrows, "no arrow element after drawing elbow edge"
        points = arrows[0].get("points", [])
        assert len(points) == 2, (
            f"elbow arrow should have 2 seed points; got {len(points)}: {points}"
        )
