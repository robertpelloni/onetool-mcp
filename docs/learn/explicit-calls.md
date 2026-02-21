# Explicit Tool Calls

OneTool's `>>>` prefix gives you explicit control over tool invocation. You write the code — the agent doesn't have to guess which tool or which parameters.

## Two Modes

### Mode 1: Snippets

Jinja2 templates invoked with `$name`. Values are plain strings; Python syntax does not apply.

```
>>> $g q=latest AI tools
>>> $pkg_npm packages=react lodash
>>> $g q="AI news"
```

- Quotes are optional and stripped (`q=abc` ≡ `q="abc"`)
- Param names support prefix abbreviation (`q` resolves to `query` if defined)
- Per-template features (e.g. pipe batch) are not snippet language features

### Mode 2: Code

Python executed directly against the tool namespace.

```
>>> brave.search(q="AI news")
>>> x = sha256(text="hello"); x
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
| `__ot`, `__onetool` | Legacy; kept for backward compat    |

**Note:** `mcp__ot__run` is NOT a valid prefix.

## Invocation Styles

### Simple Call

Direct function call after the prefix:

```
>>> sha256(text="hello")
>>> multiply(a=8472, b=9384)
```

### Code Fence

Multi-line code in a fenced block:

```
>>>
```python
metals = ["Gold", "Silver"]
results = {}
for metal in metals:
    results[metal] = brave.web_search(query=f"{metal} price")
results
```
```

## Direct MCP Call

For programmatic or explicit MCP invocation:

```
mcp__onetool__run(command='sha256(text="hello")')
```

## Complete Examples

### Simple Hash Computation

```
>>> sha256(text="hello world")
```

### Multi-step Computation with Variables

```
>>>
```python
msg = "Hello World"
sha256(text=msg)
```
```

### Loop with Multiple Tool Calls

```
>>>
```python
primes = [is_prime(n=i) for i in range(11, 21)]
primes
```
```

---

## Prompt Engineering for Tool Calls

### Pre-Call Instructions

Add context before the tool call to guide the agent:

```
Calculate the SHA-256 hash of the following text:
>>> sha256(text="hello world")
```

### Post-Call Processing

Request specific formatting or analysis after the tool result:

```
>>> brave.web_search(query="latest AI news", count=5)

Summarise the top 3 results in bullet points.
```

### Structured Output Requests

Combine tool execution with output formatting:

    >>>
    ```python
    results = {
        "hash": sha256(text="hello"),
        "reversed": reverse(text="hello"),
        "length": count_chars(text="hello")
    }
    results
    ```

    Return the results as a markdown table.

---

## Best Practices

Your system prompt should include instructions for reliable tool execution:

```yaml
system_prompt: |
  Never retry successful tool calls to get "better" results.
  If a tool call fails, report the error - do not compute the result yourself.
```

**Why these matter:**

- **No retries on success:** Agents sometimes want to "improve" results by calling the same tool again. This wastes tokens and can cause loops.
- **No manual computation on failure:** When a tool fails, agents often try to compute the answer themselves (e.g., calculating a hash or Fibonacci number). This defeats the purpose of using tools and may produce incorrect results.

---

## Troubleshooting

### "Syntax error at line 1: invalid syntax"

The prefix wasn't stripped properly. Ensure:

1. There's whitespace or a newline after the prefix
2. The code itself is valid Python

### Tool call returns unexpected result

Check that:

1. Function arguments match the expected signature
2. String arguments are properly quoted
3. For multi-line code, the last expression is what you want returned

### Code fence not recognized

Ensure:

1. Opening ` ``` ` is on its own line after the prefix
2. Closing ` ``` ` is on its own line
3. Language hint (e.g., `python`) is optional but recommended
