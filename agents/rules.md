# Rules

**IMPORTANT:** All code changes must update: code, tests, readme, docs and specs.

## Paths

- `/docs` - user docs
- `/openspec/specs` - feature specs
- `/openspec/changes` - pending proposals
- `/openspec/archive` - completed proposals

## Spec Naming

| Pattern | Example | Description |
|---------|---------|-------------|
| `{cli}` | `bench` | Main spec for a CLI (`ot-{cli}`) |
| `{cli}-{feature}` | `bench-config` | CLI feature spec |
| `serve-{feature}` | `serve-configuration` | MCP server feature spec |
| `tool-{name}` | `tool-brave-search` | Built-in tool spec |
| `_nf-{name}` | `_nf-observability` | Non-functional / cross-cutting spec |

## Models

- Bench default: `openai/gpt-5-mini`
- YAML bench: use `google/gemini-3-flash-preview` in `defaults.model`

## Style

- Australian English (colour, behaviour) except code identifiers (color, initialize)
- No em-dashes, use hyphens
- No backward compat - delete unused code completely

## CLI

- Use Rich with `highlight=False` for all CLIs (disables auto syntax highlighting)

## Python

- `__init__.py` required in `src/` packages
- `__init__.py` required in `tests/` subdirs (empty, avoids name collisions)

## Test URLs

Do not use `example.com` - it does not resolve in this environment. Use `https://www.wikipedia.org/` instead.

## Testing

Always use `uv run pytest` for proper dependency resolution (never bare `pytest` or `python -m pytest`).
Shortcut: `just test` runs the full suite.
Markers required: speed (`smoke`|`unit`|`integration`|`slow`) + component (`core`|`bench`|`serve`)
Principles: lean tests, DRY fixtures in `conftest.py`, test behaviour not implementation

## Path Resolution

Paths relative to `.onetool/` (config, databases, logs, stats) must use `resolve_ot_path()` from `ot.meta` or `_resolve_onetool_relative_path()` from config models - never `expand_path()` or `Path.expanduser()`. These resolvers honour `OT_GLOBAL_DIR` and project-level `.onetool/` directories. Use relative defaults (e.g. `mem.db`) not absolute ones (e.g. `~/.onetool/mem.db`). `expand_path()` is only for user-supplied file paths (spreadsheets, arbitrary files on disk).

## Logging

```python
with LogSpan(span="component.operation", key="value") as s:
    s.add("resultCount", len(result))
```

Span naming: `{component}.{operation}` (e.g., `brave.search.web`)
