# tool-excalidraw Specification

## Purpose

Playwright-driven live diagram manipulation on excalidraw.com. Exposes a `whiteboard`
pack with tools to draw, annotate, save, load, clear, scroll, and zoom
diagrams using a Mermaid-compatible DSL. Requires the Playwright MCP server.

Pack name: `whiteboard` (used as `whiteboard.draw(...)`, `whiteboard.note(...)`, etc.)
Short alias: `wb` — `wb.draw(...)` is equivalent to `whiteboard.draw(...)`.
Source: `src/otdev/tools/excalidraw.py`

---

## Requirements

### Requirement: Draw diagram elements

`whiteboard.draw(input=)` SHALL add shapes, edges, and subgraphs to the live
Excalidraw canvas from a Mermaid-compatible DSL string. It SHALL be additive —
elements already on canvas are never removed or repositioned. New shapes
receive auto-layout positions computed using topological layering over the full
merged graph. Edges are deduplicated by `(src, dst, label, startArrowhead,
endArrowhead)`. Unknown edge endpoints are auto-created as shapes with their
ID as label.

#### Scenario: Add shapes and edges
- **WHEN** `whiteboard.draw(input='a["A"]\nb["B"]\na-->b')` is called
- **THEN** two rectangles and a directed arrow SHALL appear on the canvas
- **AND** the return value SHALL match `"+2 shapes, +1 edge(s): edge-a-b"` (format: `"+N shapes[, M updated][, +P edge(s): ids][, +Q group(s)]"`)

#### Scenario: Additive — existing shapes untouched
- **WHEN** `whiteboard.draw(input='c["C"]')` is called after shapes `a` and `b` exist
- **THEN** only shape `c` SHALL be added; `a` and `b` SHALL be untouched

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

#### Scenario: ID pre-normalisation
- **WHEN** an ID contains spaces, hyphens, `+`, or uppercase letters (e.g. `api gateway["API Gateway"]`)
- **THEN** the ID SHALL be pre-normalised before parsing: non-word characters stripped, lowercased
- **AND** the label SHALL be preserved as written (label content is never modified)
- **AND** `api gateway --> lambda fn` SHALL parse as an edge from `apigateway` to `lambdafn`

#### Scenario: Subgraph return count
- **WHEN** `whiteboard.draw()` creates one or more new subgraphs
- **THEN** the return value SHALL include `, +N group(s)` at the end

#### Scenario: Auto-layout overlap avoidance
- **WHEN** a new node would be placed at the same column as an existing placed node
- **AND** the computed y position conflicts (within node height + gap) with any existing placed node
- **THEN** the new node SHALL be placed below all existing nodes in that column

#### Scenario: State not committed on JS failure
- **WHEN** the browser call raises an exception
- **THEN** `_dsl_state` and `_edge_keys` SHALL remain unchanged

#### Scenario: Single batch call per draw
- **WHEN** `whiteboard.draw()` is called with multiple shapes and edges
- **THEN** exactly one `_js_batch_draw` call SHALL be issued

### Requirement: Insert ASCII text notes

`whiteboard.note(input=, background=)` SHALL parse tagged blocks and render each as a
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

`whiteboard.embed_dsl()` SHALL insert the current DSL text as a grey code-font
rectangle with id `"dsl"` at `_max_rendered_y + 100`. Calling again overwrites
the previous embed (idempotent). The element is excluded from `save()`
snapshots. Returns `"nothing to embed — canvas is empty"` when state is empty.

### Requirement: Erase elements

`whiteboard.erase(ids=)` SHALL remove the specified element IDs from the canvas and
Python state. Edges that become dangling (src or dst in the erased set) SHALL
be removed automatically. Silently ignores IDs not currently rendered. Updates
`_edge_keys` by matching against the actual edges being removed (not a
reconstructed base ID string), covering both shape erasure and labeled-edge erasure.

#### Scenario: Erase shape removes dangling edges
- **WHEN** `whiteboard.erase(ids=["b"])` is called and edges `a-->b` and `b-->c` exist
- **THEN** both edges SHALL be removed from state and canvas
- **AND** the return value SHALL be `"erased 1 element(s), 2 dangling edge(s) removed"`

#### Scenario: Erase unknown ID
- **WHEN** `whiteboard.erase(ids=["nonexistent"])` is called
- **THEN** the return value SHALL be `"erased 0 element(s)"`

#### Scenario: Erase with no dangling edges
- **WHEN** `whiteboard.erase(ids=["a"])` is called and `a` has no connected edges
- **THEN** the return value SHALL be `"erased 1 element(s)"` (no dangling mention)

#### Scenario: `_max_rendered_y` not reset when shapes remain
- **WHEN** one of two shapes is erased
- **THEN** `_max_rendered_y` SHALL retain its current value

#### Scenario: `_max_rendered_y` reset when all shapes gone
- **WHEN** the last shape is erased
- **THEN** `_max_rendered_y` SHALL be reset to `0.0`

### Requirement: Save diagram to file

`whiteboard.save(file=)` SHALL write the current diagram as a native `.excalidraw` JSON
file (format: `{"type":"excalidraw","version":2,"elements":[...],...}`). Before
writing, it SHALL upsert a `__otDSL` text element containing the current DSL so
that `whiteboard.load()` and `whiteboard.sync()` can restore Python state. The file can be
opened directly in excalidraw.com. Conventionally uses the `.excalidraw` extension.

#### Scenario: File written in native .excalidraw format
- **WHEN** `whiteboard.save(file="arch.excalidraw")` is called
- **THEN** the file SHALL be valid JSON with `"type": "excalidraw"`
- **AND** `elements` SHALL include a `__otDSL` text element containing the DSL
- **AND** the file SHALL be openable directly in excalidraw.com

### Requirement: Load diagram from file

`whiteboard.load(file=)` SHALL restore a diagram from a native `.excalidraw` JSON file.
It SHALL pass all elements to `updateScene`, then read the `__otDSL` element to
restore Python DSL state. If `__otDSL` is absent, the canvas is restored but
a warning is included in the return value.

#### Scenario: Restore from .excalidraw file
- **WHEN** `whiteboard.load(file="arch.excalidraw")` is called
- **THEN** all elements SHALL be restored to the canvas at saved positions
- **AND** Python state SHALL be restored from the embedded `__otDSL` element
- **AND** the return value SHALL be `"loaded N shapes, M edges"`

#### Scenario: File missing __otDSL element
- **WHEN** the file does not contain a `__otDSL` element
- **THEN** the canvas SHALL be restored and the return SHALL include a warning
- **AND** the return format SHALL be `"loaded N element(s) [warning: no __otDSL element — ...]"`

#### Scenario: File not found
- **WHEN** the file path does not exist
- **THEN** `"Error: file not found: <path>"` SHALL be returned

#### Scenario: Invalid JSON
- **WHEN** the file is not valid JSON
- **THEN** `"Error: invalid JSON in <path>: ..."` SHALL be returned

#### Scenario: Wrong format
- **WHEN** the JSON does not have `"type": "excalidraw"`
- **THEN** `"Error: not a valid .excalidraw file - ..."` SHALL be returned

### Requirement: Clear diagram

`whiteboard.clear()` SHALL remove all elements from the canvas and reset
`_dsl_state`, `_edge_keys`, `_rendered_ids`, and `_max_rendered_y` to empty.

### Requirement: Open whiteboard

`whiteboard.open()` SHALL ensure excalidraw.com is open and bootstrapped, then always
start fresh — reset Python state and clear canvas — regardless of existing
canvas content. Untracked content warnings from `_ensure_ready()` are non-fatal.
Returns `"whiteboard ready"` on success.

### Requirement: Close whiteboard

`whiteboard.close()` SHALL reset all Python state unconditionally, then close the
browser tab (or navigate to `about:blank` as fallback). If Playwright is
unavailable, only Python state is reset.

### Requirement: Hard reset

`whiteboard.hard_reset()` SHALL reset Python state unconditionally and attempt canvas
clear if Playwright is available. Returns `"hard reset: state cleared, canvas
cleared"` or `"hard reset: state cleared (browser unavailable)"`.

### Requirement: Screenshot

`whiteboard.screenshot(file=)` SHALL call `browser_take_screenshot` with `format="png"`
and `raw=False`. Without `file`, returns the raw result for inline display.
With `file`, saves the image to disk (supports both temp-file path extraction
and base64 fallback).

### Requirement: Scroll and zoom

`whiteboard.scroll(dx=, dy=)` SHALL pan the canvas by the given pixel offsets.
`whiteboard.zoom(level=)` SHALL set the zoom level; passing `0` SHALL fit all elements
in view. Negative levels SHALL return an error string without calling the browser.
`whiteboard.fit()` SHALL delegate to `whiteboard.zoom(level=0)`.

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
| `id["Label"]` | Rectangle (only supported shape in DSL) |
| `id["Line1\nLine2"]` | Multiline label |

> **Note:** Ellipse `((...))` and diamond `{...}` syntax raise an error directing the user to `whiteboard.style()`. `classDef`/`class` syntax is also unsupported in the DSL; use `whiteboard.style()` for colours and shapes after drawing.

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

### Requirement: Apply visual styles

`whiteboard.style(ids=, style=)` SHALL apply Excalidraw style properties to existing
canvas elements in bulk. It SHALL never modify `_dsl_state` — styling is a
purely visual operation. The `style` string uses the same shorthand key:value
format as `whiteboard.draw` inline styles. All keys and values are case-insensitive.

Shape changes (`shape:d`, `shape:c`) SHALL use delete+recreate with the same ID
so arrow connections survive.

#### Scenario: Apply colour
- **WHEN** `whiteboard.style(ids=["a"], style="bc:green")` is called
- **THEN** shape `a` SHALL have `backgroundColor` set to `#bbf7d0`

#### Scenario: Case-insensitive values
- **WHEN** `whiteboard.style(ids=["a"], style="bc:Green,ss:Solid,f:Hand,shape:R")` is called
- **THEN** the values SHALL resolve identically to their lowercase equivalents

#### Scenario: Named colours
- **WHEN** the style string uses a named colour (e.g. `bc:blue`)
- **THEN** it SHALL resolve to the corresponding hex value (`#bfdbfe`)
- **AND** hex colours with `#` prefix SHALL be passed through unchanged

#### Scenario: Unknown IDs
- **WHEN** an ID in `ids` is not on the canvas
- **THEN** the call SHALL still return `"styled N element(s)"` (no error for unknown IDs)

### Requirement: Sync Python state from canvas

`whiteboard.sync()` SHALL read the `__otDSL` text element from the current Excalidraw
canvas and restore Python DSL state. Returns `"synced: N shapes, M edges"` on
success. If no `__otDSL` element is found, returns an explanatory message.

#### Scenario: Sync restores state
- **WHEN** `whiteboard.sync()` is called and a `__otDSL` element is present
- **THEN** `_dsl_state` SHALL be restored from the embedded DSL text

#### Scenario: No __otDSL element
- **WHEN** `whiteboard.sync()` is called and no `__otDSL` element is on canvas
- **THEN** a message explaining the absence SHALL be returned (no error)

### Requirement: __otDSL canvas element

The `__otDSL` element is a hidden text element on the Excalidraw canvas that
stores the current DSL text. It SHALL be:

- Written (upserted) by `whiteboard.save()` before file output
- Read by `whiteboard.load()` and `whiteboard.sync()` to restore Python state
- Excluded from `whiteboard.save()` scene snapshots (id starts with `__`)
- Written by `whiteboard.embed_dsl()` as a visible code-font element with id `"dsl"`
  (separate from the `__otDSL` hidden element)

#### Scenario: __otDSL written on save
- **WHEN** `whiteboard.save()` is called
- **THEN** a `__otDSL` text element SHALL be upserted on canvas with the current DSL

#### Scenario: __otDSL absent on load
- **WHEN** `whiteboard.load()` is called on a file with no `__otDSL` element
- **THEN** the canvas SHALL be restored and the return SHALL include a warning about empty Python state

### Requirement: DSL and style reference tool

`whiteboard.help()` SHALL return the full DSL syntax and style shorthand reference as a
plain-text string. No browser interaction is required. The content is loaded
from the bundled `dsl-reference.md` asset file.

#### Scenario: Returns non-empty string
- **WHEN** `whiteboard.help()` is called
- **THEN** a non-empty string covering DSL syntax and style shorthands SHALL be returned

### Requirement: Inline style props in draw()

Shape declarations in `whiteboard.draw()` MAY include style props after the closing `]`:

```
a["Label"] bc:green,sw:2
```

These props are applied to the shape element alongside label and position. The
same shorthand key:value format used by `whiteboard.style()` is supported. Values are
case-insensitive.
