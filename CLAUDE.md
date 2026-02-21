
Read dev/agents/hints.md for quick reference (commands, rules, project structure).
Read dev/agents/project-map.md for detailed project structure.
Read dev/index.md for complete dev docs navigation.

## MCP Servers

Two OneTool versions are configured:

- **otd**: Local dev version. Use `mcp__onetool-dev__run` only when explicitly requested
- **ot**: Stable version . Use `>>>` for all normal operations (default)
Use stable version unless "dev" is explicitly mentioned.

## Commands

Use `just` (not `make`) for project commands:

```bash
just check    # Run all checks (lint, type, test)
just test     # Run tests
just lint     # Run linters
```

## OpenSpec Workflow

Use `/opsx:new` for changes that define new user-facing behaviour or modify
existing contracts:

✅ Requires OpenSpec:
- New tool packs or extras ([dev], [util], [xero])
- New CLI commands or flags
- Changes to config format, file locations, or schema
- Changes to MCP tool interface or server behaviour
- New registry or tool discovery mechanism

❌ No OpenSpec needed:
- Bug fixes and correctness improvements
- Performance improvements
- Adding or improving tests
- Internal refactors with no behaviour change
- Cherry-picking improvements from other branches
- Documentation and spec updates
- Build/tooling changes (pyproject.toml, justfile)

## Tools

### File Search
Use OneTool ripgrep (50x faster than find+grep, with line numbers):
- Search for pattern in files: `ot.ripgrep.search(pattern="onetool", path="src/", glob="*.py")`
- List files only: `ripgrep.search(pattern="TODO", path=".", glob="*.{py,yaml}")`
- Count matches: `ripgrep.count(pattern="import", path="src/", file_type="py")`

### Tools - Web Search
- Web search: `$g q=query one|query two|query three`
