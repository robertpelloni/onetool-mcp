# Internal Tools

Guide for creating tools bundled with OneTool in `src/ot_tools/`.

## File Structure

Each tool file follows this structure:

```python
"""Tool module docstring.

Brief description of what the tool does.
Requirements (e.g., "Requires MY_API_KEY in secrets.yaml").
"""

from __future__ import annotations

# Pack declaration MUST be before other imports
pack = "mytools"

# Export only these functions as tools
__all__ = ["search", "fetch", "batch"]

from typing import Any, Literal

from ot.config.secrets import get_secret
from ot.logging import LogSpan
```

## Pack Declaration

The `pack` variable enables dot notation:

```python
pack = "brave"  # Exposes brave.search(), brave.news()
pack = "web"    # Exposes web.fetch(), web.fetch_batch()
```

**Important**: The pack declaration must appear before other imports (except `from __future__`).

## Export Control

Use `__all__` to declare which functions are exposed as tools:

```python
__all__ = ["search", "fetch", "batch"]  # Only these become tools
```

Without `__all__`, imported functions would be incorrectly exposed as tools.

## Function Signatures

All tool functions MUST use keyword-only arguments:

```python
# CORRECT
def search(
    *,
    query: str,
    count: int = 10,
) -> str:
    """Search for items."""
    ...

# WRONG - will cause runtime errors
def search(query: str, count: int = 10) -> str:
    ...
```

## Docstring Format

All public tool functions MUST include complete docstrings:

```python
def search(
    *,
    query: str,
    count: int = 10,
) -> str:
    """Search for items.

    Args:
        query: The search query string
        count: Number of results (1-20, default: 10)

    Returns:
        Formatted search results

    Example:
        mytools.search(query="python async", count=5)
    """
```

## Logging with LogSpan

All public tool functions must use LogSpan:

```python
from ot.logging import LogSpan

def search(*, query: str) -> list[dict]:
    """Search for items."""
    with LogSpan(span="mytools.search", query=query) as s:
        results = do_search(query)
        s.add("resultCount", len(results))
        return results  # Return native type directly
```

## Error Handling

Return error messages as strings, don't raise exceptions:

```python
def search(*, query: str) -> str:
    with LogSpan(span="mytools.search", query=query) as s:
        api_key = get_secret("MY_API_KEY")
        if not api_key:
            s.add("error", "no_api_key")
            return "Error: MY_API_KEY not configured"

        try:
            result = call_api(query)
            return result
        except APIError as e:
            s.add("error", str(e))
            return f"API error: {e}"
```

## Lazy Imports for Optional Dependencies

Tools with optional dependencies must use lazy imports inside functions:

**Wrong** - fails at module load:

```python
import duckdb  # BREAKS tool loading if duckdb not installed

def search(*, query: str) -> str:
    conn = duckdb.connect(":memory:")
    ...
```

**Correct** - lazy import inside function:

```python
def search(*, query: str) -> str:
    """Search using DuckDB."""
    try:
        import duckdb
    except ImportError as e:
        raise ImportError(
            "duckdb is required for search. Install with: pip install duckdb"
        ) from e

    conn = duckdb.connect(":memory:")
    ...
```

For type hints, use `TYPE_CHECKING`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI

def _get_client() -> "OpenAI":
    """Get OpenAI client with lazy import."""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError(
            "openai is required. Install with: pip install openai"
        ) from e
    return OpenAI(api_key=get_secret("OPENAI_API_KEY"))
```

## Configuration Access

Tools can define a `Config` class that is automatically discovered:

```python
from pydantic import BaseModel, Field
from ot.config import get_tool_config

class Config(BaseModel):
    timeout: float = Field(default=30.0, ge=1.0, le=120.0)

def search(*, query: str, timeout: float | None = None) -> str:
    if timeout is None:
        config = get_tool_config("mytool", Config)
        timeout = config.timeout
    # ...
```

## Path Resolution

| Function | Import From | Resolves Relative To |
|----------|-------------|----------------------|
| `resolve_cwd_path()` | `ot.paths` | Project directory (`OT_CWD`) |
| `resolve_ot_path()` | `ot.paths` | Config directory (`.onetool/`) |
| `get_effective_cwd()` | `ot.paths` | Returns project directory |
| `expand_path()` | `ot.paths` | Only expands `~` |

## Checklist

- [ ] Module docstring with description
- [ ] `pack = "..."` before imports
- [ ] `__all__ = [...]` listing exports
- [ ] All functions use keyword-only arguments (`*,`)
- [ ] Complete docstrings with Args, Returns, Example
- [ ] LogSpan logging for all operations
- [ ] Error handling returning strings
- [ ] Secrets in `secrets.yaml`
- [ ] Dependencies in `pyproject.toml` (or lazy imports)
- [ ] Attribution level determined (see [Attribution](attribution.md))
