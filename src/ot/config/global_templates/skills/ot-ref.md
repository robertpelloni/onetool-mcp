---
name: ot-ref
description: OneTool reference — error recovery, security, output control, parameter traps
tags: [reference, cheatsheet]
---

# OneTool Reference

## Error Recovery

When a call fails, introspect before guessing:
- Unknown tool? → `ot.tools(pattern="name")` or `ot.packs(pattern="name")`
- Wrong args? → `ot.tool_info(name="pack.tool")` for signature + args
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

Not all packs are installed by default. Install the appropriate extra if missing:

| Extra   | Packs                                                 |
|---------|-------------------------------------------------------|
| (core)  | mem, ot_llm, ot, package.audit                        |
| [util]  | brave, convert, excel, file, ground                   |
| [dev]   | context7, db, diagram, package, ripgrep, web, worktree |

Check loaded packs: `ot.packs()`. Install: `pip install onetool-mcp[util]`.

## Parameter Traps

Common wrong parameter names. When a call fails, check: `ot.tool_info(name="pack.tool")`

| Pack    | Wrong            | Correct                      |
|---------|------------------|------------------------------|
| excel   | `path=`          | `filepath=`                  |
| excel   | `sheet=`         | `sheet_name=`                |
| excel   | `query=`         | `pattern=`                   |
| convert | `path=`          | `pattern=` + `output_dir=`   |
| ground  | `count=`         | `max_sources=`               |
| ot_llm  | `input=`         | `data=`                      |
| ot_llm  | `instruction=`   | `prompt=`                    |
| db      | `path=`          | `db_url="sqlite:///..."`     |
| db      | `table=`         | `table_names=["list"]`       |
| package | `packages="str"` | `packages=["list"]`          |
| mem     | `key=`           | `topic=`                     |
| mem     | `tag=`           | `category=`                  |
| web     | `max_chars=`     | `max_length=`                |
