# Project Context

## Purpose

OneTool is an MCP server exposing a single `run` tool for AI-assisted development. It addresses MCP's token bloat (~46K tokens for multiple tools, 96% reduction) by moving execution to a cheap LLM.

**Architecture**: `run request` → `LLM codegen` → `Host exec` → `Return` (~2K tokens, 1 call)

## Stack

Python 3.11+, FastMCP, OpenAI SDK (OpenRouter), Typer, Pydantic, YAML config

## Full Documentation

- [Dev Docs](../dev/index.md) — architecture, guides, practices, configuration
- [Specifications Index](specs/INDEX.md) — all OpenSpec specifications

---

*Last Updated: 2026-02-09*
