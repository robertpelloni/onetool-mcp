---
name: ot-adv-guide
description: OneTool advanced reference — full tool cheatsheet, parameter traps, output control, and multi-step patterns
tags: [reference, cheatsheet, advanced]
---

# OneTool Advanced Reference

Full cheatsheet for AI agents. All examples use keyword-only arguments.

## Prerequisites

Not all tool packs are available by default. Install the appropriate extra if a pack is missing:

| Extra | Install command | Tool packs included |
|-------|----------------|---------------------|
| (core) | `pip install onetool-mcp` | `mem`, `llm`, `ot`, `package.audit` |
| `[util]` | `pip install onetool-mcp[util]` | `brave`, `convert`, `excel`, `file`, `ground` |
| `[dev]` | `pip install onetool-mcp[dev]` | `context7`, `db`, `diagram`, `package`, `ripgrep`, `web`, `worktree` |

If a tool is missing, check installed packs with `ot.packs()` and install the required extra.

## Web Search

```python
brave.search(query="python async patterns")
brave.search(query="AI news", count=5)
brave.news(query="tech layoffs")
brave.image(query="sunset beach")
brave.search_batch(queries=["topic A", "topic B"])
```

## Web Fetch

```python
web.fetch(url="https://example.com")
web.fetch(url="https://example.com", include_links=True, max_length=5000)
web.fetch_batch(urls=["https://a.com", "https://b.com"])
```

## File Operations

```python
file.read(path="src/main.py")
file.read(path="src/main.py", offset=100, limit=50)  # 1-indexed lines
file.write(path="output.txt", content="hello", create_dirs=True)
file.list(path="src/", pattern="*.py")
file.search(glob="src/**/*.py")
file.tree(path=".", max_depth=2)
file.info(path="data.csv")
file.copy(source="a.txt", dest="b.txt")
file.move(source="old.txt", dest="new.txt")
file.delete(path="temp.txt")
file.edit(path="config.yaml", old_text="key: old", new_text="key: new")
```

## Code Search (ripgrep)

```python
ripgrep.search(pattern="def main", path="src/")
ripgrep.search(pattern="TODO", path=".", glob="*.py", context=3)
ripgrep.count(pattern="import", path="src/", file_type="py")
ripgrep.files(path="src/", glob="*.py")
ripgrep.types()
```

## Memory

```python
# Categories: rule, context, decision, mistake, discovery, note
mem.write(topic="project/rules", content="Always use keyword args", category="rule")
mem.write(topic="docs/guide", file="path/to/guide.md", toc=True)
mem.read(topic="project/rules")
mem.read(topic="project/rules", meta=True)
mem.search(query="authentication patterns")
mem.search(query="LogSpan", mode="pattern", topic="docs/")
mem.grep(pattern="TODO", case_sensitive=False)
mem.grep(pattern="def \\w+\\(", topic="docs/", context=3)
mem.list(topic="project/")
mem.list(category="rule")
mem.toc(topic="docs/guide")
mem.slice(topic="docs/guide", select="Requirements")
mem.slice(topic="docs/guide", select=":50")
mem.delete(topic="temp/", confirm=True)
mem.stats()
```

## Database

```python
db.tables(db_url="sqlite:///data.db")
db.schema(table_names=["users", "orders"], db_url="sqlite:///data.db")
db.query(
    sql="SELECT * FROM users WHERE status = :status LIMIT 10",
    db_url="sqlite:///data.db",
    params={"status": "active"}
)
```

## Excel

```python
excel.info(filepath="data.xlsx")
excel.read(filepath="data.xlsx")
excel.read(filepath="data.xlsx", sheet_name="Sales", start_cell="B2", end_cell="D10")
excel.write(filepath="out.xlsx", data=[["Name", "Age"], ["Alice", 30]])
excel.sheets(filepath="data.xlsx")
excel.search(filepath="data.xlsx", pattern="Error*")
excel.formula(filepath="sales.xlsx", cell="C10", formula="=SUM(C2:C9)")
```

## Package Info

```python
package.pypi(packages=["requests", "flask"])
package.npm(packages=["react", "next"])
package.audit()
package.models(query="claude", limit=5)
```

## Document Conversion

```python
convert.auto(pattern="docs/*", output_dir="output/")
convert.pdf(pattern="report.pdf", output_dir="md/")
convert.word(pattern="specs/*.docx", output_dir="md/")
convert.excel(pattern="data/*.xlsx", output_dir="md/", include_formulas=True)
convert.powerpoint(pattern="slides/*.pptx", output_dir="md/")
```

## LLM Transform

```python
llm.transform(data=some_text, prompt="Summarise in 3 bullet points")
llm.transform(data=results, prompt="Extract prices as JSON", json_mode=True)
llm.transform_file(prompt="Convert to RST", in_file="README.md", out_file="README.rst")
```

## Diagrams

```python
diagram.list_providers(focus_only=True)
diagram.get_diagram_instructions(provider="mermaid")
diagram.generate_source(source="graph TD; A-->B", provider="mermaid", name="flow")
diagram.render_diagram(source="graph LR; A-->B", provider="mermaid", name="seq")
diagram.get_template(name="api-flow")
```

## Grounding Search

```python
ground.search(query="python best practices", focus="code", max_sources=5)
ground.docs(query="react hooks lifecycle", technology="React")
ground.dev(query="async await javascript", language="Python")
ground.reddit(query="best IDE for python", subreddit="python")
```

## Library Docs

```python
context7.search(query="fastapi")
context7.doc(library_key="fastapi/fastapi", topic="middleware")
context7.doc(library_key="pallets/flask", topic="blueprints", mode="code")
```

## Browser Annotation Utilities

OneTool provides visual annotation helpers for both browser automation stacks.
For full browser automation tools, see: `ot.skills(name="ot-chrome-devtools-mcp")` or `ot.skills(name="ot-playwright-mcp")`.

> **MCP server required.** These utilities only work when the corresponding MCP server is configured
> in your project's `servers.yaml` (or via `include: [config/servers.yaml]` in `onetool.yaml`).
> `devtools_util` requires the `devtools:` server; `playwright_util` requires the `playwright:` server.
> Check configured servers with `ot.servers()`.

### devtools_util (Chrome DevTools)

```python
devtools_util.inject_annotations()
devtools_util.highlight_element(selector="button.submit", label="Click here")
devtools_util.highlight_element(selector=".error", label="Error", color="red")
devtools_util.scan_annotations()
devtools_util.clear_annotations()
devtools_util.guide_user(task="Fill form", steps=[
    {"selector": "input[name='name']", "label": "Enter name"},
    {"selector": "button[type='submit']", "label": "Submit"},
])
```

### playwright_util (Playwright)

```python
playwright_util.inject_annotations()
playwright_util.highlight_element(selector="button.submit", label="Click here")
playwright_util.scan_annotations()
playwright_util.clear_annotations()
playwright_util.guide_user(task="Fill form", steps=[
    {"selector": "input[name='name']", "label": "Enter name"},
    {"selector": "button[type='submit']", "label": "Submit"},
])
```

## System & Config

```python
ot.health()                              # Component status
ot.config()                              # Configuration summary
ot.debug()                               # Full debug info
ot.stats()                               # Usage statistics
ot.version()                             # Version string
ot.reload()                              # Reload configuration
ot.security()                            # Security rules summary
ot.security(check="os")                  # Check specific pattern
ot.servers()                             # List MCP proxy servers
ot.servers(info="full")                  # Server details + tools
ot.result(handle="abc123")               # Paginate large output
ot.result(handle="abc123", search="error")  # Filter stored result
ot.skills()                              # List available skills
ot.skills(name="ot-guide")               # Discovery guide
ot.skills(name="ot-adv-guide")           # This cheatsheet
```

## Output Control

```python
__format__ = "yml_h"; brave.search(query="test")
__format__ = "json"; file.read(path="data.json")
__sanitize__ = False; file.read(path="config.yaml")
```

Formats: `json` (default), `json_h` (pretty), `yml` (flow), `yml_h` (block).

## Multi-Step Patterns

End multi-step code with the value to return:

```python
x = brave.search(query="topic A")
y = brave.search(query="topic B")
{"a": x, "b": y}
```

## Parameter Traps

Check `ot.tools(pattern="tool", info="full")` when a call fails:

| Pack | Wrong | Correct |
|------|-------|---------|
| excel | `path=` | `filepath=` |
| excel | `sheet=` | `sheet_name=` |
| excel | `query=` | `pattern=` |
| convert | `path=` | `pattern=` + `output_dir=` |
| ground | `count=` | `max_sources=` |
| llm | `input=` | `data=` |
| llm | `instruction=` | `prompt=` |
| db | `path=` | `db_url="sqlite:///..."` |
| db | `table=` | `table_names=["list"]` |
| package | `packages="str"` | `packages=["list"]` |
| mem | `key=` | `topic=` |
| mem | `tag=` | `category=` |
| mem | `prefix=` | `topic=` (for filtering) |
| web | `max_chars=` | `max_length=` |
