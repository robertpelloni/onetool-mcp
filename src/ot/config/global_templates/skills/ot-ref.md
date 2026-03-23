---
name: ot-ref
description: OneTool reference — error recovery, security, output control, parameter traps
tags: [reference, cheatsheet]
---

# OneTool Reference

## Error Recovery

When a call fails, introspect before guessing:
- Unknown tool? → `ot.tools(pattern="name")` or `ot.packs(pattern="name")`
- Wrong args? → `ot.tool_info(name="pack.tool")` for signature + args — short aliases work (e.g. `ctx.ask` resolves to `ot_context.ask`)
- General confusion? → `ot.help(query="topic")`
- If introspection fails → report the error, don't guess or compute results yourself

## Security

- Python glue between tool calls works: variables, dicts, list comprehensions
- Arbitrary imports are blocked — use pack tools instead
- Check rules: `ot.security()` — check a name: `ot.security(check="json")`

## Output Control

```python
__format__ = "yml_h"; brave.search(query="test")
__format__ = "json"; file.read(path="data.json")
__sanitize__ = False; file.read(path="config.yaml")
```

Formats: `json` (default), `json_h` (pretty), `yml` (flow), `yml_h` (block), `text`

## Multi-Step Patterns

Return the last expression to get results from chained calls:

```python
x = brave.search(query="topic A")
y = brave.search(query="topic B")
{"a": x, "b": y}
```

## Pack Extras

Not all packs are installed by default.

| Extra   | Packs                                                 |
|---------|-------------------------------------------------------|
| (core)  | mem, ot_llm, ot, package.audit                        |
| [util]  | brave, convert, excel, file, ground                   |
| [dev]   | context7, db, diagram, package, ripgrep, webfetch, worktree |

Check loaded packs: `ot.packs()`. Install: `pip install onetool-mcp[util]`.

## ctx Handles

Large tool results are offloaded to ctx automatically and returned as a handle dict:
```python
{"handle": "b2d18a1b", "format": "json", "size_bytes": 4200, ...}
```

**`handle` is the string ID — never pass the dict to ctx tools.**

```python
# WRONG — crashes with "File name too long" or "Handle not found: {'handle': ...}"
h = ot.tool_info(pattern='figma')
ctx.grep(h, pattern='page')

# RIGHT — extract the string ID first
h = ot.tool_info(pattern='figma')
ctx.grep(handle=h['handle'], pattern='page')
```

Navigate a handle:
```python
ctx.toc(handle=h['handle'])                           # structure overview
ctx.slice(handle=h['handle'], select='10:50')         # line range (colon, NOT dash)
ctx.slice(handle=h['handle'], select='#3')            # 3rd section by number
ctx.slice(handle=h['handle'], select='SectionName')   # markdown section by heading
ctx.query(handle=h['handle'], expr='key.path')        # json/yaml jmespath
ctx.grep(handle=h['handle'], pattern='error')         # regex search
ctx.read(handle=h['handle'], offset=1, limit=50)      # paginated raw lines
ctx.ask(handle=h['handle'], q='What is X?')           # LLM question
```

## Parameter Traps

Common wrong parameter names. When a call fails, check: `ot.tool_info(name="pack.tool")`

| Call | Correct | Common mistake |
|------|---------|----------------|
| `ctx.ask(handle=h, q='...')` | `q=` | `question=` |
| `ctx.query(handle=h, expr='...')` | `expr=` | `query=` |
| `ot_image.load(img='...')` | `img=` | `path=` |
