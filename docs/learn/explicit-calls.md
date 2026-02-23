# Explicit Tool Calls

OneTool's `>>>` prefix gives you explicit control over tool invocation. You write the code — the agent doesn't have to guess which tool or which parameters.

## Snippet Mode vs Code Mode

### Snippet Mode

Jinja2 templates invoked with `$name`. Values are plain strings; Python syntax does not apply.

```
>>> $g q=latest AI tools
>>> $pkg_npm packages=react lodash
>>> $g q="AI news"
```

- Quotes are optional and stripped (`q=abc` ≡ `q="abc"`)
- Param names support prefix abbreviation (`q` resolves to `query` if defined)
- Per-template features (e.g. pipe batch) are not snippet language features

### Code Mode

Python executed directly against the tool namespace.

```
>>> brave.search(q="AI news")
>>> x = foo(text="hello"); x
```

- Python syntax applies: strings must be quoted
- Short param names work: `q` resolves to `query` (pack proxy prefix resolution)
- Keyword arguments only: `fn(key="val")` not `fn("val")`

## Trigger Hierarchy

| Prefix              | Role                                |
| ------------------- | ----------------------------------- |
| `>>>`               | Recommended; Python REPL symbol     |
| `__run`             | Systematic short form (`__(tool)`)  |
| `mcp__onetool__run` | Canonical MCP name                  |
| `__ot`, `__onetool` | **Deprecated** — kept for backward compat, use `>>>` instead |

**Note:** `mcp__ot__run` is NOT a valid prefix.

## Invocation Styles

### Simple Call

Direct function call after the prefix:

```
>>> foo(text="hello")
>>> multiply(a=8472, b=9384)
```

### Code Fence

Multi-line code in a fenced block:

````
>>>
```python
metals = ["Gold", "Silver"]
results = {}
for metal in metals:
    results[metal] = brave.web_search(query=f"{metal} price")
results
```
````

## Direct MCP Call

For programmatic or explicit MCP invocation:

```
mcp__onetool__run foo(text="hello")
```

## Complete Examples

### Simple Hash Computation

```
>>> foo(text="hello world")
```

### Multi-step Computation with Variables

````
>>>
```python
msg = "Hello World"
foo(text=msg)
```
````

### Loop with Multiple Tool Calls

````
>>>
```python
primes = [is_prime(n=i) for i in range(11, 21)]
primes
```
````

---

## Prompt Engineering for Tool Calls

### Pre-Call Instructions

Add context before the tool call to guide the agent:

```
Process the following text:
>>> foo(text="hello world")
```

### Post-Call Processing

Request specific formatting or analysis after the tool result:

```
>>> brave.web_search(query="latest AI news", count=5)

Summarise the top 3 results in bullet points.
```

### Structured Output Requests

Combine tool execution with output formatting:

````
>>>
```python
results = {
    "hash": foo(text="hello"),
    "reversed": reverse(text="hello"),
    "length": count_chars(text="hello")
}
results
```
````

Return the results as a markdown table.

