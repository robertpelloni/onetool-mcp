# Attribution & Licensing

Guidelines for creating tools based on or inspired by external projects.

## Three-Tier Attribution Model

| Level | When to Use | Source Header | License File | Tool Doc |
|-------|-------------|---------------|--------------|----------|
| **Based on** | Code derived or ported from upstream | Required | Required in `licenses/` | Include "Based on" section |
| **Inspired by** | Similar functionality, independent code | Required | Not required | Include "Inspired by" section |
| **Original** | Clean room implementation, API wrappers | Optional `API docs:` | Not required | No attribution section |

## Source Header Format

Add attribution to the module docstring:

### Based On (Code Derived from Upstream)

```python
"""Database operations via SQLAlchemy.

Based on mcp-alchemy by Rui Machado (MPL-2.0).
https://github.com/runekaagaard/mcp-alchemy
"""
```

### Inspired By (Independent Implementation)

```python
"""Secure file operations with configurable boundaries.

Inspired by fast-filesystem-mcp by efforthye (Apache 2.0).
https://github.com/efforthye/fast-filesystem-mcp
"""
```

### Original (API Wrapper or Clean Room)

```python
"""Web search via Brave Search API.

API docs: https://api.search.brave.com/app/documentation
"""
```

## License File Requirements

For "Based on" tools, include the upstream license:

1. Copy the upstream LICENSE file to `licenses/{project-name}-LICENSE`
2. Use the exact project name from the source header
3. Example: `licenses/mcp-alchemy-LICENSE` for database tool

## Documentation Requirements

| Level | Tool Doc Attribution |
|-------|---------------------|
| Based on | Add "## Based on" section at end with project link, author, license |
| Inspired by | Add "## Inspired by" section at end with project link, author, license |
| Original | No attribution section; include "## Source" linking to API docs |

## Examples

### Based On Example (docs/reference/tools/db.md)

```markdown
## Based on

This tool is based on [mcp-alchemy](https://github.com/runekaagaard/mcp-alchemy)
by Rui Machado, licensed under MPL-2.0.
```

### Inspired By Example (docs/reference/tools/file.md)

```markdown
## Inspired by

This tool was inspired by [fast-filesystem-mcp](https://github.com/efforthye/fast-filesystem-mcp)
by efforthye, licensed under Apache 2.0.
```

### Original Example (docs/reference/tools/brave.md)

```markdown
## Source

- [Brave Search API Documentation](https://api.search.brave.com/app/documentation)
```

## Checklist

- [ ] Attribution level determined (Based on / Inspired by / Original)
- [ ] Source header in module docstring matches attribution level
- [ ] License file in `licenses/` (if "Based on")
- [ ] Tool doc attribution section matches source header
