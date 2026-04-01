# Project Context

## Purpose

OneTool Extras provides domain-specific tool packs for onetool-mcp, packaged as standalone MCP servers. Each extra installs independently alongside the core server, keeping token costs low by exposing only the tools needed for a given workflow.

**Architecture**: `onetool-mcp` (core) + `onetool-util` and/or `onetool-dev` (extras, optional)

## Stack

Python 3.12+, FastMCP, Pydantic, httpx, SQLAlchemy, Typer, PyYAML

## Packages

| Package | MCP Server | Tool Packs |
|---------|------------|------------|
| `otutil` | `onetool-util` | file, excel, brave, convert, ground, knowledge, mem, ot_image, tavily |
| `otdev` | `onetool-dev` | ripgrep, webfetch, package, db, diagram, context7 |
| `otcommon` | (shared) | Registry, tool discovery utilities |
| `ot` | (shared) | Core framework (executor, config, logging, proxy) |
| `onetool-pack` | `packages/onetool-pack/` | Shared utilities for pack authors (logging, config, caching, HTTP, paths, batch, text) |
| `onetool-bench` | `packages/onetool-bench/` | Benchmark harness for MCP server testing |

## Full Documentation

- [Dev Docs](../dev/index.md) — architecture, guides, practices, configuration
- [Specifications Index](specs/INDEX.md) — all OpenSpec specifications

---

*Last Updated: 2026-02-18*
