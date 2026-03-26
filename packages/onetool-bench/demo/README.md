# Demo Project

This directory contains demo configurations and benchmarks for OneTool.

Use these demos to:

- Test OneTool's built-in tool packs (db, file, etc.)
- Run benchmarks comparing different LLM + tool combinations
- Explore the MCP server with real data

## Quick Start

From the project root:

```bash
# Download required assets (Northwind DB)
just demo::setup

# Start the MCP server with demo config
just demo::serve

# Run benchmark scenarios interactively
just demo::bench
```

## Commands

| Command | Description |
|---------|-------------|
| `just demo::setup` | Download Northwind database |
| `just demo::serve` | Start MCP server with demo config |
| `just demo::bench` | Run benchmarks (interactive TUI picker) |
| `just demo::clean` | Remove downloaded assets |
| `just demo::logs-clean` | Truncate log files |

## Benchmark Scenarios

The `bench/` directory contains YAML files testing OneTool capabilities:

| File | Tests |
|------|-------|
| `compare.yaml` | LLM comparison — base vs MCP vs OneTool |
| `tool_db.yaml` | SQL queries against Northwind |

## Directory Structure

```text
demo/
├── .onetool/      # OneTool configuration
├── bench/         # Benchmark scenario YAML files
├── data/          # Sample data (gitignored, download via setup)
└── tmp/           # Temporary files (gitignored)
```

## Cleanup

```bash
just demo::clean   # Remove downloaded assets
```
