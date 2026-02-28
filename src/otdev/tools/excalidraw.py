"""Excalidraw tool pack — Playwright-driven live diagram manipulation.

Opens excalidraw.com via Playwright and exposes tools to draw, save, load,
clear, scroll, and zoom diagrams using a Mermaid-compatible DSL.

Requires the Playwright MCP server to be enabled:
    ot.server(enable='playwright')
"""

from __future__ import annotations

# Pack declaration MUST be before other imports
pack = "whiteboard"

__all__ = [
    "clear",
    "close",
    "draw",
    "embed_dsl",
    "erase",
    "fit",
    "hard_reset",
    "help",
    "load",
    "note",
    "open",
    "save",
    "screenshot",
    "scroll",
    "share",
    "style",
    "sync",
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

_dsl_state: dict[str, Any] = {"shapes": {}, "edges": [], "groups": {}}
_edge_keys: set[tuple[str, str, str, str | None, str | None]] = set()
_rendered_ids: set[str] = set()
_placed_positions: dict[str, tuple[float, float]] = {}
_max_rendered_y: float = 0.0


def _reset_state() -> None:
    """Reset all module-level DSL and render state to empty."""
    global _max_rendered_y
    _dsl_state.clear()
    _dsl_state.update({"shapes": {}, "edges": [], "groups": {}})
    _rendered_ids.clear()
    _edge_keys.clear()
    _placed_positions.clear()
    _max_rendered_y = 0.0


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


def _js_patch_elements(patches: list[dict[str, Any]]) -> None:
    """Patch existing elements (label and/or style) without changing position."""
    p_json = json.dumps(patches)
    _browser_evaluate(f"() => window._patch_elements({p_json})")


def _js_style_elements(ids: list[str], style_props: dict[str, Any]) -> None:
    """Apply style properties to elements by ID."""
    ids_json = json.dumps(ids)
    props_json = json.dumps(style_props)
    _browser_evaluate(f"() => window._style_elements({ids_json}, {props_json})")


def _shape_payload(
    id_: str,
    shape: dict[str, Any],
    x: float,
    y: float,
    w: float,
    h: float,
    style: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a shape payload dict for _js_batch_draw."""
    return {
        "id": id_, "label": shape["label"],
        "x": x, "y": y, "w": w, "h": h,
        "shape": "rectangle", "styleProps": style or {},
    }


# ---------------------------------------------------------------------------
# Browser lifecycle
# ---------------------------------------------------------------------------


def _process_pending_downloads() -> list[str]:
    """Retrieve captured downloads from the browser and save to disk.

    Excalidraw's 'Save to file' is intercepted by the JS download handler in
    ops.js. This function drains the queue, writes each file to the current
    working directory, and returns a list of saved paths.
    """
    try:
        queue = _browser_evaluate_json(
            "() => { const q = window.__downloadQueue || []; "
            "window.__downloadQueue = []; return q; }"
        )
        if not isinstance(queue, list) or not queue:
            return []
        saved = []
        for item in queue:
            name = item.get("name", "download.excalidraw") if isinstance(item, dict) else "download.excalidraw"
            data = item.get("data", "") if isinstance(item, dict) else ""
            if not data:
                continue
            out_path = resolve_cwd_path(name)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(data, encoding="utf-8")
            saved.append(str(out_path))
        return saved
    except Exception:
        return []


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

    # Always re-inject ops.js so in-place code changes take effect without a page reload
    _browser_evaluate(_load_js("ops.js"))

    # Save any files the user downloaded via the Excalidraw UI
    _process_pending_downloads()

    return None


def _rerender_from_state() -> None:
    """Re-render all content from _dsl_state after a page loss.

    Visual positions revert to auto-layout. To preserve positions,
    call save() before any risky operations.
    """
    global _max_rendered_y
    _rendered_ids.clear()
    positions = auto_layout(_dsl_state["shapes"], _dsl_state["edges"])

    shape_payloads = []
    for id_, shape in _dsl_state["shapes"].items():
        x, y = positions[id_]
        shape_payloads.append(_shape_payload(id_, shape, x, y, 160, 60))

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
    for p in shape_payloads:
        _placed_positions[p["id"]] = (p["x"], p["y"])
    if shape_payloads:
        _max_rendered_y = max(s["y"] + s["h"] for s in shape_payloads)


# ---------------------------------------------------------------------------
# DSL parser
# ---------------------------------------------------------------------------

# Edge operator pattern used in ID pre-normalisation (longest first to avoid prefix clashes)
_EDGE_OP_RE = re.compile(r'(<-->|-\.->|-\.-|--[ox]|-->|---)')

_RE_HEADER   = re.compile(r"^(?:flowchart|graph)\s+\w+$")
_RE_SUBGRAPH = re.compile(r'^subgraph\s+([\w-]+)(?:\s+\[\s*"([^"]+)"\s*\])?$')

# Rectangle shape — trailing content after ] is parsed as inline style props
_RE_SHAPE_RECT    = re.compile(r'^([\w-]+)\s*\[\s*"?([^"\]]*)"?\s*\]\s*(.*)$')
# Hints for deprecated ellipse/diamond syntax (to provide a clear error)
_RE_SHAPE_ELLIPSE = re.compile(r'^[\w-]+\s*\(\s*\(')
_RE_SHAPE_DIAMOND = re.compile(r'^[\w-]+\s*\{')
# Bare id + inline style props:  a bc:green,sw:2
_RE_BARE_STYLE    = re.compile(r'^([\w-]+)\s+([a-z]+:.+)$')

# (pattern, id_suffix, has_label, start_arrowhead, end_arrowhead, directed, stroke_style)
_EDGE_PATTERNS: list[tuple[re.Pattern[str], str, bool, str | None, str | None, bool, str | None]] = [
    (re.compile(r"^([\w-]+)\s*<-->\s*(?:\|([^|]*)\|)?\s*([\w-]+)$"),    "-bidir",      True,  "arrow", "arrow", True,  None),
    (re.compile(r"^([\w-]+)\s*-\.->\s*(?:\|([^|]*)\|)?\s*([\w-]+)$"),   "-dashed",     True,  None,    "arrow", True,  "dashed"),
    (re.compile(r"^([\w-]+)\s*-\.-\s*([\w-]+)$"),                         "-dashed-und", False, None,    None,    False, "dashed"),
    (re.compile(r"^([\w-]+)\s*--o\s*(?:\|([^|]*)\|)?\s*([\w-]+)$"),     "-dot",        True,  None,    "dot",   True,  None),
    (re.compile(r"^([\w-]+)\s*--x\s*(?:\|([^|]*)\|)?\s*([\w-]+)$"),     "-bar",        True,  None,    "bar",   True,  None),
    (re.compile(r"^([\w-]+)\s*-->\s*(?:\|([^|]*)\|)?\s*([\w-]+)$"),     "",            True,  None,    "arrow", True,  None),
    (re.compile(r"^([\w-]+)\s*---\s*([\w-]+)$"),                          "-und",        False, None,    None,    False, None),
]


def _norm_id(raw: str) -> str:
    """Normalise a node ID: strip non-word chars (except underscore), lowercase."""
    return re.sub(r"[^\w]", "", raw).lower()


def _prenorm_line(line: str) -> str:
    """Pre-normalise ID tokens in one DSL line before main parsing.

    Handles IDs with spaces, hyphens, or other non-word chars by applying
    _norm_id to every ID position: before ``[``, before/after edge operators,
    after the ``subgraph`` keyword, and bare-ID tokens.

    Label content inside ``["..."]`` and ``|...|`` is never modified.
    """
    if not line:
        return line
    # Preserve comment and directive lines unchanged
    if line.startswith("#") or line.startswith("%%"):
        return line
    if re.match(r"^(?:flowchart|graph|classDef|class|end)(\s|$)", line):
        return line

    # subgraph <id> [optional "Label"]
    if line.startswith("subgraph "):
        m = re.match(r"^(subgraph\s+)(.*?)(\s*(?:\[.*)?$)", line)
        if m:
            raw_id = m[2].strip()
            return "subgraph " + _norm_id(raw_id) + (" " + m[3].strip() if m[3].strip() else "")
        return line

    # Edge line — find operator and normalise src and dst independently
    if m := _EDGE_OP_RE.search(line):
        op_start, op_end = m.start(), m.end()
        op = m.group()
        src_raw = line[:op_start].strip()
        rest = line[op_end:]
        # Labeled edge: -->|label|dst
        if lm := re.match(r"^\s*\|([^|]*)\|\s*(.*)", rest):
            dst_raw = lm[2].strip()
            return _norm_id(src_raw) + op + "|" + lm[1] + "|" + _norm_id(dst_raw)
        return _norm_id(src_raw) + op + _norm_id(rest.strip())

    # Shape declaration: id["Label"] [optional inline style]
    bracket = line.find("[")
    if bracket > 0:
        return _norm_id(line[:bracket]) + line[bracket:]

    # Bare id + inline style props (id may be multi-word)
    if m := re.match(r"^([\w\s\-+]+?)\s+([a-z]+:.+)$", line):
        return _norm_id(m[1].strip()) + " " + m[2]

    # Bare id token (subgraph member or unknown) — normalise if non-canonical chars present
    if re.search(r"[\s\-+]", line) and re.match(r"^[\w\s\-+]+$", line):
        return _norm_id(line)

    return line


def _find_free_y(x: float, y: float) -> float:
    """Return y (or a shifted y) that does not overlap any already-placed node.

    Checks ``_placed_positions`` for nodes in the same x-column. If the
    proposed y conflicts with any existing node, places the new node below all
    nodes in that column instead.
    """
    node_w, node_h, gap_y = 160, 60, 40
    col_ys = [py for px, py in _placed_positions.values() if abs(px - x) < node_w]
    if not col_ys:
        return y
    for py in col_ys:
        if abs(py - y) < node_h + gap_y:
            return max(col_ys) + node_h + gap_y
    return y


# ---------------------------------------------------------------------------
# Style property helpers (shared by whiteboard.draw, whiteboard.style, whiteboard.erase docstrings)
# ---------------------------------------------------------------------------

_STYLE_SHORTHANDS: dict[str, str] = {
    "bc":    "backgroundColor",
    "sc":    "strokeColor",
    "sw":    "strokeWidth",
    "ss":    "strokeStyle",
    "r":     "roughness",
    "o":     "opacity",
    "f":     "fontFamily",
    "fs":    "fontSize",
    "ta":    "textAlign",
    "va":    "verticalAlign",
    "shape": "shape",   # special — triggers delete+recreate in JS
    "x":     "x",
    "y":     "y",
    "w":     "width",
    "h":     "height",
}

_NAMED_COLORS: dict[str, str] = {
    "green":  "#bbf7d0",
    "blue":   "#bfdbfe",
    "red":    "#fecaca",
    "purple": "#e9d5ff",
    "yellow": "#fef08a",
    "orange": "#fed7aa",
    "pink":   "#fce7f3",
    "gray":   "#e5e7eb",
    "grey":   "#e5e7eb",
    "white":  "#ffffff",
    "black":  "#000000",
}

_FONT_FAMILY_MAP: dict[str, int] = {"hand": 1, "normal": 2, "mono": 3, "excalidraw": 5}
_STROKE_STYLE_VALUES = {"solid", "dashed", "dotted"}
_TEXT_ALIGN_VALUES   = {"left", "center", "right"}
_VERT_ALIGN_VALUES   = {"top", "middle", "bottom"}
_SHAPE_MAP: dict[str, str] = {"r": "rectangle", "d": "diamond", "c": "ellipse"}


def _parse_style_props(s: str) -> dict[str, Any]:
    """Parse a comma-separated ``key:value`` style string, expanding shorthands.

    Shorthand keys are expanded to Excalidraw property names. Named colours
    (``green``, ``blue``, ``red``, ``purple``, ``yellow``, ``white``,
    ``black``, ``orange``, ``pink``, ``gray``) are resolved to hex values.
    Numeric props (``sw``, ``r``, ``o``, ``f``, ``fs``, ``x``, ``y``,
    ``w``, ``h``) are cast to int/float automatically.

    Args:
        s: Style string like ``"bc:#bbf7d0,sc:#16a34a,sw:2"``.

    Returns:
        Dict with Excalidraw property names as keys.
    """
    props: dict[str, Any] = {}
    for part in s.split(","):
        if ":" not in part:
            continue
        k, v = part.strip().split(":", 1)
        k, v = k.strip(), v.strip()
        if not k or not v:
            continue
        v_lower = v.lower()
        # Expand shorthand key
        prop = _STYLE_SHORTHANDS.get(k, k)
        # Resolve named colour (case-insensitive; hex pass-through unchanged)
        if prop in ("backgroundColor", "strokeColor") and v_lower in _NAMED_COLORS:
            v = _NAMED_COLORS[v_lower]
        # Map font-family shorthand (case-insensitive)
        if prop == "fontFamily" and v_lower in _FONT_FAMILY_MAP:
            props[prop] = _FONT_FAMILY_MAP[v_lower]
            continue
        # Map shape shorthand (r/d/c → excalidraw type names, case-insensitive)
        if prop == "shape" and v_lower in _SHAPE_MAP:
            props[prop] = _SHAPE_MAP[v_lower]
            continue
        # Numeric coercion
        if prop in ("strokeWidth", "roughness", "opacity", "fontSize", "x", "y", "width", "height"):
            try:
                props[prop] = float(v) if "." in v else int(v)
                continue
            except ValueError:
                pass
        # Enum string props: normalise to lowercase for strokeStyle, textAlign, verticalAlign
        if prop in ("strokeStyle", "textAlign", "verticalAlign"):
            props[prop] = v_lower
            continue
        props[prop] = v
    return props


def _try_shape(
    line: str,
    shapes: dict[str, Any],
    subgraph: dict[str, Any] | None,
    inline_styles: dict[str, Any] | None = None,
) -> bool:
    """Try to match line as a shape declaration. Mutates shapes. Returns True on match.

    Raises ValueError for deprecated ellipse ((...)) and diamond {...} syntax.
    Trailing style props after the closing ] are captured into inline_styles.
    """
    if _RE_SHAPE_ELLIPSE.match(line):
        nid = _norm_id(line.split("(")[0].strip())
        raise ValueError(
            f"Ellipse syntax '((...))' is not supported. "
            f"Draw a rectangle and use whiteboard.style(ids=['{nid}'], style='shape:c') to change shape."
        )
    if _RE_SHAPE_DIAMOND.match(line):
        nid = _norm_id(line.split("{")[0].strip())
        raise ValueError(
            f"Diamond syntax '{{...}}' is not supported. "
            f"Draw a rectangle and use whiteboard.style(ids=['{nid}'], style='shape:d') to change shape."
        )
    if m := _RE_SHAPE_RECT.match(line):
        nid = _norm_id(m[1])
        shape: dict[str, Any] = {"label": m[2].replace("\\n", "\n"), "classes": []}
        shapes[nid] = shape
        if subgraph is not None:
            subgraph["members"].append(nid)
        trailing = m[3].strip()
        if inline_styles is not None and trailing:
            inline_styles[nid] = _parse_style_props(trailing)
        return True
    return False


def _try_edge(line: str, edges: list[dict[str, Any]]) -> bool:
    """Try to match line as an edge. Appends to edges. Returns True on match."""
    for pat, id_sfx, has_label, s_head, e_head, directed, stroke in _EDGE_PATTERNS:
        if m := pat.match(line):
            if has_label:
                src, lbl, dst = _norm_id(m[1]), m[2] or "", _norm_id(m[3])
            else:
                src, dst, lbl = _norm_id(m[1]), _norm_id(m[2]), ""
            edge_id = f"edge-{src}-{dst}{id_sfx}" + (f"-{lbl}" if lbl else "")
            edge: dict[str, Any] = {
                "id": edge_id, "src": src, "dst": dst, "label": lbl,
                "directed": directed,
                "startArrowhead": s_head, "endArrowhead": e_head,
            }
            if stroke:
                edge["strokeStyle"] = stroke
            edges.append(edge)
            return True
    return False


def _expand_edge_chains(raw: str) -> list[str]:
    """Expand chained edge syntax into individual edge strings.

    ``"A --> B --> C"`` → ``["A --> B", "B --> C"]``

    Returns ``[raw]`` unchanged if there are fewer than two edge operators or
    if any token between operators contains a label delimiter (``|``).
    """
    ops = list(_EDGE_OP_RE.finditer(raw))
    if len(ops) < 2:
        return [raw]
    tokens: list[str] = []
    op_strs: list[str] = []
    prev_end = 0
    for m in ops:
        tokens.append(raw[prev_end : m.start()].strip())
        op_strs.append(m.group())
        prev_end = m.end()
    tokens.append(raw[prev_end:].strip())
    # Don't expand if labels are involved — let the existing parser handle it
    if any("|" in t for t in tokens):
        return [raw]
    return [f"{tokens[i]}{op_strs[i]}{tokens[i + 1]}" for i in range(len(op_strs))]


def parse_dsl(spec: str) -> dict[str, Any]:
    """Parse a Mermaid-compatible DSL string into a structured dict.

    Supported syntax:
        id["Label"]             rectangle (the only supported shape)
        id["Label"] bc:green    rectangle with inline style props
        id bc:green             style-only update (label unchanged)
        id1-->id2               directed edge
        id1-->|label|id2        labeled edge
        id1---id2               undirected edge
        id1<-->id2              bidirectional edge
        id1--o id2              dot arrowhead
        id1--x id2              bar arrowhead
        id1-.->id2              dashed directed edge
        id1-.-id2               dashed undirected edge
        subgraph name ["Label"] bounding group
          id1
        end

    Note: classDef/class and ellipse/diamond syntax are not supported.
    Use ``whiteboard.style`` to change colours and shapes after drawing.

    Args:
        spec: DSL string. Statements may be separated by newlines or semicolons.

    Returns:
        Dict with keys: ``shapes``, ``edges``, ``groups``, ``inline_styles``.
        ``inline_styles`` maps node IDs to parsed style prop dicts.
        Shape dicts have a ``label`` key (``None`` means "keep existing label").
    """
    shapes: dict[str, Any] = {}
    edges: list[dict[str, Any]] = []
    groups: dict[str, Any] = {}
    inline_styles: dict[str, Any] = {}
    current_subgraph: dict[str, Any] | None = None

    # Normalize real newlines inside quoted labels to the \n escape so they
    # survive line-splitting. Both `\n` (literal) and actual newlines work.
    spec = re.sub(r'"[^"]*"', lambda m: m.group(0).replace("\n", "\\n"), spec)

    raw_lines: list[str] = []
    for raw in re.split(r"[;\n]", spec):
        raw_lines.extend(_expand_edge_chains(raw.strip()))

    for raw in raw_lines:
        line = _prenorm_line(raw.strip())
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

        # Shape declaration (handles subgraph membership in one pass)
        if _try_shape(line, shapes, current_subgraph, inline_styles):
            continue

        # classDef / class — no longer supported
        if re.match(r"^(?:classDef|class)\s", line):
            raise ValueError(
                "classDef/class syntax is not supported. "
                "Use whiteboard.style() to apply colours and shapes after drawing."
            )

        # Bare node ID inside a subgraph — membership only
        if current_subgraph is not None and re.match(r"^[\w-]+$", line):
            current_subgraph["members"].append(_norm_id(line))
            continue

        # Edges
        if _try_edge(line, edges):
            continue

        # Bare id + inline style props (no bracket declaration):  a bc:green,sw:2
        if m := _RE_BARE_STYLE.match(line):
            nid = _norm_id(m[1])
            inline_styles[nid] = _parse_style_props(m[2])
            # Mark as style-only update (label=None means "keep existing label")
            if nid not in shapes:
                shapes[nid] = {"label": None, "classes": []}
            continue

        # Bare node ID fallback — create shape with label = node ID
        shapes[line] = {"label": line, "classes": []}

    return {"shapes": shapes, "edges": edges, "groups": groups, "inline_styles": inline_styles}


# ---------------------------------------------------------------------------
# DSL builder
# ---------------------------------------------------------------------------


def _build_dsl(state: dict[str, Any]) -> str:
    """Reconstruct DSL text from accumulated Python state.

    Emits shapes as rectangles only. Styling is not encoded in the DSL —
    it lives in the Excalidraw scene elements.
    """
    lines: list[str] = []
    for id_, shape in state["shapes"].items():
        label = shape["label"]
        if label is None:
            label = id_
        lines.append(f'{id_}["{label.replace(chr(10), "\\n")}"]')
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
# DSL canvas element helpers (issue #3)
# ---------------------------------------------------------------------------


def _read_dsl_from_canvas() -> str:
    """Read the __otDSL text element from the canvas. Returns empty string if absent."""
    result = _browser_evaluate_json(
        "() => {"
        "  const el = Array.from(window.__drawApi.read()).find(e => e.id === '__otDSL');"
        "  return el ? el.text : '';"
        "}"
    )
    return result if isinstance(result, str) else ""


def _write_dsl_to_canvas(dsl_str: str) -> None:
    """Upsert the __otDSL text element on the canvas with current DSL content."""
    _browser_evaluate(f"() => window._upsert_dsl_element({json.dumps(dsl_str)})")


def _parse_dsl_to_state(dsl_str: str) -> None:
    """Parse DSL string and update _dsl_state and _edge_keys."""
    parsed = parse_dsl(dsl_str)
    _reset_state()
    _dsl_state.update({
        "shapes": parsed["shapes"],
        "edges":  parsed["edges"],
        "groups": parsed["groups"],
    })
    for e in parsed["edges"]:
        _edge_keys.add((e["src"], e["dst"], e["label"], e.get("startArrowhead"), e.get("endArrowhead")))


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------


def draw(*, input: str) -> str:
    """Add or update diagram elements from DSL. Always additive — never clears.

    **New nodes** get auto-layout positions. **Existing nodes** are upserted:
    only the properties explicitly passed are changed; position, size, and
    other styles on the live canvas are preserved.

    Semicolons are preferred as statement separators for agent calls (compact,
    no multi-line strings needed). Newlines are also accepted.

    Shapes:
        id["Label"]                           rectangle (only supported shape)
        id["Label"] bc:green,sw:2            rectangle with inline style props
        id bc:green                           style-only update (label unchanged)

    Inline style shorthands (comma-separated ``key:value``):
        bc  backgroundColor    sc  strokeColor     sw  strokeWidth
        ss  strokeStyle        r   roughness        o   opacity
        f   fontFamily         fs  fontSize         ta  textAlign
        va  verticalAlign      shape  shape type     x/y  position
        w/h width/height

    Named colours: green, blue, red, purple, yellow, orange, pink, gray, white, black

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

    Subgraphs:
        subgraph name ["Label"]               bounding rect around members
          id1
          id2
        end

    Headers (ignored):
        flowchart TD
        graph LR

    Args:
        input: DSL string. Semicolons or newlines separate statements.

    Returns:
        Summary like "+2 shapes, +1 edge [edge-a-b]".

    Example:
        whiteboard.draw(input='a["Service A"];b["DB"];a-->b')
    """
    with LogSpan(span="excalidraw.draw") as s:
        global _max_rendered_y
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        parsed = parse_dsl(input)
        inline_styles = parsed.get("inline_styles", {})

        # Auto-create nodes referenced in edges but not declared as shapes
        for edge in parsed["edges"]:
            for nid in (edge["src"], edge["dst"]):
                if nid not in parsed["shapes"] and nid not in _dsl_state["shapes"]:
                    parsed["shapes"][nid] = {"label": nid, "classes": []}

        # Separate new shapes from existing shapes
        new_shapes = {
            id_: sh for id_, sh in parsed["shapes"].items()
            if id_ not in _dsl_state["shapes"]
        }
        existing_shape_updates = {
            id_: sh for id_, sh in parsed["shapes"].items()
            if id_ in _dsl_state["shapes"]
        }
        new_groups = {gid for gid in parsed["groups"] if gid not in _dsl_state["groups"]}

        # Build merged state for layout (new shapes get correct layer positions)
        merged_shapes = {**_dsl_state["shapes"], **parsed["shapes"]}
        merged_edges = list(_dsl_state["edges"])
        new_edges_to_commit: list[tuple[tuple[str, str, str, str | None, str | None], dict[str, Any]]] = []
        for e in parsed["edges"]:
            key = (e["src"], e["dst"], e["label"], e.get("startArrowhead"), e.get("endArrowhead"))
            if key not in _edge_keys:
                merged_edges.append(e)
                new_edges_to_commit.append((key, e))
        merged_groups = {**_dsl_state["groups"], **parsed["groups"]}

        positions = auto_layout(merged_shapes, merged_edges)

        # Build payloads for new shapes, adjusting positions to avoid overlap
        shape_payloads = []
        for id_, shape in new_shapes.items():
            x, y = positions[id_]
            y = _find_free_y(x, y)
            # Apply inline styles for new shapes
            style = dict(inline_styles.get(id_, {}))
            shape_payloads.append(_shape_payload(id_, shape, x, y, 160, 60, style))

        # Build patch payloads for existing shapes that changed
        patch_payloads = []
        for id_, shape in existing_shape_updates.items():
            patch: dict[str, Any] = {}
            # Update label only if explicitly specified (not None)
            if shape.get("label") is not None:
                existing_label = _dsl_state["shapes"][id_].get("label", "")
                if shape["label"] != existing_label:
                    patch["text"] = shape["label"]
            # Apply inline styles
            patch.update(inline_styles.get(id_, {}))
            if patch:
                patch["id"] = id_
                patch_payloads.append(patch)

        # Apply inline style-only updates for nodes not in parsed["shapes"]
        for id_, style in inline_styles.items():
            if id_ not in parsed["shapes"] and id_ in _dsl_state["shapes"]:
                patch_payloads.append({"id": id_, **style})

        # Render only NEW edges
        edge_payloads = []
        for _key, e in new_edges_to_commit:
            edge_payloads.append(
                {"id": e["id"], "srcId": e["src"], "dstId": e["dst"],
                 "label": e["label"], "startArrowhead": e.get("startArrowhead"),
                 "endArrowhead": e.get("endArrowhead", "arrow"),
                 "strokeStyle": e.get("strokeStyle", "solid")}
            )

        # Redraw ALL subgraphs — bounding boxes must reflect current member positions
        subgraph_payloads = [
            {"id": gid, "label": group["label"], "memberIds": group["members"], "savedBounds": None}
            for gid, group in merged_groups.items()
        ]

        # Single batch draw for new shapes + edges
        _js_batch_draw(shapes=shape_payloads, edges=edge_payloads, subgraphs=subgraph_payloads)

        # Patch existing shapes (separate call to preserve their live positions)
        if patch_payloads:
            _js_patch_elements(patch_payloads)

        # Commit state only after successful JS calls
        for id_, shape in parsed["shapes"].items():
            if shape.get("label") is not None:
                _dsl_state["shapes"][id_] = shape
            elif id_ not in _dsl_state["shapes"]:
                _dsl_state["shapes"][id_] = {"label": id_, "classes": []}
        _dsl_state["groups"].update(parsed["groups"])
        for key, e in new_edges_to_commit:
            _dsl_state["edges"].append(e)
            _edge_keys.add(key)
        _rendered_ids.update(s["id"] for s in shape_payloads)
        _rendered_ids.update(e["id"] for e in edge_payloads)
        for p in shape_payloads:
            _placed_positions[p["id"]] = (p["x"], p["y"])
        if shape_payloads:
            _max_rendered_y = max(_max_rendered_y, max(p["y"] + p["h"] for p in shape_payloads))

        new_edge_ids = [e["id"] for _, e in new_edges_to_commit]
        edge_msg = f", +{len(new_edge_ids)} edge(s): {', '.join(new_edge_ids)}" if new_edge_ids else ""
        updated_msg = f", {len(patch_payloads)} updated" if patch_payloads else ""
        group_msg = f", +{len(new_groups)} group(s)" if new_groups else ""

        s.add("newShapes", len(new_shapes))
        s.add("totalElements", len(_rendered_ids))
        return f"+{len(new_shapes)} shapes{updated_msg}{edge_msg}{group_msg}"


# ---------------------------------------------------------------------------
# Note DSL parser
# ---------------------------------------------------------------------------

_RE_NOTE_BLOCK = re.compile(
    r"^(\w+)\[(\w+):[ \t]*\n(.*?)\]$", re.DOTALL | re.MULTILINE
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
    for m in _RE_NOTE_BLOCK.finditer(spec.replace("\r\n", "\n")):
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
        whiteboard.note(input='''
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

    Inserts a grey code-font box with id ``dsl`` containing the full DSL
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

    **Edge ID format:** ``edge-{src}-{dst}[-{type-suffix}][-{label}]``

    Type suffixes: ``-bidir`` (↔), ``-und`` (undirected ---),
    ``-dashed`` (-.->), ``-dashed-und`` (-.-), ``-dot`` (--o), ``-bar`` (--x).

    Examples::

        a-->b               →  "edge-a-b"
        a-->|send|b         →  "edge-a-b-send"
        a<-->b              →  "edge-a-b-bidir"
        a---b               →  "edge-a-b-und"
        a-.->b              →  "edge-a-b-dashed"
        a-.->|Metrics|b     →  "edge-a-b-dashed-Metrics"

    Use ``whiteboard.draw`` output to see the generated edge IDs after drawing.

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
            _placed_positions.pop(id_, None)

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
        dangling = len(orphaned_edge_ids)
        s.add("erased", n)
        s.add("danglingEdges", dangling)
        if dangling:
            return f"erased {n} element(s), {dangling} dangling edge(s) removed"
        return f"erased {n} element(s)"


def save(*, file: str) -> str:
    """Save current diagram to a native ``.excalidraw`` JSON file.

    Writes the full Excalidraw scene (including user-added elements and
    live positions) plus a ``__otDSL`` text element that stores the
    logical DSL for future ``whiteboard.load`` / ``whiteboard.sync`` calls.

    The saved file can be opened directly in excalidraw.com.

    Args:
        file: Output file path (relative to project root). Conventionally
              uses the ``.excalidraw`` extension.

    Returns:
        Summary of elements saved.

    Example:
        excalidraw.save(file="diagrams/arch.excalidraw")
    """
    with LogSpan(span="excalidraw.save", file=file) as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        # Write current DSL as __otDSL element so load() can restore Python state
        dsl_str = _build_dsl(_dsl_state)
        if dsl_str.strip():
            _write_dsl_to_canvas(dsl_str)

        elements = _browser_evaluate_json(
            "() => Array.from(window.__drawApi.read())"
        )
        if not isinstance(elements, list):
            return f"Error: could not read scene elements: {elements}"

        native = {
            "type": "excalidraw",
            "version": 2,
            "source": "https://excalidraw.com",
            "elements": elements,
            "appState": {"viewBackgroundColor": "#ffffff"},
            "files": {},
        }

        out_path = resolve_cwd_path(file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(native, indent=2), encoding="utf-8")

        n = len([e for e in elements if not e.get("isDeleted", False)])
        s.add("elementCount", n)
        return f"saved {n} elements to {file}"


def load(*, file: str) -> str:
    """Restore diagram from a native ``.excalidraw`` file.

    Loads the full Excalidraw scene and restores Python DSL state from the
    embedded ``__otDSL`` element (written by ``whiteboard.save``). If the file was
    not created by ``whiteboard.save`` and lacks a ``__otDSL`` element, Python state
    will be empty (call ``whiteboard.sync`` after manually adding a DSL element).

    Args:
        file: Path to a ``.excalidraw`` file.

    Returns:
        Summary of elements loaded.

    Example:
        excalidraw.load(file="diagrams/arch.excalidraw")
    """
    with LogSpan(span="excalidraw.load", file=file) as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        src_path = resolve_cwd_path(file)
        if not src_path.exists():
            return f"Error: file not found: {file}"

        raw = src_path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return f"Error: invalid JSON in {file}: {exc}"

        if not isinstance(data, dict) or data.get("type") != "excalidraw":
            return (
                "Error: not a valid .excalidraw file - "
                "expected {\"type\": \"excalidraw\", ...}"
            )

        elements = data.get("elements", [])
        elements_json = json.dumps(elements)

        # Restore canvas
        _browser_evaluate(
            f"() => {{"
            f"  window.__drawElements = {{}};"
            f"  for (const el of {elements_json}) window.__drawElements[el.id] = el;"
            f"  window.__drawApi._raw.updateScene({{ elements: {elements_json} }});"
            f"}}"
        )

        # Sync Python state from __otDSL element
        _reset_state()
        dsl_str = _read_dsl_from_canvas()
        if dsl_str:
            _parse_dsl_to_state(dsl_str)
            warning = ""
        else:
            warning = " [warning: no __otDSL element — Python state is empty; call whiteboard.sync() after adding one]"

        # Rebuild _rendered_ids from state
        for id_ in _dsl_state["shapes"]:
            _rendered_ids.add(id_)
            _rendered_ids.add(id_ + "-text")
        for e in _dsl_state["edges"]:
            _rendered_ids.add(e["id"])

        n_shapes = len(_dsl_state["shapes"])
        n_edges = len(_dsl_state["edges"])
        n_elements = len(elements)
        s.add("shapes", n_shapes)
        s.add("edges", n_edges)
        if warning:
            s.add("warning", "no __otDSL element")
            return f"loaded {n_elements} element(s){warning}"
        return f"loaded {n_shapes} shapes, {n_edges} edges"


def sync() -> str:
    """Sync Python DSL state from the ``__otDSL`` canvas element.

    Reads the ``__otDSL`` text element from the current Excalidraw canvas
    and updates Python state. Use this after:

    - Loading a file directly in the Excalidraw UI (File → Open)
    - Drag-and-dropping an ``.excalidraw`` file onto the canvas
    - Any operation that bypasses ``whiteboard.load``

    Returns:
        Summary like ``"synced: 4 shapes, 3 edges"``.

    Example:
        excalidraw.sync()
    """
    with LogSpan(span="excalidraw.sync") as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        dsl_str = _read_dsl_from_canvas()
        if not dsl_str:
            return (
                "sync: no __otDSL element found on canvas. "
                "Canvas may have been created outside whiteboard, or whiteboard.save() was not used."
            )

        _parse_dsl_to_state(dsl_str)

        # Rebuild _rendered_ids
        _rendered_ids.clear()
        for id_ in _dsl_state["shapes"]:
            _rendered_ids.add(id_)
            _rendered_ids.add(id_ + "-text")
        for e in _dsl_state["edges"]:
            _rendered_ids.add(e["id"])

        n_shapes = len(_dsl_state["shapes"])
        n_edges = len(_dsl_state["edges"])
        s.add("shapes", n_shapes)
        s.add("edges", n_edges)
        return f"synced: {n_shapes} shapes, {n_edges} edges"


def help() -> str:
    """Return the full DSL and style reference. Call this before using whiteboard.draw or whiteboard.style.

    Returns the complete whiteboard DSL syntax and style shorthand reference as plain text.
    No browser interaction needed.

    Returns:
        Full DSL and style reference as a plain-text string.

    Example:
        excalidraw.help()
    """
    return _load_js("dsl-reference.md")


def style(*, ids: list[str], style: str) -> str:
    """Apply visual style properties to existing canvas elements in bulk.

    Applies Excalidraw style properties to the named elements. Never touches
    ``_dsl_state`` — styling is a purely visual operation.

    Style string is comma-separated ``key:value`` pairs using the shorthand
    table shared with ``whiteboard.draw`` inline styles:

    +---------+----------------------+------------------------------------------+
    | Key     | Excalidraw property  | Notes                                    |
    +=========+======================+==========================================+
    | ``bc``  | backgroundColor      | hex or named colour                      |
    | ``sc``  | strokeColor          | hex or named colour                      |
    | ``sw``  | strokeWidth          | number                                   |
    | ``ss``  | strokeStyle          | ``solid``, ``dashed``, ``dotted``        |
    | ``r``   | roughness            | 0-2                                      |
    | ``o``   | opacity              | 0-100                                    |
    | ``f``   | fontFamily           | ``hand``, ``normal``, ``mono``           |
    | ``fs``  | fontSize             | number                                   |
    | ``ta``  | textAlign            | ``left``, ``center``, ``right``          |
    | ``va``  | verticalAlign        | ``top``, ``middle``, ``bottom``          |
    | ``shape``| element type        | ``r``=rect, ``d``=diamond, ``c``=circle  |
    | ``x``/``y`` | position         | pixels                                   |
    | ``w``/``h`` | width/height     | pixels                                   |
    +---------+----------------------+------------------------------------------+

    Shape changes (``shape:d``, ``shape:c``) use delete+recreate with the same
    ID so arrow connections survive.

    Named colours: ``green``, ``blue``, ``red``, ``purple``, ``yellow``,
    ``orange``, ``pink``, ``gray``, ``white``, ``black``.

    Args:
        ids:   List of node IDs to style.
        style: Style string, e.g. ``"bc:#bbf7d0,sc:#16a34a,sw:2"``.

    Returns:
        Summary like ``"styled 3 element(s)"``.

    Example:
        excalidraw.style(ids=["a", "b"], style="bc:green,sc:#16a34a")
        excalidraw.style(ids=["c"], style="shape:d")
    """
    with LogSpan(span="excalidraw.style", ids=ids, style=style) as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        if not style.strip():
            return "Error: style string is empty"

        style_props = _parse_style_props(style)
        if not style_props:
            return "Error: no valid style properties parsed from style string"

        _js_style_elements(ids, style_props)

        s.add("count", len(ids))
        return f"styled {len(ids)} element(s)"


def share() -> str:
    """Generate a shareable Excalidraw link for the current canvas.

    Encrypts the full scene client-side (AES-GCM, 128-bit) and uploads it
    to Excalidraw's storage, returning a URL that anyone can open in a browser.

    The encryption and upload use the same protocol as Excalidraw's own
    "Export to Link" feature — end-to-end encrypted, key never sent to server.

    Returns:
        Shareable URL like ``https://excalidraw.com/#json={id},{key}``.

    Example:
        excalidraw.share()
    """
    with LogSpan(span="excalidraw.share") as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        # Read scene elements
        elements = _browser_evaluate_json(
            "() => Array.from(window.__drawApi.read())"
        )
        if not isinstance(elements, list):
            return f"Error: could not read scene elements: {elements}"

        # Build native excalidraw payload
        payload_obj = {
            "type": "excalidraw",
            "version": 2,
            "source": "https://excalidraw.com",
            "elements": elements,
            "appState": {"viewBackgroundColor": "#ffffff"},
            "files": {},
        }
        payload_json_str = json.dumps(payload_obj)

        # Encrypt client-side via Web Crypto API (AES-GCM, 128-bit key)
        # Return object directly (not JSON.stringify) so _browser_evaluate_json
        # can parse it without double-encoding issues.
        encrypt_js = (
            "async () => {"
            "  const data = " + json.dumps(payload_json_str) + ";"
            "  const enc = new TextEncoder().encode(data);"
            "  const key = await crypto.subtle.generateKey("
            "    {name: 'AES-GCM', length: 128}, true, ['encrypt']);"
            "  const iv = crypto.getRandomValues(new Uint8Array(12));"
            "  const ct = await crypto.subtle.encrypt({name: 'AES-GCM', iv}, key, enc);"
            "  const exportedKey = await crypto.subtle.exportKey('raw', key);"
            "  const combined = new Uint8Array(iv.byteLength + ct.byteLength);"
            "  combined.set(iv);"
            "  combined.set(new Uint8Array(ct), iv.byteLength);"
            "  const b64 = buf => btoa(String.fromCharCode(...new Uint8Array(buf)));"
            "  const keyB64 = b64(exportedKey)"
            "    .replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=/g,'');"
            "  return {data: b64(combined), key: keyB64};"
            "}"
        )

        enc_data = _browser_evaluate_json(encrypt_js)
        if not isinstance(enc_data, dict) or "data" not in enc_data or "key" not in enc_data:
            return f"Error: unexpected encryption result: {enc_data}"

        # Upload to Excalidraw storage using Python urllib (bypasses CORS)
        import urllib.error
        import urllib.request

        req_body = json.dumps({"data": enc_data["data"]}).encode("utf-8")
        req = urllib.request.Request(
            "https://json.excalidraw.com/api/v2/post/",
            data=req_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            return f"Error: upload failed — {exc}"
        except (json.JSONDecodeError, ValueError) as exc:
            return f"Error: unexpected response from Excalidraw storage — {exc}"

        share_id = resp_data.get("id", "")
        if not share_id:
            return f"Error: no ID in upload response: {resp_data}"

        key = enc_data["key"]
        url = f"https://excalidraw.com/#json={share_id},{key}"
        s.add("url", url)
        return url


def clear() -> str:
    """Clear all elements from canvas and reset Python DSL state.

    Returns:
        Confirmation message.

    Example:
        excalidraw.clear()
    """
    with LogSpan(span="excalidraw.clear") as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        _browser_evaluate("() => window.__drawApi.clear()")
        _reset_state()
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
    _reset_state()

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
    To restore previous content after opening, call whiteboard.load().

    Returns:
        "whiteboard ready" on success, or an error string.

    Example:
        excalidraw.open()
    """
    with LogSpan(span="excalidraw.open") as s:
        err = _ensure_ready()
        # Untracked content warning is non-fatal — open() always starts fresh
        if err and not err.startswith("Warning:"):
            s.add("error", err)
            return err
        # Always start fresh: reset Python state and clear canvas
        _reset_state()
        with contextlib.suppress(Exception):
            _browser_evaluate("() => window.__drawApi.clear()")
        return "whiteboard ready"


def close() -> str:
    """Close the excalidraw tab and reset all Python state.

    Resets DSL state unconditionally, then closes the browser tab so it is
    not left open. On the next whiteboard tool call a fresh excalidraw.com tab will
    be opened automatically.

    If Playwright is unavailable, only the Python state is reset.

    Returns:
        Confirmation message.

    Example:
        excalidraw.close()
    """
    _reset_state()

    if _check_playwright() is not None:
        return "whiteboard closed (browser unavailable)"

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
