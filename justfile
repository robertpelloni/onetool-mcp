# OneTool Development Tasks
# Run `just` to see available commands

set dotenv-load := true

# Project-local global config base (all versions stored here)
global_base := justfile_directory() + "/.onetool-global"

# Default: show available commands
default:
    @just --list --unsorted

# ============================================================================
# QUICK START
# ============================================================================

# Install all dependencies
install:
    uv sync --group dev

# Run all quality checks (lint, typecheck, test)
check: lint typecheck test

# Run the MCP server in development mode (uses dev global dir)
dev *args:
    OT_GLOBAL_DIR={{ global_base }}/dev uv run onetool {{ args }}

# ============================================================================
# TESTING
# ============================================================================

# Run all tests (strict - errors on missing requirements)
test *args:
    uv run pytest {{ args }}

# Run tests with --allow-skips (lenient - skips on missing requirements)
test-lenient *args:
    uv run pytest --allow-skips {{ args }}

# Run unit tests only
test-unit:
    uv run pytest -m unit

# Run integration tests only
test-integration:
    uv run pytest -m integration

# Run tests with coverage report
test-coverage:
    uv run pytest --cov=onetool --cov-report=html

# ============================================================================
# CODE QUALITY
# ============================================================================

# Lint code with ruff
lint:
    uv run ruff check src/

# Lint and auto-fix issues
lint-fix:
    uv run ruff check --fix src/

# Format code with ruff
fmt:
    uv run ruff format src/

# Check formatting without changes
fmt-check:
    uv run ruff format --check src/

# Type check with mypy
typecheck:
    uv run mypy

# Check for unused dependencies
deps-check:
    uvx deptry . 2>&1 | grep -v "^Assuming"

# Scan for secrets with gitleaks
secrets-check:
    gitleaks detect --source . --verbose

# ============================================================================
# DOCUMENTATION
# ============================================================================

# Serve documentation locally with hot reload
docs-serve *args:
    uv run mkdocs serve --dev-addr 127.0.0.1:8000 {{ args }}

# Stop the documentation server
docs-serve-stop:
    @lsof -ti :8000 | xargs kill 2>/dev/null && echo "Docs server stopped" || echo "No server running on port 8000"

# Build documentation site (strict mode)
docs-build:
    uv run mkdocs build --strict

# Clean and rebuild docs (strict mode)
docs-clean:
    rm -rf dist/site && uv run mkdocs build --strict

# Deploy documentation to GitHub Pages
docs-deploy:
    uv run mkdocs gh-deploy --force

# Regenerate the OpenSpec specifications viewer HTML
docs-specs:
    uv run python scripts/generate_specs_html.py

# ============================================================================
# BUILD & RELEASE
# ============================================================================

# Build the package
build:
    uv build

# Clean build artifacts and caches
clean:
    rm -rf dist/ build/ *.egg-info tmp/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    uv cache clean

# ============================================================================
# CODE SEARCH (ChunkHound)
# ============================================================================

# Index current project for semantic code search (requires OPENAI_API_KEY env var)
index path=".":
    @echo "=== Indexing {{ path }} for semantic code search ==="
    uvx chunkhound index {{ path }} --db {{ path }}/.chunkhound/chunks.db --model text-embedding-3-small --base-url https://openrouter.ai/api/v1
    @echo "=== Index complete. Use code.search() or code.status() ==="

# ============================================================================
# MODULES (use `just <module>::<task>`)
# ============================================================================

mod demo
mod release "release.just"

# ============================================================================
# TOOL: DIAGRAM (Kroki Server)
# ============================================================================

# Start Kroki diagram server
tool-diagram-start:
    docker compose -f resources/docker/kroki/docker-compose.yaml up -d
    @echo "Kroki running at http://localhost:8000"
    @echo "Health check: curl http://localhost:8000/health"

# Stop Kroki diagram server
tool-diagram-stop:
    docker compose -f resources/docker/kroki/docker-compose.yaml down

# Show Kroki server status
tool-diagram-status:
    @docker compose -f resources/docker/kroki/docker-compose.yaml ps 2>/dev/null || echo "Kroki not running"
    @curl -s http://localhost:8000/health 2>/dev/null && echo " - Kroki healthy" || echo "Kroki not responding"

# View Kroki server logs
tool-diagram-logs:
    docker compose -f resources/docker/kroki/docker-compose.yaml logs -f

# ============================================================================
# TOOL: MCP INSPECTOR (MCPJam)
# ============================================================================

# Launch MCP Inspector for testing MCP servers
# https://github.com/MCPJam/inspector
ot-inspector:
    npx @mcpjam/inspector@latest

# ============================================================================
# GLOBAL TOOL MANAGEMENT
# ============================================================================

# Install onetool globally via uv
ot-install:
    uv tool install . -v

# Install onetool globally via uv
ot-install-dev:
    uv tool install . -e -v


# Uninstall global onetool
ot-uninstall:
    uv tool uninstall onetool-mcp || true

# List installed uv tools
ot-list:
    uv tool list

# ============================================================================
# MULTI-VERSION DEVELOPMENT
# ============================================================================

# Initialize dev version config in .onetool-global/dev
ot-init-dev:
    @echo "Initializing dev version config..."
    @mkdir -p {{ global_base }}/dev
    OT_GLOBAL_DIR={{ global_base }}/dev uv run onetool init
    @echo ""
    @echo "✅ Dev config initialized at {{ global_base }}/dev"
    @echo ""
    @echo "MCP Configuration:"
    @echo "  Command: {{ justfile_directory() }}/.venv/bin/python"
    @echo "  Args: [\"-m\", \"ot.mcp\"]"
    @echo "  Env: {\"OT_GLOBAL_DIR\": \"{{ global_base }}/dev\"}"

# Initialize stable version config in .onetool-global/stable
ot-init-stable:
    @echo "Initializing stable version config..."
    @mkdir -p {{ global_base }}/stable
    OT_GLOBAL_DIR={{ global_base }}/stable uv run onetool init
    @echo ""
    @echo "✅ Stable config initialized at {{ global_base }}/stable"
    @echo ""
    @echo "MCP Configuration:"
    @echo "  Command: uvx"
    @echo "  Args: [\"--from\", \"onetool-mcp\", \"onetool\"]"
    @echo "  Env: {\"OT_GLOBAL_DIR\": \"{{ global_base }}/stable\"}"

# Initialize specific version config in .onetool-global/<version>
ot-init-version VERSION:
    @echo "Initializing {{ VERSION }} config..."
    @mkdir -p {{ global_base }}/{{ VERSION }}
    OT_GLOBAL_DIR={{ global_base }}/{{ VERSION }} uv run onetool init
    @echo ""
    @echo "✅ Version {{ VERSION }} config initialized at {{ global_base }}/{{ VERSION }}"
    @echo ""
    @echo "MCP Configuration:"
    @echo "  Command: uvx"
    @echo "  Args: [\"--from\", \"onetool-mcp=={{ VERSION }}\", \"onetool\"]"
    @echo "  Env: {\"OT_GLOBAL_DIR\": \"{{ global_base }}/{{ VERSION }}\"}"

# Show all initialized OneTool versions
ot-versions:
    @echo "=== OneTool Versions ==="
    @echo ""
    @echo "Dev (local editable):"
    @test -f .venv/bin/python && .venv/bin/python -c "from ot import __version__; print(f'  Version: {__version__}')" 2>/dev/null || echo "  Not installed (run 'just install')"
    @test -d {{ global_base }}/dev && echo "  Config: {{ global_base }}/dev" || echo "  Config: Not initialized (run 'just ot-init-dev')"
    @test -f .venv/bin/python && echo "  Command: {{ justfile_directory() }}/.venv/bin/python -m ot.mcp" || true
    @echo ""
    @echo "Global directories:"
    @test -d {{ global_base }} && ls -1d {{ global_base }}/*/ 2>/dev/null | sed 's|{{ global_base }}/||;s|/$||' | sed 's/^/  /' || echo "  None (run 'just ot-init-dev' or 'just ot-init-stable')"

# Run dev version with specific global dir
ot-run-dev *args:
    @echo "Running dev version from {{ global_base }}/dev"
    OT_GLOBAL_DIR={{ global_base }}/dev uv run python -m ot.mcp {{ args }}

# Debug dev version (shows paths, config, runtime info)
ot-debug-dev:
    @echo "=== Dev Version Debug Info ==="
    OT_GLOBAL_DIR={{ global_base }}/dev uv run python -c "from ot.meta import debug; import json; print(json.dumps(debug(), indent=2))"

# Debug specific version
ot-debug VERSION:
    @echo "=== {{ VERSION }} Version Debug Info ==="
    OT_GLOBAL_DIR={{ global_base }}/{{ VERSION }} uv run python -c "from ot.meta import debug; import json; print(json.dumps(debug(), indent=2))"

# Reset dev version config (prompts before overwriting)
ot-reset-dev:
    @echo "Resetting dev version config at {{ global_base }}/dev"
    OT_GLOBAL_DIR={{ global_base }}/dev uv run onetool init reset

# Remove a version's global directory
ot-remove VERSION:
    @echo "Removing {{ global_base }}/{{ VERSION }}"
    @rm -rf {{ global_base }}/{{ VERSION }}
    @echo "✅ Removed {{ VERSION }}"

# Clean all global directories (DESTRUCTIVE)
ot-clean-all:
    @echo "⚠️  This will remove ALL OneTool config directories in {{ global_base }}"
    @echo "Press Ctrl+C to cancel, or Enter to continue..."
    @read _
    rm -rf {{ global_base }}
    @echo "✅ All configs removed"

# Validate dev version config
ot-validate-dev:
    OT_GLOBAL_DIR={{ global_base }}/dev uv run onetool init validate

# Validate specific version config
ot-validate VERSION:
    OT_GLOBAL_DIR={{ global_base }}/{{ VERSION }} uv run onetool init validate

# Copy dev config to another version
ot-copy-config FROM TO:
    @echo "Copying config from {{ FROM }} to {{ TO }}"
    @mkdir -p {{ global_base }}/{{ TO }}
    @cp -r {{ global_base }}/{{ FROM }}/config {{ global_base }}/{{ TO }}/
    @echo "✅ Config copied from {{ FROM }} to {{ TO }}"

