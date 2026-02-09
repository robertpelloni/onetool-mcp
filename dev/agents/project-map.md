# OneTool MCP - Project Structure Map

MCP server with single `run` tool for LLM Python code execution.

---

## Source Code Structure

### Core Framework (`src/ot/`)

Core execution engine, configuration, logging, and inter-tool API.

| Module | Purpose | Key Files |
|--------|---------|-----------|
| `executor/` | Code execution engine | `runner.py`, `validator.py` |
| `config/` | Configuration management | `loader.py`, `schema.py` |
| `logging/` | LogSpan structured logging | `logspan.py` |
| `registry/` | AST-based tool discovery | `registry.py`, `discovery.py` |
| `meta/` | Metadata and paths | `paths.py`, `version.py` |
| `proxy/` | External MCP server support | `client.py`, `server.py` |

### Tool Packs (`src/ot_tools/`)

Built-in tool packs (15+ packs, 100+ tools).

| Pack | Description | Key Functions |
|------|-------------|---------------|
| `brave.py` | Web search | `search()`, `web_search()` |
| `db.py` | Database operations | `query()`, `connect()` |
| `excel.py` | Excel file handling | `read()`, `write()` |
| `file.py` | File operations | `read()`, `write()`, `list()` |
| `git.py` | Git operations | `status()`, `commit()` |
| `mem.py` | Vector memory | `store()`, `search()` |
| `pkg.py` | Package management | `install()`, `search()` |
| `ripgrep.py` | Fast code search | `search()`, `count()` |
| `screenshot.py` | Screen capture | `capture()` |
| `shell.py` | Shell commands | `run()` |
| `sys.py` | System info | `info()`, `platform()` |

### MCP Server (`src/onetool/`)

MCP server CLI and implementation.

| File | Purpose |
|------|---------|
| `server.py` | MCP server entry point |
| `handlers.py` | Request handlers |
| `__main__.py` | CLI entry point |

### Benchmark Harness (`src/bench/`)

Performance benchmarking CLI.

| File | Purpose |
|------|---------|
| `cli.py` | Benchmark CLI |
| `runner.py` | Benchmark execution |
| `reporters.py` | Results reporting |

---

## Configuration Files

| File | Purpose | Key Sections |
|------|---------|--------------|
| `pyproject.toml` | Dependencies, scripts, tools | `[project]`, `[tool.ruff]`, `[tool.pytest]` |
| `justfile` | Dev commands | `install`, `check`, `test`, `dev` |
| `onetool.yaml` | OneTool config (optional) | Tool-specific settings |

---

## Tests

| Directory | Test Type | Markers |
|-----------|-----------|---------|
| `tests/smoke/` | Fast sanity checks | `@pytest.mark.smoke` |
| `tests/unit/` | Unit tests | `@pytest.mark.unit` |
| `tests/integration/` | Integration tests | `@pytest.mark.integration` |
| `tests/slow/` | Slow tests | `@pytest.mark.slow` |

**Component markers:** `core`, `bench`, `serve`, `tools`

---

## Documentation

| Directory | Purpose | Audience |
|-----------|---------|----------|
| `dev/` | Developer documentation | Contributors, AI agents |
| `docs/` | User-facing docs | End users |
| `openspec/` | Specifications | Contributors |

---

## Developer Resources

| File | Purpose |
|------|---------|
| `dev/agents/hints.md` | Quick reference for agents |
| `dev/agents/project-map.md` | This file - project structure |
| `dev/practices/commit-scopes.md` | Conventional commit scopes |
| `dev/practices/git.md` | Git workflow, branches, tags |
| `CLAUDE.md` | Instructions for Claude Code |
| `README.md` | Project overview |

---

## Work in Progress

| Directory | Purpose |
|-----------|---------|
| `wip/test-results/` | Sanity test outputs |
| `wip/issues/` | Issues found during testing |
| `wip/consult/` | Consultation findings |
| `wip/bench/` | Benchmark results |

---

## Quick Navigation

**Need to modify:**
- Tool pack → `src/ot_tools/<pack>.py`
- Core executor → `src/ot/executor/runner.py`
- MCP server → `src/onetool/server.py`
- Tests → `tests/{smoke,unit,integration}/`
- Specs → `openspec/specs/<feature>/spec.md`

**Need to understand:**
- Architecture → `dev/project/arch/index.md`
- How to create tools → `dev/project/guides/creating-tools.md`
- Testing guide → `dev/practices/testing.md`
- Git workflow → `dev/practices/git.md`

---

**Last updated:** 2026-02-09
