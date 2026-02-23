# Creating Tools

Guide for creating tools bundled with OneTool in `src/ottools/`.

---

## File Location

```
src/ottools/<name>.py
```

One file per pack. The filename doesn't need to match the pack name (e.g., `brave_search.py` declares `pack = "brave"`).

---

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

---

## Minimal Tool Example

```python
"""Short description of what this pack does."""

from __future__ import annotations

pack = "mytool"
__all__ = ["search", "list_items"]


def search(*, query: str, count: int = 10) -> dict[str, list[dict[str, str]]]:
    """Search for items.

    Args:
        query: The search query.
        count: Number of results (1-100).

    Returns:
        Dict with results key containing list of result dicts.
    """
    return {"results": []}


def list_items(*, category: str = "all") -> list[str]:
    """List available items.

    Args:
        category: Filter by category.

    Returns:
        List of item names.
    """
    return []
```

Usage: `mytool.search(query="test")`, `mytool.list_items(category="web")`

---

## Required Elements

| Element | Purpose |
|---------|---------|
| `pack = "name"` | Dot-notation namespace (must be before imports) |
| `__all__ = [...]` | Public functions for registry |
| Type hints on all functions | mypy strict mode |
| Google-style docstrings | Registry extracts for introspection |
| Keyword-only args (`*,`) | All tool functions use keyword args |

---

## Pack Declaration

The `pack` variable enables dot notation:

```python
pack = "brave"  # Exposes brave.search(), brave.news()
pack = "web"    # Exposes web.fetch(), web.fetch_batch()
```

**Important**: The pack declaration must appear before other imports (except `from __future__`).

---

## Export Control

Use `__all__` to declare which functions are exposed as tools:

```python
__all__ = ["search", "fetch", "batch"]  # Only these become tools
```

Without `__all__`, imported functions would be incorrectly exposed as tools.

---

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

---

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

---

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

See [Logging](../../practices/logging.md) for detailed LogSpan patterns.

---

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

---

## Return Types

Tools return native Python types (str, dict, list). The framework handles serialisation to JSON/YAML/raw based on the caller's `__format__` setting.

---

## Dependencies

### External Dependencies

Declare external dependencies with install hints:

```python
__ot_requires__ = {
    "cli": [("rg", "brew install ripgrep")],         # External binaries
    "lib": [("openpyxl", "pip install openpyxl")],    # Python packages
    "secrets": [("BRAVE_API_KEY", "Get from brave.com")],  # API keys
}
```

### Accessing Secrets

Access secrets at runtime:

```python
from ot.config import get_secret

api_key = get_secret("BRAVE_API_KEY")
if not api_key:
    raise ValueError("BRAVE_API_KEY not configured")
```

### Lazy Imports for Optional Dependencies

Tools with optional dependencies must use lazy imports inside functions:

**Wrong** - fails at module load:

```python
import sqlalchemy  # BREAKS tool loading if sqlalchemy not installed

def query(*, sql: str) -> str:
    engine = sqlalchemy.create_engine("sqlite:///:memory:")
    ...
```

**Correct** - lazy import inside function:

```python
def query(*, sql: str) -> str:
    """Query using SQLAlchemy."""
    try:
        import sqlalchemy
    except ImportError as e:
        raise ImportError(
            "sqlalchemy is required for query. Install with: pip install sqlalchemy"
        ) from e

    engine = sqlalchemy.create_engine("sqlite:///:memory:")
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

---

## Path Handling

| Function | Import From | Resolves Relative To |
|----------|-------------|----------------------|
| `resolve_cwd_path()` | `ot.paths` | Project directory (`OT_CWD`) |
| `resolve_ot_path()` | `ot.paths` | Config directory (`.onetool/`) |
| `get_effective_cwd()` | `ot.paths` | Returns project directory |
| `expand_path()` | `ot.paths` | Only expands `~` |

**Example:**

```python
from ot.paths import resolve_cwd_path

def read_file(*, path: str) -> str:
    resolved = resolve_cwd_path(path)
    return resolved.read_text()
```

**Never use** `Path.expanduser()` or bare `expand_path()` for project-relative paths. Use `resolve_cwd_path()` for user-supplied paths and `resolve_ot_path()` for `.onetool/`-relative paths (databases, logs, stats). Use relative defaults (e.g., `mem.db` not `~/.onetool/mem.db`).

---

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

See [Tool Configuration](tool-configuration.md) for detailed configuration patterns.

---

## Testing Your Tool

```python
# tests/unit/test_mytool.py
import pytest
from ottools.mytool import search

@pytest.mark.unit
@pytest.mark.tools
class TestSearch:
    def test_empty_query_returns_empty(self):
        result = search(query="")
        assert result == {"results": []}
```

See [Testing](../../practices/testing.md) for markers, fixtures, and patterns.

---

## Large Packs: Multi-File Layout

When a pack grows beyond ~500 lines, split it into a private package using the
`convert.py` / `_convert/` convention. The tool loader discovers only `*.py`
files in the tools directory; private packages (underscore prefix) are
implementation detail.

### Layout

```
src/otutil/tools/
├── mem.py          ← discovered by tool loader (pack = "mem", __all__, __ot_requires__)
└── _mem/           ← private implementation package (not discovered directly)
    ├── __init__.py ← re-exports everything; also used for direct imports in tests
    ├── config.py
    ├── db.py
    ├── write.py
    └── ...
```

### Facade file (`mem.py`)

```python
"""Tool description."""
from __future__ import annotations

pack = "mem"

# Only public functions go here – these become MCP tools.
__all__ = ["write", "read", "search", ...]

__ot_requires__ = {"lib": [("openai", "pip install openai")]}

# Import public API (and any private symbols needed by tests / type checkers)
from otutil.tools._mem import (
    write, read, search, ...,  # public
    _close_connection, Config, ...,  # private – available but not in __all__
)
```

### Private package (`_mem/__init__.py`)

Keeps `pack`, `__all__` (full list including privates), and imports from
submodules. This is what tests import when they need internal symbols:

```python
from otutil.tools._mem import Config, _close_connection
```

### Key rules

- Facade `__all__` lists **only public tool functions** — private symbols are
  importable but not exposed as MCP tools.
- Internal submodules use relative imports (`from .config import Config`).
- Tests that patch submodule internals use the `_mem` path:
  `@patch("otutil.tools._mem.write._get_connection")`.
- The underscore prefix (`_mem/`) is what prevents the loader from treating
  the package as a second pack registration.

---

## Checklist

- [ ] File at `src/ottools/<name>.py`
- [ ] Module docstring with description
- [ ] `pack = "..."` before imports
- [ ] `__all__ = [...]` listing exports
- [ ] `__ot_requires__` declared if external dependencies needed
- [ ] All functions use keyword-only args (`*,`)
- [ ] Type hints on all functions
- [ ] Complete Google-style docstrings (Args, Returns, Example)
- [ ] `LogSpan` for operations with external calls
- [ ] Error handling returning strings (not raising exceptions)
- [ ] Lazy imports for optional dependencies
- [ ] Secrets accessed via `get_secret()` from `ot.config`
- [ ] Path resolution using `resolve_cwd_path()` or `resolve_ot_path()`
- [ ] `Config` class if tool has settings
- [ ] Unit tests with `@pytest.mark.unit` + `@pytest.mark.tools`
- [ ] Integration tests if external APIs involved
- [ ] Spec at `openspec/specs/tool-<name>/spec.md` (for non-trivial tools)
- [ ] Attribution level determined (see [Attribution](attribution.md))
- [ ] Update `src/ot/config/global_templates/agent-hints.md` if adding user-facing tools
- [ ] `just check` passes

---

**Related:**
- [Tool Configuration](tool-configuration.md) - Adding config to tools
- [Logging](../../practices/logging.md) - LogSpan patterns
- [Testing](../../practices/testing.md) - Test markers and fixtures
- [Attribution](attribution.md) - License handling for derived tools
