# wb DSL and Style Reference

Use `;` as statement separator — no multi-line strings needed for agent calls.

---

## Draw DSL

### Shapes

Only rectangles are supported. Use `wb.style()` to change shape after drawing.

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

## Style Shorthands

Used in `wb.draw()` inline props and `wb.style()`. All keys and values are **case-insensitive**.

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
| `f` | fontFamily | `hand`, `normal`, `mono` |
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

### Roughness / opacity

| Key | Excalidraw property | Values |
|-----|---------------------|--------|
| `r` | roughness | 0, 1, or 2 |
| `o` | opacity | 0–100 |
