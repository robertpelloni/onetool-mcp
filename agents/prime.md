# OneTool MCP

MCP server with single `run` tool for LLM Python code execution.

## Source

- `src/ot/` - Core (executor, config, logging, inter-tool API)
- `src/ot_tools/` - Tools (db, excel, web, file)
- `src/onetool/` - MCP server CLI
- `src/bench/` - Benchmark CLI

## Config

- `pyproject.toml` - deps, scripts, tools
- `justfile` - dev tasks (`just check`, `just demo::*`)
- `agents/rules.md` - coding/testing rules

## Work in Progress

- `wip/test-results/` - Sanity test outputs
- `wip/issues/` - Issues found during testing
- `wip/consult/` - Consultation findings
