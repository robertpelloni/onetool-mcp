# OneTool MCP - Project Structure Map

MCP server with single `run` tool for LLM Python code execution.

---

## Source Code Structure

### Core Framework (`src/ot/`)

Core execution engine, configuration, logging, and inter-tool API.

| Module | Purpose | Key Files |
|--------|---------|-----------|
| `executor/` | Code execution engine | `runner.py`, `validator.py`, `tool_loader.py` |
| `config/` | Configuration management | `loader.py`, `models.py`, `secrets.py` |
| `logging/` | LogSpan structured logging | `span.py`, `entry.py`, `format.py` |
| `registry/` | AST-based tool discovery | `registry.py`, `parser.py`, `models.py` |
| `meta/` | Metadata, health, and introspection helpers | `_help.py`, `_stats.py`, `_config_health.py` |
| `proxy/` | External MCP server support | `manager.py` |

### Tool Packs (`src/ottools/`)

Built-in core packs bundled with base install.

| Pack | Description | Key Functions |
|------|-------------|---------------|
| `ot_forge.py` | Extension scaffolding and validation | `create_ext()`, `validate_ext()`, `install_skill()` |
| `ot_llm.py` | LLM-powered transformation tools | `transform()`, `transform_file()` |
| `ot_secrets.py` | Secret management utilities | `init()`, `encrypt()`, `audit()` |
| `ot_timer.py` | Named stopwatch timers | `start()`, `elapsed()`, `list()` |
| `server.py` | MCP server metadata/resources | prompt/resource helpers |
| `skills.py` | Skills loading and lookup | skill registry helpers |

### MCP Server (`src/onetool/`)

Standalone CLI wrapper.

| File | Purpose |
|------|---------|
| `cli.py` | onetool CLI entry point and commands |

### Benchmark Harness (`packages/onetool-bench/src/bench/`)

Performance benchmarking CLI (internal, not distributed with `onetool-mcp`).

| File | Purpose |
|------|---------|
| `cli.py` | Benchmark CLI |
| `run.py` | Benchmark execution entry |
| `harness/runner.py` | Scenario/task execution loop |
| `reporter.py` | Console and summary reporting |

### Dev Extras (`src/otdev/`) — optional `[dev]`

Tool packs for developer-focused features. Installed via `pip install onetool-mcp[dev]`.

| Pack | Description |
|------|-------------|
| `tools/context7.py` | Context7 documentation lookup |
| `tools/db.py` | Database operations (SQLAlchemy) |
| `tools/diagram.py` | Diagram generation (Kroki) |
| `tools/package.py` | Package version checking |
| `tools/ripgrep.py` | Fast code search |
| `tools/webfetch.py` | Web scraping (trafilatura) |
| `tools/worktree.py` | Git worktree management for parallel agents |

### Util Extras (`src/otutil/`) — optional `[util]`

Tool packs for document and file utilities. Installed via `pip install onetool-mcp[util]`.

| Pack | Description |
|------|-------------|
| `tools/brave.py` | Brave web search |
| `tools/convert.py` | Document conversion (PDF/DOCX/PPTX→MD) |
| `tools/excel.py` | Excel file handling |
| `tools/file.py` | File operations |
| `tools/ground.py` | Gemini grounding search |
| `tools/tavily.py` | Tavily AI search and URL extraction |

---

## Configuration Files

| File | Purpose | Key Sections |
|------|---------|--------------|
| `pyproject.toml` | Dependencies, scripts, tools | `[project]`, `[tool.ruff]`, `[tool.pytest]` |
| `justfile` | Dev commands | `install`, `check`, `test`, `dev` |
| `onetool.yaml` | OneTool config (optional) | Tool-specific settings |

---

## Tests

Tests mirror the source package structure:

| Source package | Test root |
|----------------|-----------|
| `src/ot/`, `src/onetool/` | `tests/` |
| `src/ottools/` | `tests/ottools/` |
| `src/otdev/` | `tests/otdev/` |
| `src/otutil/` | `tests/otutil/` |

Each test root has the same layout:

| Sub-directory | Test Type | Markers |
|---------------|-----------|---------|
| `smoke/` | Fast sanity checks | `@pytest.mark.smoke` |
| `unit/` | Unit tests | `@pytest.mark.unit` |
| `integration/` | Integration tests | `@pytest.mark.integration` |
| `slow/` | Long-running tests | `@pytest.mark.slow` |

**Component markers:** `core`, `bench`, `serve`, `tools`

**Rule:** Always place tests under the root that matches the source package.
A test for `src/otdev/tools/worktree.py` → `tests/otdev/unit/tools/test_worktree.py`.

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
- Tool pack → `src/ottools/<pack>.py`
- Core executor → `src/ot/executor/runner.py`
- MCP server runtime → `src/ot/server.py`
- onetool CLI → `src/onetool/cli.py`
- Tests → `tests/otdev/`, `tests/ottools/`, `tests/otutil/`, or `tests/` (match source package)
- Specs → `openspec/specs/<feature>/spec.md`

**Need to understand:**
- Architecture → `dev/project/arch/index.md`
- How to create tools → `dev/project/guides/creating-tools.md`
- Testing guide → `dev/practices/testing.md`
- Git workflow → `dev/practices/git.md`

---

**Last updated:** 2026-02-09
