# Extending OneTool

Build custom tools for your projects. No OneTool source code required.

## Tool Types

OneTool supports two types of user-created tools:

| Type | When to Use | Imports |
|------|-------------|---------|
| **Extension Tool** | Most tools - no external dependencies | `from ot.*` |
| **Isolated Tool** | Tools needing external packages (numpy, pandas, etc.) | None (standalone) |

**Extension tools** (recommended) run in-process with full access to OneTool's logging, config, and secrets APIs.

**Isolated tools** run in separate subprocesses via PEP 723, providing complete dependency isolation.

## Quick Start

1. Create a tool file in `.onetool/tools/` or your own directory
2. Add `pack = "mytool"` and `__all__ = ["function_name"]`
3. Write your function with keyword-only arguments
4. Configure `tools_dir` in `onetool.yaml` to point to your tool
5. Restart the server

```python
# .onetool/tools/mytool.py
pack = "mytool"
__all__ = ["greet"]

def greet(*, name: str) -> str:
    """Greet someone by name.

    Args:
        name: The name to greet

    Returns:
        A greeting message
    """
    return f"Hello, {name}!"
```

## Next Steps

- [Extension Tools](extension-tools.md) - In-process tools with OneTool API access
- [Isolated Tools](isolated-tools.md) - Standalone tools with external dependencies
