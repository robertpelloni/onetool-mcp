# Contributing to OneTool

Internal development documentation for OneTool contributors and LLM-assisted development.

## Specifications

| Resource | Purpose |
|----------|---------|
| [Full Specifications](specs-viewer.md) | Interactive viewer for all 400+ requirements and 1300+ scenarios |
| [INDEX.md](https://github.com/beycom/onetool-mcp/blob/main/openspec/specs/INDEX.md) | Categorized specification index |

## Documentation

| Guide | Purpose |
|-------|---------|
| [Architecture](architecture.md) | Project structure and components |
| [Internal Tools](internal-tools.md) | Building bundled tools in `src/ot_tools/` |
| [Testing](testing.md) | Test markers, fixtures, CI integration |
| [Logging](logging.md) | Logging infrastructure and configuration |
| [CLI Patterns](cli-patterns.md) | Patterns for onetool and bench CLIs |
| [Attribution](attribution.md) | License handling for derived tools |

## Brand & Style

| Guide | Purpose |
|-------|---------|
| [Brand](brand/brand.md) | Brand identity, taglines, claims |
| [Terminology](brand/ref-terminology.md) | Agent vs LLM, MCP terms |
| [Documentation](docs/index.md) | MkDocs styling and best practices |

## Quick Reference

### Development Commands

```bash
just check    # Run all checks (lint, type, test)
just test     # Run tests
just lint     # Run linters
```

### Code Style

- Format with `ruff format`
- Lint with `ruff check`
- Type check with `mypy`

### Test Markers

Every test requires two markers:

| Speed Tier | Component Tag |
|------------|---------------|
| `smoke`, `unit`, `integration`, `slow` | `tools`, `core`, `serve`, `bench`, `pkg`, `spec` |

```python
@pytest.mark.smoke
@pytest.mark.serve
def test_server_starts():
    ...
```
