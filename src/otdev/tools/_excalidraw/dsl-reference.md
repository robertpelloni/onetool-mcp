# whiteboard DSL and Style Reference

Use `;` as statement separator — no multi-line strings needed for agent calls.

---

## Draw DSL

### Shapes

Only rectangles are supported. Use `whiteboard.style()` to change shape after drawing.

```
id["Label"]                  rectangle
id["Label"] bc:green,sw:2   rectangle with inline style props
id["Line1\nLine2"]           multiline label (literal \n in string)
id bc:green                  style-only update (label unchanged, no brackets)
```

### Edges

```
a-->b                        directed arrow
a-->|label|b                 directed arrow with label
a---b                        undirected (no arrowheads)
a<-->b                       bidirectional arrows
a --o b                      dot/circle arrowhead at end
a --x b                      bar/cross arrowhead at end
a-.->b                       dashed directed arrow
a-.->|label|b                dashed directed arrow with label
a-.-b                        dashed undirected
```

Inline style props can be appended to any edge with a `{key:value,...}` block:

```
a --> b {sc:red,sw:2}          arrow with red thick stroke
a --> b {at:elbow}             orthogonal self-routing connector
a --> b {at:sharp,ss:dashed}   straight dashed line
a --> b {at:curve,sc:blue,o:60,fi:solid}   bezier blue semi-transparent arrow
```

### Subgraphs

```
subgraph grp ["Label"]
  id1
  id2
end
```

Draws a bounding rectangle around the listed member shapes.

### Headers (silently ignored)

```
flowchart TD
graph LR
```

### Comments (silently ignored)

```
%% this is a comment
# this is also a comment
```

### ID normalisation

Node IDs are lowercased and non-word characters stripped before parsing:

- `api gateway["API Gateway"]` → ID is `apigateway`, label is `API Gateway`
- `api gateway --> lambda fn` → edge from `apigateway` to `lambdafn`

---

## Note DSL

The `note()` input uses tagged blocks: `id[type:\ncontent\n]`

One or more blocks per call. Each becomes a code-font rectangle placed below the diagram.

### `table` — CSV grid

First row is the header. Columns separated by commas; rows by newlines or semicolons.

```
t[table:
Name,Role
Alice,Dev
Bob,QA
]
```

### `tree` — directory / hierarchy

Depth indicated by leading `-`, `.`, `_`, or spaces.

```
tr[tree:
root/
-src/
--main.py
-tests/
]
```

### `seq` — sequence diagram

One message per line: `Actor -> Actor: label` (label optional).

```
s[seq:
Client -> Server: request
Server -> DB: query
DB -> Server: rows
Server -> Client:
]
```

### `timeline` — Gantt bar chart

One task per line: `name,start,duration` (integers, 1-indexed).

```
g[timeline:
Design,1,4
Build,3,8
Test,9,4
]
```

### `note` — plain text

Word-wrapped paragraph (default 60 chars).

```
n[note:
This is a plain text annotation.
]
```

---

## Layout and Alignment

### `wb.layout()` — ELK.js graph layout

Reads the live canvas (not just DSL-drawn shapes), runs ELK.js in the browser
to compute layout positions, and applies them. If any elements are selected,
only the selected nodes are laid out. Calls `wb.fit()` implicitly after layout.

```python
wb.layout(
    direction="DOWN",      # DOWN | RIGHT | UP | LEFT
    gap_layer=80,          # px between layers
    gap_node=40,           # px between sibling nodes
    algorithm="layered",   # layered | stress | mrtree | radial | force
    node_placement="NETWORK_SIMPLEX",   # layered only
    crossing_min="LAYER_SWEEP",         # layered only
    cycle_breaking="GREEDY",            # layered only
    arrow_type=None,       # None | "curve" | "sharp" | "elbow" — patch all arrows after layout
    elk_options=None,      # dict of raw ELK key→value (merged last, overrides all)
)
```

**Algorithms:**
- `layered` — best for DAGs/pipelines; minimises crossings
- `stress` — spring-based; good for undirected graphs; increase `gap_node` to avoid overlaps
- `mrtree` — minimal-spanning-tree; good for single-root trees
- `radial` — radial tree centred on one node
- `force` — force-directed; good for clustered undirected graphs

### `wb.align()` — align or distribute elements

Aligns a set of elements using Excalidraw's built-in alignment actions.

```python
wb.align(ids=["a", "b", "c"], axis="top")
```

| `axis` | Effect |
|---|---|
| `"left"` | Snap left edges to leftmost element |
| `"hcenter"` | Centre on vertical axis |
| `"right"` | Snap right edges to rightmost element |
| `"top"` | Snap top edges to topmost element |
| `"vcenter"` | Centre on horizontal axis |
| `"bottom"` | Snap bottom edges to lowest element |
| `"hdistribute"` | Even horizontal spacing |
| `"vdistribute"` | Even vertical spacing |

---

## Style Shorthands

Used in `whiteboard.draw()` inline props and `whiteboard.style()`. All keys and values are **case-insensitive**.

Format: comma-separated `key:value` pairs, e.g. `bc:green,sw:2,ss:dashed`

### Colour keys

| Key | Excalidraw property | Notes |
|-----|---------------------|-------|
| `bc` | backgroundColor | hex or named colour |
| `sc` | strokeColor | hex or named colour |

Hex colours require `#` prefix: `bc:#ff0000`
Named colours do not: `bc:green`

Named colours: `green`, `blue`, `red`, `purple`, `yellow`, `orange`, `pink`, `gray` (or `grey`), `white`, `black`

### Stroke / line

| Key | Excalidraw property | Values |
|-----|---------------------|--------|
| `sw` | strokeWidth | number (e.g. `sw:2`) |
| `ss` | strokeStyle | `solid`, `dashed`, `dotted` |

### Text

| Key | Excalidraw property | Values |
|-----|---------------------|--------|
| `f` | fontFamily | `hand`, `normal`, `mono`, `excalidraw` |
| `fs` | fontSize | number (e.g. `fs:20`) |
| `ta` | textAlign | `left`, `center`, `right` |
| `va` | verticalAlign | `top`, `middle`, `bottom` |

### Shape

| Key | Excalidraw property | Values |
|-----|---------------------|--------|
| `shape` | element type | `r`=rectangle, `d`=diamond, `c`=circle |

### Position / size

| Key | Excalidraw property | Values |
|-----|---------------------|--------|
| `x` / `y` | position | pixels |
| `w` / `h` | width / height | pixels |

New shapes are **auto-sized** from their label content: width scales with the longest line, height with the number of lines. Minimum size is 160×60 px. Use `w` / `h` to override: `a["Label"] w:300,h:80`.

### Roughness / opacity

| Key | Excalidraw property | Values |
|-----|---------------------|--------|
| `r` | roughness | 0, 1, or 2 |
| `o` | opacity | 0–100 |

### Fill and corner style

| Key | Applies to | Excalidraw property | Values |
|-----|------------|---------------------|--------|
| `fi` | shapes, arrows | fillStyle | `solid`, `hachure`, `cross-hatch`, `dots`, `zigzag`, `zigzag-line` |
| `cr` | shapes only | corners | `round` (default), `sharp` |
| `at` | arrows only | arrowType | `curve` (default), `sharp`, `elbow` |

`at:curve` → bezier curve; `at:sharp` → straight line; `at:elbow` → orthogonal connector
