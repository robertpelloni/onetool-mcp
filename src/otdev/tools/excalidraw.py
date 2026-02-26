"""Excalidraw tool pack — Playwright-driven live diagram manipulation.

Opens excalidraw.com via Playwright and exposes tools to draw, save, load,
clear, scroll, and zoom diagrams using a Mermaid-compatible DSL.

Requires the Playwright MCP server to be enabled:
    ot.server(enable='playwright')
"""

from __future__ import annotations

# Pack declaration MUST be before other imports
pack = "wb"

__all__ = [
    "clear",
    "close",
    "draw",
    "embed_dsl",
    "erase",
    "fit",
    "hard_reset",
    "load",
    "note",
    "open",
    "save",
    "screenshot",
    "scroll",
    "zoom",
]

import base64
import contextlib
import json
import re
from collections import defaultdict, deque
from importlib import resources
from typing import Any

from ot.logging import LogSpan
from ot.paths import resolve_cwd_path
from ot.proxy import get_proxy_manager

# ---------------------------------------------------------------------------
# Module-level DSL state
# ---------------------------------------------------------------------------

_dsl_state: dict[str, Any] = {"shapes": {}, "classes": {}, "edges": [], "groups": {}}
_edge_keys: set[tuple[str, str, str, str | None, str | None]] = set()
_rendered_ids: set[str] = set()
_max_rendered_y: float = 0.0

# ---------------------------------------------------------------------------
# JS asset loader
# ---------------------------------------------------------------------------

def _load_js(filename: str) -> str:
    """Load a bundled JavaScript file from disk."""
    return (
        resources.files("otdev.tools._excalidraw")
        .joinpath(filename)
        .read_text(encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# Playwright helpers
# ---------------------------------------------------------------------------

_PLAYWRIGHT_SERVER = "playwright"


def _check_playwright() -> str | None:
    """Return error string if Playwright server not connected, else None."""
    proxy = get_proxy_manager()
    if _PLAYWRIGHT_SERVER not in proxy.servers:
        return (
            "Error: Playwright server not connected. "
            "Enable with `ot.server(enable='playwright')`"
        )
    return None


def _extract_playwright_result(raw: str | Any) -> str:
    """Extract value from a Playwright browser_evaluate response."""
    raw_str = str(raw)
    marker = "### Result\n"
    if raw_str.startswith(marker):
        value = raw_str[len(marker):]
        end = value.find("\n### ")
        if end != -1:
            value = value[:end]
        return value.strip()
    return raw_str.strip()


def _browser_navigate(url: str) -> None:
    """Navigate the Playwright browser to the given URL."""
    proxy = get_proxy_manager()
    proxy.call_tool_sync(_PLAYWRIGHT_SERVER, "browser_navigate", {"url": url})


def _browser_evaluate(fn: str) -> str:
    """Evaluate a JS function string in the browser and return the raw result."""
    proxy = get_proxy_manager()
    raw = proxy.call_tool_sync(
        _PLAYWRIGHT_SERVER, "browser_evaluate", {"function": fn}
    )
    return _extract_playwright_result(raw)


def _browser_evaluate_json(fn: str) -> Any:
    """Evaluate a JS function and JSON-parse the result."""
    raw = _browser_evaluate(fn)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


# ---------------------------------------------------------------------------
# JS batch draw caller
# ---------------------------------------------------------------------------


def _js_batch_draw(
    *,
    shapes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    subgraphs: list[dict[str, Any]],
) -> None:
    """Send all shapes, edges, and subgraphs to the browser in one round-trip."""
    s_json = json.dumps(shapes)
    e_json = json.dumps(edges)
    f_json = json.dumps(subgraphs)
    _browser_evaluate(f"() => window._batch_draw({s_json}, {e_json}, {f_json})")


# ---------------------------------------------------------------------------
# Browser lifecycle
# ---------------------------------------------------------------------------


def _ensure_ready() -> str | None:
    """Ensure excalidraw.com is open and bootstrapped.

    Returns error string if Playwright not available, else None.
    Handles: first call, closed tab, navigated-away page, page reload.
    """
    err = _check_playwright()
    if err:
        return err

    try:
        result = _browser_evaluate(
            "() => !!(window.__drawApi?.backend === 'excalidraw' "
            "&& location.hostname.includes('excalidraw.com'))"
        )
        ready = result.lower() == "true"
    except Exception:
        ready = False

    if not ready:
        _browser_navigate("https://excalidraw.com")
        # Wait for React to mount (10s timeout)
        try:
            _browser_evaluate(
                "() => new Promise((resolve, reject) => {"
                "  const tid = setTimeout(() => reject(new Error('timeout')), 10000);"
                "  const check = () => document.getElementById('root')?.children.length > 0"
                "    ? (clearTimeout(tid), resolve()) : setTimeout(check, 100);"
                "  check();"
                "})"
            )
        except Exception:
            return "Error: timed out waiting for excalidraw.com to load"
        bootstrap_result = _browser_evaluate(_load_js("bootstrap.js"))
        if bootstrap_result.strip().lower() == "false":
            return "Error: excalidraw bootstrap failed — React API not found on page"
        # Wait for __drawApi to be set — bootstrap may run before Excalidraw fully mounts (10s timeout)
        try:
            _browser_evaluate(
                "() => new Promise((resolve, reject) => {"
                "  const tid = setTimeout(() => reject(new Error('timeout')), 10000);"
                "  const check = () => typeof window.__drawApi !== 'undefined'"
                "    ? (clearTimeout(tid), resolve(true)) : setTimeout(check, 100);"
                "  check();"
                "})"
            )
        except Exception:
            return "Error: timed out waiting for __drawApi to initialise"
        if _dsl_state["shapes"]:
            _rerender_from_state()

    elif not _rendered_ids:
        # Ready but nothing tracked — check for untracked canvas content
        try:
            live = _browser_evaluate_json("() => Array.from(window.__drawApi.read())")
            if isinstance(live, list):
                untracked = [
                    e for e in live
                    if isinstance(e, dict)
                    and not e.get("id", "").startswith("__")
                    and not e.get("isDeleted", False)
                ]
                if untracked:
                    for e in untracked:
                        _rendered_ids.add(e["id"])
        except Exception:
            pass

    # Always re-inject ops.js so in-place code changes take effect without a page reload
    _browser_evaluate(_load_js("ops.js"))

    return None


def _rerender_from_state() -> None:
    """Re-render all content from _dsl_state after a page loss.

    Visual positions revert to auto-layout. To preserve positions,
    call save_diag() before any risky operations.
    """
    global _max_rendered_y
    _rendered_ids.clear()
    positions = auto_layout(_dsl_state["shapes"], _dsl_state["edges"])

    shape_payloads = []
    for id_, shape in _dsl_state["shapes"].items():
        x, y = positions[id_]
        style = _resolve_style(shape, _dsl_state["classes"])
        shape_payloads.append(
            {"id": id_, "label": shape["label"], "x": x, "y": y,
             "w": 160, "h": 60, "shape": shape.get("type", "rectangle"), "styleProps": style}
        )

    edge_payloads = [
        {"id": e["id"], "srcId": e["src"], "dstId": e["dst"],
         "label": e["label"], "startArrowhead": e.get("startArrowhead"),
         "endArrowhead": e.get("endArrowhead", "arrow")}
        for e in _dsl_state["edges"]
    ]

    subgraph_payloads = [
        {"id": gid, "label": group["label"], "memberIds": group["members"], "savedBounds": None}
        for gid, group in _dsl_state["groups"].items()
    ]

    _js_batch_draw(shapes=shape_payloads, edges=edge_payloads, subgraphs=subgraph_payloads)
    _rendered_ids.update(s["id"] for s in shape_payloads)
    _rendered_ids.update(e["id"] for e in edge_payloads)
    if shape_payloads:
        _max_rendered_y = max(s["y"] + s["h"] for s in shape_payloads)


# ---------------------------------------------------------------------------
# DSL parser
# ---------------------------------------------------------------------------

_RE_HEADER = re.compile(r"^(?:flowchart|graph)\s+\w+$")
_RE_SHAPE = re.compile(r'^([\w-]+)\s*\[\s*"?([^"\]]*)"?\s*\]$')
_RE_SHAPE_ELLIPSE = re.compile(r'^([\w-]+)\s*\(\s*\(\s*"?([^")]*)"?\s*\)\s*\)$')
_RE_SHAPE_DIAMOND = re.compile(r'^([\w-]+)\s*\{\s*"?([^"}]*)"?\s*\}$')
_RE_CLASSDEF = re.compile(r"^classDef\s+([\w-]+)\s+(.+?);?$")
_RE_CLASS = re.compile(r"^class\s+([\w,\s-]+)\s+([\w-]+)$")
_RE_EDGE_ARR = re.compile(r"^([\w-]+)\s*-->(?:\|([^|]*)\|)?\s*([\w-]+)$")
_RE_EDGE_BIDIR = re.compile(r"^([\w-]+)\s*<-->(?:\|([^|]*)\|)?\s*([\w-]+)$")
_RE_EDGE_UND = re.compile(r"^([\w-]+)\s*---\s*([\w-]+)$")
_RE_EDGE_DOT = re.compile(r"^([\w-]+)\s*--o(?:\|([^|]*)\|)?\s*([\w-]+)$")
_RE_EDGE_BAR = re.compile(r"^([\w-]+)\s*--x(?:\|([^|]*)\|)?\s*([\w-]+)$")
_RE_EDGE_DASHED_ARR = re.compile(r"^([\w-]+)\s*-\.->(?:\|([^|]*)\|)?\s*([\w-]+)$")
_RE_EDGE_DASHED_UND = re.compile(r"^([\w-]+)\s*-\.-\s*([\w-]+)$")
_RE_SUBGRAPH = re.compile(r'^subgraph\s+([\w-]+)(?:\s+\[\s*"([^"]+)"\s*\])?$')


def _norm_id(raw: str) -> str:
    """Normalise a node ID: strip non-word chars (except underscore), lowercase."""
    return re.sub(r"[^\w]", "", raw).lower()


def _parse_style_props(s: str) -> dict[str, str]:
    """Parse a comma-separated `key:value` style string."""
    props: dict[str, str] = {}
    for part in s.split(","):
        if ":" in part:
            k, v = part.strip().split(":", 1)
            props[k.strip()] = v.strip()
    return props


def parse_dsl(spec: str) -> dict[str, Any]:
    """Parse a Mermaid-compatible DSL string into a structured dict.

    Args:
        spec: DSL string with shapes, edges, classDefs, and subgraphs.

    Returns:
        Dict with keys: shapes, classes, edges, groups.
    """
    shapes: dict[str, Any] = {}
    classes: dict[str, Any] = {}
    edges: list[dict[str, Any]] = []
    groups: dict[str, Any] = {}
    current_subgraph: dict[str, Any] | None = None

    # Normalize real newlines inside quoted labels to the \n escape so they
    # survive line-splitting. Both `\n` (literal) and actual newlines work.
    spec = re.sub(r'"[^"]*"', lambda m: m.group(0).replace("\n", "\\n"), spec)

    for raw in re.split(r"[;\n]", spec):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("%%"):
            continue
        if _RE_HEADER.match(line):
            continue

        if m := _RE_SUBGRAPH.match(line):
            current_subgraph = {"id": _norm_id(m[1]), "label": m[2] or m[1], "members": []}
            continue

        if line == "end" and current_subgraph is not None:
            groups[current_subgraph["id"]] = {
                "label": current_subgraph["label"],
                "members": current_subgraph["members"],
            }
            current_subgraph = None
            continue

        if current_subgraph is not None:
            if m := _RE_SHAPE.match(line):
                nid = _norm_id(m[1])
                shapes[nid] = {"label": m[2].replace("\\n", "\n"), "classes": []}
                current_subgraph["members"].append(nid)
                continue
            elif m := _RE_SHAPE_ELLIPSE.match(line):
                nid = _norm_id(m[1])
                shapes[nid] = {"label": m[2].replace("\\n", "\n"), "classes": [], "type": "ellipse"}
                current_subgraph["members"].append(nid)
                continue
            elif m := _RE_SHAPE_DIAMOND.match(line):
                nid = _norm_id(m[1])
                shapes[nid] = {"label": m[2].replace("\\n", "\n"), "classes": [], "type": "diamond"}
                current_subgraph["members"].append(nid)
                continue
            elif re.match(r"^[\w-]+$", line):
                current_subgraph["members"].append(_norm_id(line))
                continue
            # Edges/classDef/class inside subgraph fall through

        if m := _RE_SHAPE.match(line):
            shapes[_norm_id(m[1])] = {"label": m[2].replace("\\n", "\n"), "classes": []}
        elif m := _RE_SHAPE_ELLIPSE.match(line):
            shapes[_norm_id(m[1])] = {"label": m[2].replace("\\n", "\n"), "classes": [], "type": "ellipse"}
        elif m := _RE_SHAPE_DIAMOND.match(line):
            shapes[_norm_id(m[1])] = {"label": m[2].replace("\\n", "\n"), "classes": [], "type": "diamond"}
        elif m := _RE_CLASSDEF.match(line):
            classes[_norm_id(m[1])] = _parse_style_props(m[2])
        elif m := _RE_CLASS.match(line):
            cls = _norm_id(m[2].strip())
            for id_ in [_norm_id(x) for x in m[1].split(",")]:
                if id_ in shapes:
                    shapes[id_]["classes"].append(cls)
        elif m := _RE_EDGE_ARR.match(line):
            src, dst, lbl = _norm_id(m[1]), _norm_id(m[3]), m[2] or ""
            edges.append({
                "id": f"edge-{src}-{dst}" + (f"-{lbl}" if lbl else ""),
                "src": src, "dst": dst, "label": lbl, "directed": True,
                "startArrowhead": None, "endArrowhead": "arrow",
            })
        elif m := _RE_EDGE_BIDIR.match(line):
            src, dst, lbl = _norm_id(m[1]), _norm_id(m[3]), m[2] or ""
            edges.append({
                "id": f"edge-{src}-{dst}-bidir" + (f"-{lbl}" if lbl else ""),
                "src": src, "dst": dst, "label": lbl, "directed": True,
                "startArrowhead": "arrow", "endArrowhead": "arrow",
            })
        elif m := _RE_EDGE_UND.match(line):
            src, dst = _norm_id(m[1]), _norm_id(m[2])
            edges.append({
                "id": f"edge-{src}-{dst}-und", "src": src, "dst": dst,
                "label": "", "directed": False,
                "startArrowhead": None, "endArrowhead": None,
            })
        elif m := _RE_EDGE_DOT.match(line):
            src, dst, lbl = _norm_id(m[1]), _norm_id(m[3]), m[2] or ""
            edges.append({
                "id": f"edge-{src}-{dst}-dot" + (f"-{lbl}" if lbl else ""),
                "src": src, "dst": dst, "label": lbl, "directed": True,
                "startArrowhead": None, "endArrowhead": "dot",
            })
        elif m := _RE_EDGE_BAR.match(line):
            src, dst, lbl = _norm_id(m[1]), _norm_id(m[3]), m[2] or ""
            edges.append({
                "id": f"edge-{src}-{dst}-bar" + (f"-{lbl}" if lbl else ""),
                "src": src, "dst": dst, "label": lbl, "directed": True,
                "startArrowhead": None, "endArrowhead": "bar",
            })
        elif m := _RE_EDGE_DASHED_ARR.match(line):
            src, dst, lbl = _norm_id(m[1]), _norm_id(m[3]), m[2] or ""
            edges.append({
                "id": f"edge-{src}-{dst}-dashed" + (f"-{lbl}" if lbl else ""),
                "src": src, "dst": dst, "label": lbl, "directed": True,
                "startArrowhead": None, "endArrowhead": "arrow", "strokeStyle": "dashed",
            })
        elif m := _RE_EDGE_DASHED_UND.match(line):
            src, dst = _norm_id(m[1]), _norm_id(m[2])
            edges.append({
                "id": f"edge-{src}-{dst}-dashed-und",
                "src": src, "dst": dst, "label": "", "directed": False,
                "startArrowhead": None, "endArrowhead": None, "strokeStyle": "dashed",
            })
        else:
            shapes[line] = {"label": line, "classes": []}

    return {"shapes": shapes, "classes": classes, "edges": edges, "groups": groups}


# ---------------------------------------------------------------------------
# DSL builder
# ---------------------------------------------------------------------------


def _build_dsl(state: dict[str, Any]) -> str:
    """Reconstruct DSL text from accumulated Python state."""
    lines: list[str] = []
    for id_, shape in state["shapes"].items():
        label = shape["label"].replace("\n", "\\n")
        stype = shape.get("type", "rectangle")
        if stype == "ellipse":
            lines.append(f'{id_}(("{label}"))')
        elif stype == "diamond":
            lines.append(f'{id_}{{"{label}"}}')
        else:
            lines.append(f'{id_}["{label}"]')
    for name, props in state["classes"].items():
        prop_str = ",".join(f"{k}:{v}" for k, v in props.items())
        lines.append(f"classDef {name} {prop_str};")
    class_members: dict[str, list[str]] = {}
    for id_, shape in state["shapes"].items():
        for cls in shape.get("classes", []):
            class_members.setdefault(cls, []).append(id_)
    for cls, members in class_members.items():
        lines.append(f'class {",".join(members)} {cls}')
    for edge in state["edges"]:
        src, dst = edge["src"], edge["dst"]
        lbl = f'|{edge["label"]}|' if edge["label"] else ""
        sh = edge.get("startArrowhead")
        eh = edge.get("endArrowhead", "arrow")
        dashed = edge.get("strokeStyle") == "dashed"
        if dashed and not edge.get("directed", True):
            lines.append(f"{src}-.-{dst}")
        elif dashed:
            lines.append(f"{src}-.->{lbl}{dst}")
        elif not edge.get("directed", True):
            lines.append(f"{src}---{dst}")
        elif sh == "arrow" and eh == "arrow":
            lines.append(f"{src}<-->{lbl}{dst}")
        elif eh == "dot":
            lines.append(f"{src} --o{lbl} {dst}")
        elif eh == "bar":
            lines.append(f"{src} --x{lbl} {dst}")
        else:
            lines.append(f"{src}-->{lbl}{dst}")
    for gid, group in state["groups"].items():
        lines.append(f'subgraph {gid} ["{group["label"]}"]')
        for mid in group["members"]:
            lines.append(f"  {mid}")
        lines.append("end")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Auto-layout
# ---------------------------------------------------------------------------


def auto_layout(
    shapes: dict[str, Any],
    edges: list[dict[str, Any]],
    node_w: int = 160,
    node_h: int = 60,
    gap_x: int = 80,
    gap_y: int = 40,
) -> dict[str, tuple[float, float]]:
    """Compute topological layer positions for new shapes.

    Args:
        shapes: Dict of shape id → shape data.
        edges: List of edge dicts with src/dst keys.
        node_w: Node width in pixels.
        node_h: Node height in pixels.
        gap_x: Horizontal gap between layers.
        gap_y: Vertical gap between nodes in a layer.

    Returns:
        Dict of id → (x, y) position tuples.
    """
    ids = list(shapes.keys())
    in_e: dict[str, set[str]] = defaultdict(set)
    out_e: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        if e["src"] in shapes and e["dst"] in shapes:
            out_e[e["src"]].add(e["dst"])
            in_e[e["dst"]].add(e["src"])

    # Track original incoming edges to identify cyclic nodes after Kahn's
    had_incoming: set[str] = {id_ for id_ in ids if in_e[id_]}

    layer: dict[str, int] = {}
    queue: deque[str] = deque(id_ for id_ in ids if not in_e[id_])
    while queue:
        n = queue.popleft()
        for dst in out_e[n]:
            layer[dst] = max(layer.get(dst, 0), layer.get(n, 0) + 1)
            in_e[dst].discard(n)
            if not in_e[dst]:
                queue.append(dst)

    # Source nodes (no incoming) not yet in layer default to 0
    for id_ in ids:
        if id_ not in layer and id_ not in had_incoming:
            layer[id_] = 0

    # Nodes with original incoming edges still not placed are part of cycles
    cyclic = [id_ for id_ in ids if id_ not in layer]
    if cyclic:
        max_layer = max(layer.values(), default=-1) + 1
        cols = max(1, int(len(cyclic) ** 0.5 + 0.5))
        for i, id_ in enumerate(cyclic):
            layer[id_] = max_layer + i // cols

    by_layer: dict[int, list[str]] = defaultdict(list)
    for id_, lyr in sorted(layer.items(), key=lambda x: x[1]):
        by_layer[lyr].append(id_)

    positions: dict[str, tuple[float, float]] = {}
    for lyr, members in by_layer.items():
        x = 500 + lyr * (node_w + gap_x)
        total_h = len(members) * node_h + (len(members) - 1) * gap_y
        y_start = 500 - total_h // 2
        for i, id_ in enumerate(members):
            positions[id_] = (x, y_start + i * (node_h + gap_y))
    return positions


# ---------------------------------------------------------------------------
# Style resolver
# ---------------------------------------------------------------------------

_FONT_FAMILY = {"handwritten": 1, "normal": 2, "code": 3, "serif": 4}
_FONT_SIZE = {"S": 16, "M": 20, "L": 28, "XL": 36}
_ROUNDNESS: dict[str, Any] = {"sharp": None, "round": {"type": 3}}


def _resolve_style(shape: dict[str, Any], classes: dict[str, Any]) -> dict[str, Any]:
    """Merge class style properties into an Excalidraw style dict.

    Args:
        shape: Shape dict with optional 'classes' list.
        classes: Dict of class name → parsed style props.

    Returns:
        Excalidraw-compatible style dict.
    """
    merged: dict[str, str] = {}
    for cls in shape.get("classes", []):
        merged.update(classes.get(cls, {}))
    try:
        stroke_w = int(merged.get("stroke-width", "2").replace("px", ""))
    except ValueError:
        stroke_w = 2
    style: dict[str, Any] = {
        "backgroundColor": merged.get("fill", "#ffffff"),
        "strokeColor": merged.get("stroke", "#1e1e1e"),
        "strokeWidth": stroke_w,
        "color": merged.get("color", "#1e1e1e"),
    }
    if "stroke-style" in merged:
        style["strokeStyle"] = merged["stroke-style"]
    if "roughness" in merged:
        with contextlib.suppress(ValueError):
            style["roughness"] = int(merged["roughness"])
    if "edges" in merged and merged["edges"] in _ROUNDNESS:
        style["roundness"] = _ROUNDNESS[merged["edges"]]
    if "font-family" in merged and merged["font-family"] in _FONT_FAMILY:
        style["fontFamily"] = _FONT_FAMILY[merged["font-family"]]
    if "font-size" in merged:
        fs = merged["font-size"]
        if fs in _FONT_SIZE:
            style["fontSize"] = _FONT_SIZE[fs]
        else:
            with contextlib.suppress(ValueError):
                style["fontSize"] = int(fs)
    if "text-align" in merged:
        style["textAlign"] = merged["text-align"]
    if "vertical-align" in merged:
        style["verticalAlign"] = merged["vertical-align"]
    if "opacity" in merged:
        with contextlib.suppress(ValueError):
            style["opacity"] = int(merged["opacity"])
    return style


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------


def draw(*, input: str) -> str:
    """Add diagram elements from DSL. Additive — never clears existing elements.

    New shapes get auto-layout positions. Existing shapes are untouched.
    Edges are deduplicated by (src, dst, label).

    Shapes:
        id["Label"]                           rectangle (default)
        id(("Label"))                         ellipse
        id{"Label"}                           diamond
        id["Line1
Line2"]                             multiline label (preferred: use a real newline)
        id["Line1\\nLine2"]                   multiline label (also accepted)

    Edges:
        a-->b                                 directed arrow
        a-->|label|b                          directed arrow with label
        a---b                                 undirected, no arrowheads
        a<-->b                                arrows at both ends
        a --o b                               dot/circle arrowhead at end
        a --x b                               bar/cross arrowhead at end
        a-.->b                                dashed directed arrow
        a-.->|label|b                         dashed directed arrow with label
        a-.-b                                 dashed undirected

    Styles:
        classDef name fill:#hex,stroke:#hex,color:#fff;  define a style class
        class id1,id2 className                          assign style to nodes

    Subgraphs:
        subgraph name ["Label"]               bounding rect around members
          id1
          id2
        end

    Headers (ignored):
        flowchart TD
        graph LR

    Args:
        input: DSL string describing shapes, edges, and style classes.

    Returns:
        Summary of elements added, e.g. "+2 shapes, total 5 elements".

    Example:
        excalidraw.draw(input='a["Service A"]\nb["DB"]\na-->b')
    """
    with LogSpan(span="excalidraw.draw") as s:
        global _max_rendered_y
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        parsed = parse_dsl(input)

        # Auto-create nodes referenced in edges but not declared as shapes
        for edge in parsed["edges"]:
            for nid in (edge["src"], edge["dst"]):
                if nid not in parsed["shapes"] and nid not in _dsl_state["shapes"]:
                    parsed["shapes"][nid] = {"label": nid, "classes": []}

        # Compute new shapes (not yet rendered) before mutating state
        new_shapes = {
            id_: sh for id_, sh in parsed["shapes"].items()
            if id_ not in _rendered_ids
        }

        # Build merged state for layout without mutating globals yet
        merged_shapes = {**_dsl_state["shapes"], **parsed["shapes"]}
        merged_classes = {**_dsl_state["classes"], **parsed["classes"]}
        new_edges_to_commit: list[tuple[tuple[str, str, str, str | None, str | None], dict[str, Any]]] = []
        merged_edges = list(_dsl_state["edges"])
        for e in parsed["edges"]:
            key = (e["src"], e["dst"], e["label"], e.get("startArrowhead"), e.get("endArrowhead"))
            if key not in _edge_keys:
                merged_edges.append(e)
                new_edges_to_commit.append((key, e))
        merged_groups = {**_dsl_state["groups"], **parsed["groups"]}

        # Use full merged graph for topology — new shapes get correct layer positions
        positions = auto_layout(merged_shapes, merged_edges)

        shape_payloads = []
        for id_, shape in new_shapes.items():
            x, y = positions[id_]
            style = _resolve_style(shape, merged_classes)
            shape_payloads.append(
                {"id": id_, "label": shape["label"], "x": x, "y": y,
                 "w": 160, "h": 60, "shape": shape.get("type", "rectangle"), "styleProps": style}
            )

        # Render only NEW edges
        edge_payloads = []
        for edge in parsed["edges"]:
            if edge["id"] not in _rendered_ids:
                edge_payloads.append(
                    {"id": edge["id"], "srcId": edge["src"], "dstId": edge["dst"],
                     "label": edge["label"], "startArrowhead": edge.get("startArrowhead"),
                     "endArrowhead": edge.get("endArrowhead", "arrow"),
                     "strokeStyle": edge.get("strokeStyle", "solid")}
                )

        # Redraw ALL subgraphs — bounding boxes must reflect current member positions
        subgraph_payloads = [
            {"id": gid, "label": group["label"], "memberIds": group["members"], "savedBounds": None}
            for gid, group in merged_groups.items()
        ]

        _js_batch_draw(shapes=shape_payloads, edges=edge_payloads, subgraphs=subgraph_payloads)

        # Commit state only after successful JS call
        _dsl_state["shapes"].update(parsed["shapes"])
        _dsl_state["classes"].update(parsed["classes"])
        _dsl_state["groups"].update(parsed["groups"])
        for key, e in new_edges_to_commit:
            _dsl_state["edges"].append(e)
            _edge_keys.add(key)
        _rendered_ids.update(s["id"] for s in shape_payloads)
        _rendered_ids.update(e["id"] for e in edge_payloads)
        if shape_payloads:
            _max_rendered_y = max(_max_rendered_y, max(p["y"] + p["h"] for p in shape_payloads))

        s.add("newShapes", len(new_shapes))
        s.add("totalElements", len(_rendered_ids))
        return f"+{len(new_shapes)} shapes, total {len(_rendered_ids)} elements"


# ---------------------------------------------------------------------------
# Note DSL parser
# ---------------------------------------------------------------------------

_RE_NOTE_BLOCK = re.compile(
    r"^(\w+)\[(\w+):\n(.*?)\]$", re.DOTALL | re.MULTILINE
)

_NOTE_RENDERERS: dict[str, Any] = {}


def _get_note_renderers() -> dict[str, Any]:
    if not _NOTE_RENDERERS:
        from otdev.tools._excalidraw.renderers import (
            render_note,
            render_sequence,
            render_table,
            render_timeline,
            render_tree,
        )
        _NOTE_RENDERERS.update({
            "table": render_table,
            "tree": render_tree,
            "seq": render_sequence,
            "timeline": render_timeline,
            "note": render_note,
        })
    return _NOTE_RENDERERS


def _parse_note_blocks(spec: str) -> list[dict[str, Any]]:
    """Parse id[type:\\n content] blocks from a note DSL string."""
    blocks = []
    for m in _RE_NOTE_BLOCK.finditer(spec):
        blocks.append({"id": m[1], "type": m[2], "content": m[3]})
    return blocks


# ---------------------------------------------------------------------------
# Note tool constants
# ---------------------------------------------------------------------------

_NOTE_CHAR_W = 8.4
_NOTE_LINE_H = 18
_NOTE_FONT_SIZE = 14
_NOTE_PADDING = 20
_NOTE_DEFAULT_BG = "#f5f5dc"


def note(*, input: str, background: str = _NOTE_DEFAULT_BG) -> str:
    """Insert ASCII-rendered text annotations onto the canvas.

    Parses tagged blocks and renders each as a code-font rectangle below
    any existing diagram content.

    Each block uses the syntax:
        id[type:
        content...
        ]

    Block types:

    table — CSV grid, first row is the header:
        t[table:
        Name,Role
        Alice,Dev
        Bob,QA
        ]

    tree — hierarchy with '-' depth prefix (one char = one level):
        tr[tree:
        root/
        -src/
        --main.py
        -tests/
        ]

    seq — sequence diagram, one message per line:
        s[seq:
        Client -> Server: request
        Server -> DB: query
        DB -> Server: rows
        Server -> Client:
        ]

    timeline — Gantt bars, one task per line as 'name,start,duration':
        g[timeline:
        Design,1,4
        Build,3,8
        Test,9,4
        ]

    note — plain word-wrapped paragraph text:
        n[note:
        This is a plain text annotation.
        ]

    Args:
        input: Note DSL string with one or more blocks.
        background: Background color for note boxes (default beige #f5f5dc).

    Returns:
        Summary of notes inserted.

    Example:
        excalidraw.note(input='''
        t[table:
        Name,Role
        Alice,Dev
        Bob,QA
        ]
        ''')
    """
    with LogSpan(span="excalidraw.note") as s:
        global _max_rendered_y
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        blocks = _parse_note_blocks(input)
        if not blocks:
            return "Error: no valid note blocks found (expected id[type:\\ncontent\\n])"

        renderers = _get_note_renderers()

        # Place notes below existing canvas content
        base_y = _max_rendered_y + 100

        shape_payloads = []
        y_cursor = base_y
        for block in blocks:
            renderer = renderers.get(block["type"])
            if renderer is None:
                supported = ", ".join(renderers.keys())
                return f"Error: unknown note type '{block['type']}'. Supported: {supported}"
            rendered = renderer(block["content"])
            if not rendered:
                continue
            if rendered.startswith("Error:"):
                return f"Error in block '{block['id']}': {rendered}"

            lines = rendered.splitlines()
            w = max(len(line) for line in lines) * _NOTE_CHAR_W + _NOTE_PADDING * 2
            h = len(lines) * _NOTE_LINE_H + _NOTE_PADDING * 2
            style = {
                "backgroundColor": background,
                "strokeColor": "#aaaaaa",
                "strokeWidth": 1,
                "fontFamily": 3,
                "fontSize": _NOTE_FONT_SIZE,
                "textAlign": "left",
                "verticalAlign": "top",
                "color": "#1e1e1e",
            }
            shape_payloads.append(
                {"id": block["id"], "label": rendered,
                 "x": 500.0, "y": y_cursor, "w": w, "h": h,
                 "shape": "rectangle", "styleProps": style}
            )
            y_cursor += h + 20

        inserted = len(shape_payloads)
        if shape_payloads:
            _js_batch_draw(shapes=shape_payloads, edges=[], subgraphs=[])
            _rendered_ids.update(s["id"] for s in shape_payloads)
            _max_rendered_y = y_cursor

        s.add("inserted", inserted)
        return f"inserted {inserted} note(s)"


def embed_dsl() -> str:
    """Embed the current DSL as a note element on the canvas.

    Inserts a grey code-font box with id ``__dsl__`` containing the full DSL
    text. Calling again overwrites the previous embed (idempotent). The element
    is excluded from save() snapshots.

    Returns:
        Summary such as "embedded DSL (12 lines)".

    Example:
        excalidraw.embed_dsl()
    """
    with LogSpan(span="excalidraw.embed_dsl") as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        dsl_text = _build_dsl(_dsl_state)
        if not dsl_text.strip():
            return "nothing to embed — canvas is empty"

        lines = dsl_text.splitlines()
        w = max(len(line) for line in lines) * _NOTE_CHAR_W + _NOTE_PADDING * 2
        h = len(lines) * _NOTE_LINE_H + _NOTE_PADDING * 2
        style = {
            "backgroundColor": "#e8e8e8",
            "strokeColor": "#aaaaaa",
            "strokeWidth": 1,
            "fontFamily": 3,
            "fontSize": _NOTE_FONT_SIZE,
            "textAlign": "left",
            "verticalAlign": "top",
            "color": "#555555",
        }
        payload = {
            "id": "dsl", "label": dsl_text,
            "x": 500.0, "y": _max_rendered_y + 100,
            "w": w, "h": h, "shape": "rectangle", "styleProps": style,
        }
        _js_batch_draw(shapes=[payload], edges=[], subgraphs=[])
        _rendered_ids.add("dsl")

        n = len(lines)
        s.add("lines", n)
        return f"embedded DSL ({n} lines)"


def erase(*, ids: list[str]) -> str:
    """Remove individual elements from the canvas and Python state.

    Bound children (shape text, arrow labels) are removed automatically.
    Silently ignores IDs that are not currently rendered.

    Args:
        ids: List of element IDs to remove.

    Returns:
        Summary such as "erased 2 element(s)".

    Example:
        excalidraw.erase(ids=["a", "edge-a-b"])
    """
    with LogSpan(span="excalidraw.erase", ids=ids) as s:
        global _max_rendered_y

        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        id_set = set(ids)

        # Only erase IDs that are actually rendered
        to_erase = [id_ for id_ in ids if id_ in _rendered_ids]
        if not to_erase:
            return "erased 0 element(s)"

        # Find edges that become dangling (src or dst is being erased)
        orphaned_edge_ids = [
            e["id"] for e in _dsl_state["edges"]
            if e["src"] in id_set or e["dst"] in id_set
        ]
        all_to_erase = list(to_erase) + [eid for eid in orphaned_edge_ids if eid not in to_erase]

        ids_json = json.dumps(all_to_erase)
        _browser_evaluate(f"() => window._batch_erase({ids_json})")

        # Update Python state
        for id_ in to_erase:
            _dsl_state["shapes"].pop(id_, None)
            _rendered_ids.discard(id_)
            _rendered_ids.discard(id_ + "-text")
            _rendered_ids.discard(id_ + "-label")

        # Remove edges by their own ID or if their src/dst is being erased
        keys_to_remove = {
            (e["src"], e["dst"], e["label"], e.get("startArrowhead"), e.get("endArrowhead"))
            for e in _dsl_state["edges"]
            if e["id"] in id_set or e["src"] in id_set or e["dst"] in id_set
        }
        _dsl_state["edges"][:] = [
            e for e in _dsl_state["edges"]
            if e["id"] not in id_set
            and e["src"] not in id_set
            and e["dst"] not in id_set
        ]
        _edge_keys.difference_update(keys_to_remove)
        for eid in orphaned_edge_ids:
            _rendered_ids.discard(eid)

        # Only reset _max_rendered_y when all shapes are gone
        if not _dsl_state["shapes"]:
            _max_rendered_y = 0.0

        n = len(to_erase)
        s.add("erased", n)
        return f"erased {n} element(s)"


def save(*, file: str) -> str:
    """Save current diagram to a file in DSL+scene format.

    Reads getSceneElements() for live positions, sizes, and styles,
    capturing any user edits. Bound text and arrow elements are excluded —
    they are re-derived on load.

    Args:
        file: Output file path (relative to project root).

    Returns:
        Summary of elements saved.

    Example:
        excalidraw.save(file="diagrams/arch.wb")
    """
    with LogSpan(span="excalidraw.save", file=file) as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        elements = _browser_evaluate_json(
            "() => Array.from(window.__drawApi.read())"
        )
        if not isinstance(elements, list):
            return f"Error: could not read scene elements: {elements}"

        scene = []
        for el in elements:
            if not isinstance(el, dict):
                continue
            el_id = el.get("id", "")
            if el_id.startswith("__") or el_id == "dsl":
                continue
            if (el_id.endswith("-text") or el_id.endswith("-label")) and el.get("containerId"):
                continue
            if el.get("type") == "arrow" and el.get("startBinding"):
                continue
            scene.append({
                "id": el_id,
                "x": el.get("x", 0),
                "y": el.get("y", 0),
                "w": el.get("width", 160),
                "h": el.get("height", 60),
                "strokeColor": el.get("strokeColor"),
                "backgroundColor": el.get("backgroundColor"),
                "strokeWidth": el.get("strokeWidth"),
                "strokeStyle": el.get("strokeStyle"),
                "roughness": el.get("roughness"),
                "opacity": el.get("opacity"),
            })

        dsl_str = _build_dsl(_dsl_state)
        out_path = resolve_cwd_path(file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            f"[dsl]\n{dsl_str}\n[scene]\n{json.dumps(scene, indent=2)}\n"
        )

        s.add("elementCount", len(scene))
        return f"saved {len(scene)} elements to {file}"


def load(*, file: str) -> str:
    """Restore diagram from a file saved by save().

    Parses the DSL, restores Python state, and renders all elements at
    the saved scene positions and visual properties.

    Args:
        file: Path to a file previously saved by save().

    Returns:
        Summary of elements loaded.

    Example:
        excalidraw.load(file="diagrams/arch.wb")
    """
    with LogSpan(span="excalidraw.load", file=file) as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        src_path = resolve_cwd_path(file)
        if not src_path.exists():
            return f"Error: file not found: {file}"

        raw = src_path.read_text()
        if "[dsl]" not in raw:
            return f"Error: no [dsl] block found in {file}"
        _render_dsl_block(raw)

        n_shapes = len(_dsl_state["shapes"])
        n_edges = len(_dsl_state["edges"])
        s.add("shapes", n_shapes)
        s.add("edges", n_edges)
        return f"loaded {n_shapes} shapes, {n_edges} edges"


def _render_parsed(parsed: dict[str, Any], layout: dict[str, Any]) -> None:
    """Reset state and render a parsed DSL dict to canvas with given layout positions."""
    global _max_rendered_y

    # Reset state in-place — avoids breakage if the module was loaded under two names
    _dsl_state.clear()
    _dsl_state.update({"shapes": {}, "classes": {}, "edges": [], "groups": {}})
    _dsl_state.update(parsed)
    _rendered_ids.clear()
    _edge_keys.clear()
    _max_rendered_y = 0.0
    for e in parsed["edges"]:
        _edge_keys.add((e["src"], e["dst"], e["label"], e.get("startArrowhead"), e.get("endArrowhead")))

    # Clear canvas first
    _browser_evaluate("() => window.__drawApi.clear()")

    shape_payloads = []
    for id_, shape in parsed["shapes"].items():
        pos = layout.get(id_, {})
        style = _resolve_style(shape, parsed["classes"])
        style.update({
            k: pos[k] for k in (
                "strokeColor", "backgroundColor", "strokeWidth",
                "strokeStyle", "roughness", "opacity"
            ) if k in pos
        })
        shape_payloads.append(
            {"id": id_, "label": shape["label"],
             "x": pos.get("x", 0), "y": pos.get("y", 0),
             "w": pos.get("w", 160), "h": pos.get("h", 60),
             "shape": shape.get("type", "rectangle"), "styleProps": style}
        )

    edge_payloads = [
        {"id": e["id"], "srcId": e["src"], "dstId": e["dst"],
         "label": e["label"], "startArrowhead": e.get("startArrowhead"),
         "endArrowhead": e.get("endArrowhead", "arrow")}
        for e in parsed["edges"]
    ]

    subgraph_payloads = []
    for gid, group in parsed["groups"].items():
        pos = layout.get(gid, {})
        subgraph_payloads.append(
            {"id": gid, "label": group["label"], "memberIds": group["members"],
             "savedBounds": pos if pos else None}
        )

    _js_batch_draw(shapes=shape_payloads, edges=edge_payloads, subgraphs=subgraph_payloads)
    _rendered_ids.update(s["id"] for s in shape_payloads)
    _rendered_ids.update(e["id"] for e in edge_payloads)
    if shape_payloads:
        _max_rendered_y = max(s["y"] + s["h"] for s in shape_payloads)


def _render_dsl_block(raw: str) -> None:
    """Parse a [dsl]/[scene] file and render to canvas. Used by load_diag."""
    # New format: [dsl] ... [scene] ...
    dsl_match = re.search(r"\[dsl\]\n(.*?)(?:\[scene\]|$)", raw, re.DOTALL)
    scene_match = re.search(r"\[scene\]\n(.*)", raw, re.DOTALL)
    dsl_lines = dsl_match.group(1).strip() if dsl_match else ""
    layout: dict[str, Any] = {}
    if scene_match:
        try:
            saved = json.loads(scene_match.group(1).strip())
            layout = {e["id"]: e for e in saved if isinstance(e, dict)}
        except (json.JSONDecodeError, KeyError):
            pass

    parsed = parse_dsl(dsl_lines)
    _render_parsed(parsed, layout)




def clear() -> str:
    """Clear all elements from canvas and reset Python DSL state.

    Returns:
        Confirmation message.

    Example:
        excalidraw.clear()
    """
    global _max_rendered_y

    with LogSpan(span="excalidraw.clear") as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        _browser_evaluate("() => window.__drawApi.clear()")
        _dsl_state.clear()
        _dsl_state.update({"shapes": {}, "classes": {}, "edges": [], "groups": {}})
        _rendered_ids.clear()
        _edge_keys.clear()
        _max_rendered_y = 0.0

        return "canvas cleared"


def scroll(*, dx: int = 0, dy: int = 0) -> str:
    """Pan the canvas by (dx, dy) pixels.

    Args:
        dx: Horizontal scroll offset in pixels (positive = right).
        dy: Vertical scroll offset in pixels (positive = down).

    Returns:
        Confirmation message.

    Example:
        excalidraw.scroll(dx=200, dy=0)
    """
    with LogSpan(span="excalidraw.scroll", dx=dx, dy=dy) as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        _browser_evaluate(f"() => window.__drawApi.scroll({dx}, {dy})")
        return f"scrolled dx={dx}, dy={dy}"


def zoom(*, level: float) -> str:
    """Set zoom level. Pass 0 to fit all elements in view.

    Args:
        level: Zoom level (1.0 = 100%, 0.5 = 50%). Pass 0 to fit all.

    Returns:
        Confirmation message.

    Example:
        excalidraw.zoom(level=0.5)
        excalidraw.zoom(level=0)   # fit all
    """
    if level < 0:
        return "Error: zoom level must be >= 0 (use 0 to fit all)"

    with LogSpan(span="excalidraw.zoom", zoom=level) as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        _browser_evaluate(f"() => window.__drawApi.zoom({level})")
        if level == 0:
            return "zoomed to fit all elements"
        return f"zoom set to {level}"


def fit() -> str:
    """Fit all elements in view.

    Returns:
        Confirmation message.

    Example:
        excalidraw.fit()
    """
    return zoom(level=0)


def screenshot(*, file: str | None = None) -> Any:
    """Take a screenshot of the current canvas as PNG.

    Returns image content for inline display. Optionally saves to disk.

    Args:
        file: Optional path to save the screenshot (PNG).

    Returns:
        Screenshot image content, or confirmation message when file is given.

    Example:
        excalidraw.screenshot()
        excalidraw.screenshot(file="diagrams/canvas.png")
    """
    with LogSpan(span="excalidraw.screenshot") as s:
        err = _check_playwright()
        if err:
            s.add("error", err)
            return err

        proxy = get_proxy_manager()
        result = proxy.call_tool_sync(
            _PLAYWRIGHT_SERVER,
            "browser_take_screenshot",
            {"raw": False, "format": "png"},
        )

        if file is None:
            return result

        import shutil

        result_str = str(result)
        out_path = resolve_cwd_path(file)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Playwright writes the image to a temp file — extract that path and copy it
        path_match = re.search(r"\[.*?\]\(([^)]+)\)", result_str)
        if path_match:
            src_path = path_match.group(1)
            try:
                shutil.copy(src_path, str(out_path))
                return f"screenshot saved to {file}"
            except Exception as exc:
                return f"Error: could not save screenshot from {src_path} — {exc}"

        # Fallback: base64-encoded content
        import contextlib

        img_bytes: bytes | None = None
        if "base64," in result_str:
            with contextlib.suppress(Exception):
                img_bytes = base64.b64decode(result_str.split("base64,", 1)[1].strip())
        if img_bytes is None:
            with contextlib.suppress(Exception):
                img_bytes = base64.b64decode(result_str.strip())
        if img_bytes:
            out_path.write_bytes(img_bytes)
            return f"screenshot saved to {file}"

        return f"Error: could not save screenshot to {file} — unexpected result format"


def hard_reset() -> str:
    """Reset Python DSL state unconditionally; attempt canvas clear if browser is available.

    Use this to recover from a broken Playwright/Chrome state where normal
    tools fail. Python state is always reset. Browser clear is attempted
    opportunistically — if Playwright is down it is silently skipped.

    Returns:
        "hard reset: state cleared, canvas cleared" or
        "hard reset: state cleared (browser unavailable)"

    Example:
        excalidraw.hard_reset()
    """
    global _max_rendered_y

    _dsl_state.clear()
    _dsl_state.update({"shapes": {}, "classes": {}, "edges": [], "groups": {}})
    _rendered_ids.clear()
    _edge_keys.clear()
    _max_rendered_y = 0.0

    browser_ok = False
    if _check_playwright() is None:
        try:
            _browser_evaluate("() => window.__drawApi.clear()")
            browser_ok = True
        except Exception:
            pass

    if browser_ok:
        return "hard reset: state cleared, canvas cleared"
    return "hard reset: state cleared (browser unavailable)"


def open() -> str:
    """Open excalidraw.com and start with a clean canvas.

    Navigates to excalidraw.com and initialises the drawing API if not
    already ready, then clears the canvas and resets all Python state.
    To restore previous content after opening, call wb.load().

    Returns:
        "whiteboard ready" on success, or an error string.

    Example:
        excalidraw.open()
    """
    global _max_rendered_y
    with LogSpan(span="excalidraw.open") as s:
        err = _ensure_ready()
        # Untracked content warning is non-fatal — open() always starts fresh
        if err and not err.startswith("Warning:"):
            s.add("error", err)
            return err
        # Always start fresh: reset Python state and clear canvas
        import contextlib

        _dsl_state.clear()
        _dsl_state.update({"shapes": {}, "classes": {}, "edges": [], "groups": {}})
        _rendered_ids.clear()
        _edge_keys.clear()
        _max_rendered_y = 0.0
        with contextlib.suppress(Exception):
            _browser_evaluate("() => window.__drawApi.clear()")
        return "whiteboard ready"


def close() -> str:
    """Close the excalidraw tab and reset all Python state.

    Resets DSL state unconditionally, then closes the browser tab so it is
    not left open. On the next wb tool call a fresh excalidraw.com tab will
    be opened automatically.

    If Playwright is unavailable, only the Python state is reset.

    Returns:
        Confirmation message.

    Example:
        excalidraw.close()
    """
    global _max_rendered_y

    _dsl_state.clear()
    _dsl_state.update({"shapes": {}, "classes": {}, "edges": [], "groups": {}})
    _rendered_ids.clear()
    _edge_keys.clear()
    _max_rendered_y = 0.0

    if _check_playwright() is not None:
        return "whiteboard closed (browser unavailable)"

    import contextlib

    proxy = get_proxy_manager()
    try:
        proxy.call_tool_sync(_PLAYWRIGHT_SERVER, "browser_close", {})
    except Exception:
        # Fall back to navigating away if browser_close is unsupported
        with contextlib.suppress(Exception):
            proxy.call_tool_sync(
                _PLAYWRIGHT_SERVER, "browser_navigate", {"url": "about:blank"}
            )

    return "whiteboard closed"
