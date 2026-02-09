<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

Read dev/agents/hints.md for quick reference (commands, rules, project structure).
Read dev/agents/project-map.md for detailed project structure.
Read dev/index.md for complete dev docs navigation.

## MCP Servers

Two OneTool versions are configured:

- **otd**: Local dev version. Use `mcp__onetool-dev__run` only when explicitly requested
- **ot**: Stable version . Use `__ot` for all normal operations (default)
Use stable version unless "dev" is explicitly mentioned.

## Commands

Use `just` (not `make`) for project commands:

```bash
just check    # Run all checks (lint, type, test)
just test     # Run tests
just lint     # Run linters
```

## Tools

### File Search
Use OneTool ripgrep (50x faster than find+grep, with line numbers):
- Search for pattern in files: `ot.ripgrep.search(pattern="onetool", path="src/", glob="*.py")`
- List files only: `ripgrep.search(pattern="TODO", path=".", glob="*.{py,yaml}")`
- Count matches: `ripgrep.count(pattern="import", path="src/", file_type="py")`

### Tools - Web Search
- Web search: `$g q=query one|query two|query three`


