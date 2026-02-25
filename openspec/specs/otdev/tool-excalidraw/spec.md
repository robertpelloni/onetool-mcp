# tool-excalidraw Specification

## Purpose

Playwright-driven live diagram manipulation on excalidraw.com. Exposes a `wb`
pack with tools to draw, annotate, save, load, clear, scroll, and zoom
diagrams using a Mermaid-compatible DSL. Requires the Playwright MCP server.

Pack name: `wb` (used as `wb.draw(...)`, `wb.note(...)`, etc.)
Source: `src/otdev/tools/excalidraw.py`

---

## Requirements

### Requirement: Draw diagram elements

`wb.draw(input=)` SHALL add shapes, edges, and subgraphs to the live
Excalidraw canvas from a Mermaid-compatible DSL string. It SHALL be additive —
elements already on canvas are never removed or repositioned. New shapes
receive auto-layout positions computed using topological layering over the full
merged graph. Edges are deduplicated by `(src, dst, label, startArrowhead,
endArrowhead)`. Unknown edge endpoints are auto-created as shapes with their
ID as label.

#### Scenario: Add shapes and edges
- **WHEN** `wb.draw(input='a["A"]\nb["B"]\na-->b')` is called
- **THEN** two rectangles and a directed arrow SHALL appear on the canvas
- **AND** the return value SHALL be `"+2 shapes, total 3 elements"`

#### Scenario: Additive — existing shapes untouched
- **WHEN** `wb.draw(input='c["C"]')` is called after shapes `a` and `b` exist
- **THEN** only shape `c` SHALL be added; `a` and `b` SHALL be untouched

#### Scenario: Style classes
- **WHEN** the DSL includes `classDef svc fill:#dae8fc,stroke:#6c8ebf;` and `class a svc`
- **THEN** shape `a` SHALL be drawn with the specified fill and stroke colours

#### Scenario: Subgraph bounding rect
- **WHEN** the DSL includes a `subgraph ... end` block naming existing shapes
- **THEN** a bounding rectangle SHALL appear behind the member shapes
- **AND** subgraphs are redrawn on every call to reflect current member positions

#### Scenario: Edge deduplication
- **WHEN** `draw()` is called twice with the same edge
- **THEN** only one arrow SHALL appear on canvas

#### Scenario: Bidirectional and special arrowheads
- **WHEN** the DSL contains `a<-->b`, `a --o b`, or `a --x b`
- **THEN** arrows SHALL render with the correct arrowhead style at each end

#### Scenario: Dashed edges
- **WHEN** the DSL contains `a-.->b` (dashed directed) or `a-.-b` (dashed undirected)
- **THEN** arrows SHALL render with a dashed stroke style

#### Scenario: Auto-create unknown nodes
- **WHEN** an edge references a node not declared as a shape (e.g. `a-->typo`)
- **THEN** the unknown node SHALL be auto-created with its ID as the label

#### Scenario: State not committed on JS failure
- **WHEN** the browser call raises an exception
- **THEN** `_dsl_state` and `_edge_keys` SHALL remain unchanged

#### Scenario: Single batch call per draw
- **WHEN** `wb.draw()` is called with multiple shapes and edges
- **THEN** exactly one `_js_batch_draw` call SHALL be issued

### Requirement: Insert ASCII text notes

`wb.note(input=, background=)` SHALL parse tagged blocks and render each as a
code-font rectangle placed below any existing diagram content (below
`_max_rendered_y + 100`). It SHALL NOT call `auto_layout`. The background
colour defaults to beige (`#f5f5dc`).

#### Scenario: Table note
- **WHEN** a `table` block with CSV content is provided
- **THEN** a `tabulate` ASCII grid table SHALL appear on canvas with the first row as header

#### Scenario: Tree note
- **WHEN** a `tree` block with indented lines is provided
- **THEN** a unicode-connector tree (├──, └──, │) SHALL appear on canvas
- **AND** depth is detected from leading `-`, `.`, `_`, or space characters

#### Scenario: Sequence diagram note
- **WHEN** a `seq` block with `Actor -> Actor: label` lines is provided
- **THEN** an ASCII box-and-arrow sequence diagram SHALL appear on canvas

#### Scenario: Timeline note
- **WHEN** a `timeline` block with `name,start,duration` lines is provided
- **THEN** a Gantt-style bar chart SHALL appear on canvas
- **AND** non-integer start or duration SHALL return an error string

#### Scenario: Plain text note
- **WHEN** a `note` block with paragraph text is provided
- **THEN** word-wrapped text (default 60 chars) SHALL appear on canvas

#### Scenario: Unknown block type
- **WHEN** a block type not in `{table, tree, seq, timeline, note}` is used
- **THEN** an error string naming the unsupported type SHALL be returned
- **AND** no shape SHALL be inserted

#### Scenario: No blocks found
- **WHEN** the input contains no valid `id[type:\ncontent\n]` blocks
- **THEN** an error string SHALL be returned

#### Scenario: Renderer error propagates
- **WHEN** a renderer returns a string starting with `Error:`
- **THEN** `note()` SHALL return the error string with the block ID prepended
- **AND** no shape SHALL be inserted for that block

#### Scenario: Note placed below existing content
- **WHEN** `_max_rendered_y` is 300.0 and `note()` is called
- **THEN** the note shape `y` SHALL be at least 400.0 (`_max_rendered_y + 100`)

### Requirement: Embed DSL as canvas element

`wb.embed_dsl()` SHALL insert the current DSL text as a grey code-font
rectangle with id `"dsl"` at `_max_rendered_y + 100`. Calling again overwrites
the previous embed (idempotent). The element is excluded from `save()`
snapshots. Returns `"nothing to embed — canvas is empty"` when state is empty.

### Requirement: Erase elements

`wb.erase(ids=)` SHALL remove the specified element IDs from the canvas and
Python state. Edges that become dangling (src or dst in the erased set) SHALL
be removed automatically. Silently ignores IDs not currently rendered. Updates
`_edge_keys` by matching against the actual edges being removed (not a
reconstructed base ID string), covering both shape erasure and labeled-edge erasure.

#### Scenario: Erase shape removes dangling edges
- **WHEN** `wb.erase(ids=["b"])` is called and edges `a-->b` and `b-->c` exist
- **THEN** both edges SHALL be removed from state and canvas

#### Scenario: Erase unknown ID
- **WHEN** `wb.erase(ids=["nonexistent"])` is called
- **THEN** the return value SHALL be `"erased 0 element(s)"`

#### Scenario: `_max_rendered_y` not reset when shapes remain
- **WHEN** one of two shapes is erased
- **THEN** `_max_rendered_y` SHALL retain its current value

#### Scenario: `_max_rendered_y` reset when all shapes gone
- **WHEN** the last shape is erased
- **THEN** `_max_rendered_y` SHALL be reset to `0.0`

### Requirement: Save diagram to file

`wb.save(file=)` SHALL write the current diagram to a file in `[dsl]/[scene]`
format. The scene block SHALL capture live element positions, sizes, and visual
properties from `getSceneElements()`. Bound text elements (id ends in `-text`
or `-label`) and bound arrow elements (has `startBinding`) SHALL be excluded.
Elements with id starting with `__` or equal to `"dsl"` SHALL be excluded.

#### Scenario: File written in [dsl]/[scene] format
- **WHEN** `wb.save(file="out.wb")` is called
- **THEN** the file SHALL start with `[dsl]\n` followed by the DSL text
- **AND** contain `[scene]\n` followed by a JSON array of scene elements

### Requirement: Load diagram from file

`wb.load(file=)` SHALL restore a diagram saved by `save()`. It SHALL parse the
DSL, restore Python state, and render all elements at the saved scene positions.
Files must use the `[dsl]/[scene]` format written by `save()`.

#### Scenario: Restore from [dsl]/[scene] format
- **WHEN** `wb.load(file=)` is called on a `[dsl]/[scene]` file
- **THEN** shapes SHALL appear at the saved x/y positions

#### Scenario: File missing [dsl] block
- **WHEN** the file does not contain a `[dsl]` section
- **THEN** an error string SHALL be returned

#### Scenario: File not found
- **WHEN** the file path does not exist
- **THEN** an error string SHALL be returned

### Requirement: Clear diagram

`wb.clear()` SHALL remove all elements from the canvas and reset
`_dsl_state`, `_edge_keys`, `_rendered_ids`, and `_max_rendered_y` to empty.

### Requirement: Open whiteboard

`wb.open()` SHALL ensure excalidraw.com is open and bootstrapped, then always
start fresh — reset Python state and clear canvas — regardless of existing
canvas content. Untracked content warnings from `_ensure_ready()` are non-fatal.
Returns `"whiteboard ready"` on success.

### Requirement: Close whiteboard

`wb.close()` SHALL reset all Python state unconditionally, then close the
browser tab (or navigate to `about:blank` as fallback). If Playwright is
unavailable, only Python state is reset.

### Requirement: Hard reset

`wb.hard_reset()` SHALL reset Python state unconditionally and attempt canvas
clear if Playwright is available. Returns `"hard reset: state cleared, canvas
cleared"` or `"hard reset: state cleared (browser unavailable)"`.

### Requirement: Screenshot

`wb.screenshot(file=)` SHALL call `browser_take_screenshot` with `format="png"`
and `raw=False`. Without `file`, returns the raw result for inline display.
With `file`, saves the image to disk (supports both temp-file path extraction
and base64 fallback).

### Requirement: Scroll and zoom

`wb.scroll(dx=, dy=)` SHALL pan the canvas by the given pixel offsets.
`wb.zoom(level=)` SHALL set the zoom level; passing `0` SHALL fit all elements
in view. Negative levels SHALL return an error string without calling the browser.
`wb.fit()` SHALL delegate to `wb.zoom(level=0)`.

### Requirement: Automatic browser lifecycle management

Every public tool SHALL call `_ensure_ready()` before executing (except
`screenshot` and `hard_reset` which call `_check_playwright()` instead).
If excalidraw.com is not open or the API is missing, the tool SHALL
transparently navigate, bootstrap, and re-render from the current Python state.

#### Scenario: First call opens browser
- **WHEN** no browser session is active and any excalidraw tool is called
- **THEN** excalidraw.com SHALL be opened and bootstrapped automatically

#### Scenario: Recovery after page reload
- **WHEN** the user reloads excalidraw.com mid-session and then calls `draw()`
- **THEN** `draw()` SHALL re-bootstrap and re-render existing shapes from Python state
- **AND** the new shape SHALL also appear

#### Scenario: Bootstrap failure
- **WHEN** `bootstrap.js` returns `false` (React API not found)
- **THEN** the tool SHALL return `"Error: excalidraw bootstrap failed — React API not found on page"`

#### Scenario: Playwright not running
- **WHEN** the Playwright MCP server is not active and any excalidraw tool is called
- **THEN** the tool SHALL return an error instructing the user to enable the Playwright server

#### Scenario: Untracked canvas content warning
- **WHEN** the canvas is ready but `_rendered_ids` is empty and the canvas has untracked elements
- **THEN** `_ensure_ready()` SHALL return a warning string (non-fatal for `open()`)

### Requirement: DSL syntax

The DSL accepted by `draw()` SHALL support a strict subset of Mermaid flowchart syntax.
Lines may be separated by newlines or semicolons. Node IDs are normalised to
lowercase with non-word characters stripped.

#### Supported shape types
| Syntax | Shape |
|--------|-------|
| `id["Label"]` | Rectangle |
| `id(("Label"))` | Ellipse |
| `id{"Label"}` | Diamond |
| `id["Line1\nLine2"]` | Multiline label |

#### Supported edge types
| Syntax | Meaning |
|--------|---------|
| `a-->b` | Directed arrow |
| `a-->|label|b` | Directed arrow with label |
| `a---b` | Undirected (no arrowheads) |
| `a<-->b` | Bidirectional arrows |
| `a --o b` | Dot arrowhead at end |
| `a --x b` | Bar arrowhead at end |
| `a-.->b` | Dashed directed arrow |
| `a-.-b` | Dashed undirected |

#### Scenario: Mermaid header ignored
- **WHEN** DSL starts with `flowchart TD` or `graph LR`
- **THEN** the header SHALL be silently ignored

#### Scenario: Comment lines ignored
- **WHEN** DSL lines begin with `%%` or `#`
- **THEN** those lines SHALL be treated as comments and ignored

#### Scenario: Multiline labels
- **WHEN** a shape is defined as `id["Line1\nLine2"]`
- **THEN** the shape label SHALL contain a newline character

### Requirement: Auto-layout

`auto_layout(shapes, edges)` SHALL compute topological layer positions using
Kahn's algorithm. Cyclic nodes (not resolved by Kahn's) SHALL be placed in a
grid after the last DAG layer.

#### Scenario: Linear chain
- **WHEN** shapes form `a → b → c`
- **THEN** x-positions SHALL satisfy `x(a) < x(b) < x(c)`

#### Scenario: Cyclic graph
- **WHEN** all shapes form a cycle
- **THEN** every shape SHALL receive a position
- **AND** not all shapes SHALL share the same x-coordinate

### Requirement: Style resolution

`_resolve_style(shape, classes)` SHALL merge class style properties into an
Excalidraw-compatible style dict. Unknown values for `edges`, `font-family`,
`font-size`, `roughness`, `stroke-width`, and `opacity` SHALL be silently
ignored (no exception raised).

### Requirement: Note DSL

The `note()` input uses `id[type:\ncontent\n]` blocks. Supported types:

| Type | Renderer | Input format |
|------|----------|-------------|
| `table` | ASCII grid via `tabulate` | CSV (first row = header; `;` as row separator) |
| `tree` | Unicode tree (├──, └──) | Indented lines; `-`, `.`, `_`, or spaces as depth |
| `seq` | ASCII sequence diagram | `Actor -> Actor: label` lines |
| `timeline` | Gantt bar chart | `name,start,duration` (integers, 1-indexed) |
| `note` | Word-wrapped text | Plain paragraph text (wrap at 60 chars) |

All renderers accept `;` as a line separator in addition to newlines.
