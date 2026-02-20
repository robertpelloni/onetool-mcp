# Registry System

The registry discovers tools without importing them by scanning Python files
with AST. For each file it extracts:

- Pack name and public functions
- Function signatures, docstrings, type hints
- `@tool` decorator metadata
- Config class definitions
- `__ot_requires__` dependency declarations

The registry is cached and invalidated by file mtime changes.

## Sequence Diagram

```mermaid
sequenceDiagram
    participant C as Caller
    participant R as ToolRegistry
    participant A as AST Parser
    participant M as ToolInfo Model

    C->>R: get_registry()
    R->>R: Check cache (mtime-based)

    alt Cache miss or stale
        R->>R: scan_directory(ottools/)
        loop Each *.py file
            R->>A: Parse file with ast.parse()
            A-->>R: AST tree

            R->>R: Extract pack = "name"
            R->>R: Extract __all__ exports
            R->>R: Extract __ot_requires__

            loop Each public function
                R->>R: Extract signature & type hints
                R->>R: Extract docstring
                R->>R: Check @tool decorator
                R->>M: Create ToolInfo(name, pack, args, ...)
                M-->>R: ToolInfo stored
            end

            opt Has Config class
                R->>R: Extract Config source
                R->>M: Attach config_schema
            end
        end
        R->>R: Cache registry
    end

    R-->>C: ToolRegistry (all ToolInfo objects)

    Note over C,M: Registry used for:<br/>- Introspection (ot.tools())<br/>- Namespace building<br/>- Parameter resolution<br/>- Validation
```


## ToolInfo Structure

Each discovered tool is stored as a `ToolInfo` with:

| Field | Description |
|-------|-------------|
| `name` | Full qualified name (e.g., `brave.search`) |
| `pack` | Pack namespace (e.g., `brave`) |
| `module` | Python module path |
| `signature` | Full function signature |
| `description` | From docstring |
| `args` | List of ArgInfo (name, type, default, description) |
| `config_schema` | Config class source (if present) |
| `requires` | `__ot_requires__` declarations |

## Key Files

| File | Role |
|------|------|
| `src/ot/registry/registry.py` | Scanner and cache logic |
| `src/ot/registry/models.py` | ToolInfo, ArgInfo data models |
