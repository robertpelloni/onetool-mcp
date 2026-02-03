# Isolated Tools

!!! warning "Beta Feature"
    Isolated tools are experimental and not fully tested. Consider using [Extension Tools](extension-tools.md) instead, which cover most use cases.

If your tool needs external packages that aren't bundled with OneTool (numpy, pandas, specialized libraries), use an isolated tool with PEP 723 headers.

## When to Use Isolated Tools

Use isolated tools when you need:

- External packages not in OneTool's dependencies
- Dependency version isolation (avoiding conflicts)
- Crash isolation (tool crashes don't affect the server)

For most tools, prefer [Extension Tools](extension-tools.md) instead.

## Basic Structure

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2.0.0"]
# ///
"""Tool with external dependencies."""

from __future__ import annotations

import json
import sys

import numpy as np

pack = "mytool"
__all__ = ["analyze"]

def analyze(*, data: list[float]) -> str:
    """Analyze numerical data.

    Args:
        data: List of numbers

    Returns:
        Analysis results

    Example:
        mytool.analyze(data=[1.0, 2.0, 3.0])
    """
    arr = np.array(data)
    return f"Mean: {arr.mean():.2f}, Std: {arr.std():.2f}"

# JSON-RPC main loop for subprocess communication
if __name__ == "__main__":
    _functions = {
        "analyze": analyze,
    }
    for line in sys.stdin:
        request = json.loads(line)
        func = _functions.get(request["function"])
        if func is None:
            print(json.dumps({"error": f"Unknown function: {request['function']}"}), flush=True)
            continue
        try:
            result = func(**request.get("kwargs", {}))
            print(json.dumps({"result": result}), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)
```

## Required Components

### PEP 723 Header

The script header declares Python version and dependencies:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0", "beautifulsoup4>=4.12.0"]
# ///
```

**Critical:** All imports must be declared in the `dependencies` list. If you import a module without declaring it, the subprocess will crash with `ModuleNotFoundError`.

### JSON-RPC Main Loop

The `if __name__ == "__main__":` block is required for subprocess communication:

```python
if __name__ == "__main__":
    _functions = {
        "my_function": my_function,
        "other_function": other_function,
    }
    for line in sys.stdin:
        request = json.loads(line)
        func = _functions.get(request["function"])
        if func is None:
            print(json.dumps({"error": f"Unknown function: {request['function']}"}), flush=True)
            continue
        try:
            result = func(**request.get("kwargs", {}))
            print(json.dumps({"result": result}), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)
```

Without this block, the tool fails with "Worker closed unexpectedly".

## Limitations

Isolated tools cannot:

- Access secrets via `get_secret()` - use environment variables instead
- Access OneTool config via `get_tool_config()` - hardcode values
- Use structured logging with LogSpan
- Call other tools via `call_tool()` or `get_pack()`

This trade-off provides full dependency isolation and crash safety.

## Testing Locally

Verify your isolated tool works before deploying:

```bash
uv run your_tool.py
```

This ensures all dependencies resolve correctly.

## Creating with Scaffold

Use the scaffold tool to generate isolated tools:

```python
scaffold.create(name="numpy_tool", template="isolated")
```

## Complete Example

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0"]
# ///
"""Web scraping tool with isolated dependencies."""

from __future__ import annotations

import json
import sys

pack = "scraper"
__all__ = ["fetch_title"]

def fetch_title(*, url: str) -> str:
    """Fetch the title of a web page.

    Args:
        url: URL to fetch

    Returns:
        The page title or error message

    Example:
        scraper.fetch_title(url="https://example.com")
    """
    import httpx

    try:
        response = httpx.get(url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()

        # Simple title extraction
        text = response.text
        if "<title>" in text and "</title>" in text:
            start = text.index("<title>") + 7
            end = text.index("</title>")
            return text[start:end].strip()
        return "No title found"
    except httpx.HTTPError as e:
        return f"HTTP error: {e}"
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    _functions = {
        "fetch_title": fetch_title,
    }
    for line in sys.stdin:
        request = json.loads(line)
        func = _functions.get(request["function"])
        if func is None:
            print(json.dumps({"error": f"Unknown function: {request['function']}"}), flush=True)
            continue
        try:
            result = func(**request.get("kwargs", {}))
            print(json.dumps({"result": result}), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)
```

## Checklist

- [ ] PEP 723 header with all dependencies declared
- [ ] `pack = "..."` declaration
- [ ] `__all__ = [...]` listing exports
- [ ] All functions use keyword-only arguments (`*,`)
- [ ] Complete docstrings with Args, Returns, Example
- [ ] JSON-RPC main loop with all functions registered
- [ ] Tested locally with `uv run your_tool.py`
