# wb (Whiteboard)

Playwright-driven live diagram manipulation on [excalidraw.com](https://excalidraw.com). Draw, annotate, save, and restore diagrams using a Mermaid-compatible DSL.

## TL;DR

- Call `wb.open()` first, then `wb.draw(...)`.
- Use `wb.note(...)` and `wb.embed_dsl()` for documentation overlays.
- Persist with `wb.save(file=...)` / `wb.load(file=...)`.
- Export visuals with `wb.screenshot(...)`; recover with `wb.hard_reset()` when state is broken.

Requires the Playwright MCP server:

```python
ot.server(enable="playwright")
```

## Quick Start

```python
wb.open()
wb.draw(input='a["API"]; b["DB"]; a-->b')
wb.screenshot()
wb.save(file="diagrams/arch.wb")
```

## API Summary (Generated)

Source of truth: `src/otdev/tools/excalidraw.py` (`__all__` + function docstrings).

<!-- BEGIN GENERATED:WB_HELP_SUMMARY -->
| Function | Summary |
|---|---|
| `wb.clear() -> str` | Clear all elements from canvas and reset Python DSL state. |
| `wb.close() -> str` | Close the excalidraw tab and reset all Python state. |
| `wb.draw(*, input: str) -> str` | Add diagram elements from DSL. Additive — never clears existing elements. |
| `wb.embed_dsl() -> str` | Embed the current DSL as a note element on the canvas. |
| `wb.erase(*, ids: list[str]) -> str` | Remove individual elements from the canvas and Python state. |
| `wb.fit() -> str` | Fit all elements in view. |
| `wb.hard_reset() -> str` | Reset Python DSL state unconditionally; attempt canvas clear if browser is available. |
| `wb.load(*, file: str) -> str` | Restore diagram from a file saved by save(). |
| `wb.note(*, input: str, background: str = '#f5f5dc') -> str` | Insert ASCII-rendered text annotations onto the canvas. |
| `wb.open() -> str` | Open excalidraw.com and start with a clean canvas. |
| `wb.save(*, file: str) -> str` | Save current diagram to a file in DSL+scene format. |
| `wb.screenshot(*, file: str | None = None) -> Any` | Take a screenshot of the current canvas as PNG. |
| `wb.scroll(*, dx: int = 0, dy: int = 0) -> str` | Pan the canvas by (dx, dy) pixels. |
| `wb.zoom(*, level: float) -> str` | Set zoom level. Pass 0 to fit all elements in view. |
<!-- END GENERATED:WB_HELP_SUMMARY -->

## Configuration

### Required

- No required `tools.wb` settings.

### Optional

- This pack does not define any pack-specific keys under `tools.wb`.

### Defaults

- OneTool uses the built-in defaults for whiteboard layout, DSL state, and save/load behavior.
- Runtime access still depends on the `playwright` MCP server being enabled.

## Tools

### `open()`

Open excalidraw.com and start with a clean canvas. Resets all Python state.

```python
wb.open()
# Returns: "whiteboard ready"
```

### `draw(input)`

Add diagram elements from DSL. Additive — never clears existing elements. New shapes get auto-layout positions. Edges are deduplicated by `(src, dst, label)`.

```python
wb.draw(input='a["Service A"]; b["DB"]; a-->b')
# Returns: "+2 shapes, total 3 elements"
```

### `note(input, background)`

Insert ASCII-rendered text annotations below any existing diagram content.

```python
wb.note(input="""
t[table:
Name,Role
Alice,Dev
Bob,QA
]
""")
```

### `erase(ids)`

Remove elements by ID. Dangling edges (whose src or dst is erased) are removed automatically.

```python
wb.erase(ids=["a", "edge-a-b"])
# Returns: "erased 2 element(s)"
```

### `embed_dsl()`

Insert the current DSL as a grey code-font box (`id="dsl"`) on the canvas. Idempotent. Excluded from `save()` snapshots.

```python
wb.embed_dsl()
# Returns: "embedded DSL (5 lines)"
```

### `save(file)`

Save the diagram to a `.wb` file (DSL + scene positions).

```python
wb.save(file="diagrams/arch.wb")
```

### `load(file)`

Restore a diagram saved by `save()`.

```python
wb.load(file="diagrams/arch.wb")
```

### `clear()`

Clear all elements from the canvas and reset Python state.

```python
wb.clear()
```

### `screenshot(file)`

Take a PNG screenshot of the current canvas.

```python
wb.screenshot()                            # return inline image
wb.screenshot(file="diagrams/canvas.png") # save to disk
```

### `scroll(dx, dy)`

Pan the canvas.

```python
wb.scroll(dx=200, dy=0)
```

### `zoom(level)`

Set zoom level. Pass `0` to fit all elements in view.

```python
wb.zoom(level=0.5)   # 50%
wb.zoom(level=0)     # fit all
```

### `fit()`

Fit all elements in view. Equivalent to `wb.zoom(level=0)`.

```python
wb.fit()
```

### `close()`

Close the excalidraw tab and reset all Python state.

```python
wb.close()
```

### `hard_reset()`

Reset Python state unconditionally; attempt canvas clear if browser is available. Use to recover from broken Playwright state.

```python
wb.hard_reset()
```

---

## Draw DSL

The `draw()` input uses a Mermaid-compatible syntax. Lines can be separated by newlines or semicolons.

### Shapes

```
id["Label"]               rectangle (default)
id(("Label"))             ellipse
id{"Label"}               diamond
id["Line1\nLine2"]        multiline label
```

### Edges

```
a-->b                     directed arrow
a-->|label|b              directed arrow with label
a---b                     undirected (no arrowheads)
a<-->b                    bidirectional arrows
a --o b                   dot/circle arrowhead at end
a --x b                   bar/cross arrowhead at end
a-.->b                    dashed directed arrow
a-.->|label|b             dashed directed arrow with label
a-.-b                     dashed undirected
```

### Style Classes

```
classDef name fill:#hex,stroke:#hex,stroke-width:2px;
class id1,id2 name
```

Supported style properties:

| Property | Values |
|----------|--------|
| `fill` | CSS colour (`#hex`, `red`, etc.) |
| `stroke` | CSS colour |
| `stroke-width` | Integer (px) |
| `stroke-style` | `solid`, `dashed`, `dotted` |
| `color` | Text colour |
| `roughness` | `0` (smooth) – `3` (rough) |
| `edges` | `sharp`, `round` |
| `font-family` | `handwritten`, `normal`, `code`, `serif` |
| `font-size` | `S` (16), `M` (20), `L` (28), `XL` (36), or integer |
| `text-align` | `left`, `center`, `right` |
| `vertical-align` | `top`, `middle` |
| `opacity` | 0–100 |

### Subgraphs

```
subgraph grp ["Group Label"]
  a
  b
end
```

Draws a bounding rectangle around the listed members.

### Headers (ignored)

```
flowchart TD
graph LR
```

Mermaid direction headers are accepted and silently skipped.

### Comments

```
%% this is a comment
# this is also a comment
```

---

## Note DSL

The `note()` input uses tagged blocks:

```
id[type:
content...
]
```

One or more blocks per call. Each becomes a code-font rectangle placed below the diagram.

### `table` — CSV grid

First row is the header. Columns separated by commas; rows by newlines or semicolons.

```python
wb.note(input="""
t[table:
Task,In,Out
compare:base,33,273
compare:mcp,3261,92
]
""")
```

Output:

```
+----------------+------+------+
| Task           |   In |  Out |
+================+======+======+
| compare:base   |   33 |  273 |
+----------------+------+------+
| compare:mcp    | 3261 |   92 |
+----------------+------+------+
```

### `tree` — directory / hierarchy

Depth indicated by leading `-`, `.`, `_`, or spaces. One character = one level (for spaces, the smallest non-zero indent is the unit).

```python
wb.note(input="""
tr[tree:
root/
-src/
--main.py
--utils.py
-tests/
]
""")
```

Output:

```
root/
├── src/
│   ├── main.py
│   └── utils.py
└── tests/
```

Space-indented trees also work:

```
root/
  src/
    main.py
  tests/
```

### `seq` — sequence diagram

One message per line: `Actor -> Actor: label`. Label is optional.

```python
wb.note(input="""
s[seq:
Client -> Server: request
Server -> DB: query
DB -> Server: rows
Server -> Client:
]
""")
```

Output:

```
+--------+      +--------+    +----+
| Client |      | Server |    | DB |
+--------+      +--------+    +----+
    |                |            |
    |---request----->|            |
    |                |---query--->|
    |                |<--rows-----|
    |<---------------|            |
+--------+      +--------+    +----+
| Client |      | Server |    | DB |
+--------+      +--------+    +----+
```

### `timeline` — Gantt bar chart

One task per line: `name,start,duration` (integers, 1-indexed).

```python
wb.note(input="""
g[timeline:
Design,1,4
Build,3,8
Test,9,4
]
""")
```

Output:

```
Design  [####........]
Build   [..########..]
Test    [...........####]
```

### `note` — plain text

Word-wrapped paragraph text (default wrap at 60 chars).

```python
wb.note(input="""
n[note:
This is a plain text annotation that will be
word-wrapped and displayed in a code-font box.
]
""")
```

---

## Examples

### Architecture diagram with annotations

```python
wb.open()
wb.draw(input="""
classDef svc fill:#dae8fc,stroke:#6c8ebf;
classDef db  fill:#d5e8d4,stroke:#82b366;
api["API Gateway"]
auth["Auth Service"]
users["Users DB"]
api-->auth
auth-->users
class api,auth svc
class users db
""")
wb.note(input="""
t[table:
Service,Latency,Owner
API Gateway,12ms,Platform
Auth Service,8ms,Security
]
""")
wb.fit()
wb.screenshot()
```

### Save and restore

```python
wb.save(file="diagrams/arch.wb")
# ... later ...
wb.open()
wb.load(file="diagrams/arch.wb")
```

### Incremental drawing

```python
wb.draw(input='a["Start"]; b["Process"]')
wb.draw(input='c["End"]; b-->c')   # additive, positions relative to existing
```
