# Agent Quick Reference

**Primary use:** Load this file for immediate context about the project.

**For detailed info:** Use `mem.search(query="your topic")` or browse `dev/` directory.

---

## Common Commands

| Task | Command | Notes |
|------|---------|-------|
| Run all checks | `just check` | Lint + type + test |
| Run tests | `just test` | Full test suite |
| Run smoke tests | `uv run pytest -m smoke` | Fast checks only |
| Run specific component | `uv run pytest -m serve` | By marker |
| Dev server | `just dev` | MCP server in dev mode |
| Install deps | `just install` | UV install |

---

## Project Structure

```
src/
  ot/           Core framework (executor, config, logging, registry)
  ottools/     Built-in tool packs (15+ packs, 100+ tools)
  onetool/      MCP server CLI
  bench/        Benchmark harness CLI
  otdev/        [dev] extra: context7, db, diagram, package, ripgrep, web
  otutil/       [util] extra: brave, convert, excel, file, ground

tests/          All tests (smoke, unit, integration)
dev/            Developer documentation (THIS folder)
docs/           User-facing documentation
openspec/       Specifications and proposals
```

---

## Key File Locations

| Type | Path | Description |
|------|------|-------------|
| **Config** | `pyproject.toml` | Deps, scripts, ruff/mypy/pytest config |
| **Config** | `justfile` | All dev commands |
| **Rules** | `dev/agents/hints.md` | This file - quick reference |
| **Tools** | `src/ottools/*.py` | Built-in tool packs |
| **Core** | `src/ot/executor/runner.py` | Main execution engine |
| **Server** | `src/onetool/server.py` | MCP server |
| **Tests** | `tests/{smoke,unit,integration}/` | Test organization |
| **Specs** | `openspec/specs/` | Feature specifications |

---

## Critical Rules (Must Follow)

### Code Style
- ✅ All tool functions: keyword-only args (`*,`)
- ✅ Type hints: All functions must have complete type hints
- ✅ Docstrings: Google-style for all public functions

### Testing
- ✅ Two markers required: speed (`smoke`|`unit`|`integration`|`slow`) + component (`core`|`bench`|`serve`|`tools`)
- ✅ Run with: `uv run pytest` (never bare `pytest`)
- ✅ Fixtures: Use shared fixtures from `conftest.py`
- ✅ Test location mirrors source package: `src/otdev/` → `tests/otdev/`, `src/ottools/` → `tests/ottools/`, `src/otutil/` → `tests/otutil/`, core → `tests/`

### Paths
- ✅ `.onetool/` paths: Use `resolve_ot_path()` from `ot.meta`
- ✅ Project paths: Use `resolve_cwd_path()` from `ot.paths`
- ✅ Never use: `Path.expanduser()` or bare `expand_path()` for project paths

### Logging
- ✅ Use LogSpan: `with LogSpan(span="component.operation", key="value") as s:`
- ✅ Span naming: `{component}.{operation}` (e.g., `brave.search.web`)

### Git Commits
- ✅ Format: `type(scope): description` (no body)
- ✅ Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`, `ci`, `chore`
- ✅ Scopes: See `dev/practices/commit-scopes.md` or use `/proj:stage`

### Backwards Compatibility
- ❌ No backwards compat - delete unused code completely
- ❌ No renaming unused vars, no re-exports, no "removed" comments

---

## Quick Problem Solving

### Need to find something?

| I need... | Use mem.search() | Or read file |
|-----------|------------------|--------------|
| How to create a tool | `query="create tool pack"` | `dev/project/guides/creating-tools.md` |
| OneTool architecture | `query="request pipeline"` | `dev/project/arch/index.md` |
| Tool packs info | `query="tool packs"` | `dev/project/brand/tool-packs.md` |
| Testing guide | `query="test markers fixtures"` | `dev/practices/testing.md` |
| Git workflow | `query="git merge strategy"` | `dev/practices/git.md` |
| Commit scope | `query="commit scope for X"` | `dev/practices/commit-scopes.md` |
| Python style | `query="python style rules"` | `dev/practices/python-style.md` |
| Logging patterns | `query="LogSpan examples"` | `dev/practices/logging.md` |

### Common Tasks

**Create a new tool:**
1. Add file: `src/ottools/mypack.py` (or `src/otdev/tools/`, `src/otutil/tools/`)
2. Declare: `pack = "mypack"` and `__all__ = ["func1", "func2"]`
3. Functions: Keyword-only args, type hints, docstrings, LogSpan
4. Test: mirror source under `tests/` — e.g. `src/otdev/tools/foo.py` → `tests/otdev/unit/tools/test_foo.py`
5. Details: `mem.search(query="create tool pack")` or `dev/project/guides/creating-tools.md`

**Run tests for my changes:**
1. Smoke: `uv run pytest -m smoke` (fast, always run first)
2. Component: `uv run pytest -m tools` (if you changed tools)
3. Full: `just test` (before committing)

**Make a commit:**
1. Stage files: `git add <files>`
2. Or use: `/proj:stage` (agent suggests commit message)
3. Format: `type(scope): description`
4. Scopes: `mem.search(query="commit scope")` or `dev/practices/commit-scopes.md`

**Understand architecture:**
1. Overview: `dev/project/arch/index.md`
2. Core concepts: `dev/project/arch/core-concepts.md`
3. Request flow: `dev/project/arch/request-pipeline.md`
4. Search: `mem.search(query="architecture X")`

---

## Browser Testing

**Test URL for browser annotation tests:**
- ✅ Use: `https://en.wikipedia.org/wiki/Anthropic` - Stable, reliable, good variety of selectors
- ❌ Do NOT use: `example.com` (does not exist), Google (too complex/dynamic)

**Reliable selectors for Wikipedia:**
- Headings: `"h1"`, `"h2"`, `".mw-headline"`
- Content: `"p"`, `"a"`, `".mw-content"`
- Navigation: `".vector-menu"`, `"nav"`

**Browser annotation testing rules:**
- Do NOT manually interact with browser during automated tests (no CMD-I, no clicking)
- Always dismiss dialogs before starting: `devtools.handle_dialog(action="dismiss")`
- Use simple, stable selectors (avoid complex SPAs or dynamic content)
- Test file: `tests/explore/test-browser.md`

---

## MCP Proxy Tools

**Automatic Name Aliasing:**
MCP servers may use non-Python-friendly naming (hyphens, camelCase). OneTool automatically resolves aliases:

```python
# All these work for tool "list-organisation-details":
xero.list_organisation_details()  # Python snake_case ✓
xero.listOrganisationDetails()    # camelCase ✓
xero.ListOrganisationDetails()    # PascalCase ✓
xero.LIST_ORGANISATION_DETAILS()  # SCREAMING_SNAKE ✓
```

**How it works:**
- Exact match tried first (fast path)
- Falls back to canonical matching (remove `_`, `-`, lowercase)
- Caches resolution for performance
- Shows suggestions if no match found

**Ambiguous matches:**
If two tools normalize to same form (e.g., `list-accounts` + `list_accounts`):
- Error raised with all matching tools listed
- Use `getattr(pack, "exact-name")()` to disambiguate

**Implementation:** `src/ot/executor/naming.py`, `src/ot/executor/pack_proxy.py`

---

## When This File Isn't Enough

**For OneTool-specific info:**
- Architecture: Browse `dev/project/arch/`
- Tool creation: Browse `dev/project/guides/`
- Brand/terminology: Browse `dev/project/brand/`

**For development practices:**
- Git, testing, Python style: Browse `dev/practices/`

**For anything else:** Use `mem.search(query="your question")`

**File structure:** See `dev/index.md` for complete table of contents

---

## Related Files

- `dev/agents/project-map.md` - Detailed project structure
- `dev/index.md` - Full dev docs table of contents
- `CLAUDE.md` - Instructions for Claude Code agents
- `README.md` - Project overview for users

---

**Last updated:** 2026-02-09
**Maintained by:** Contributors (update when major structure changes)
