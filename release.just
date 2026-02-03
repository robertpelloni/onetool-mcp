# Release Tasks for OneTool
# Usage: just release::<task>

set dotenv-load := true

# ============================================================================
# RELEASE WORKFLOW: prep → check → release
# ============================================================================

# Show available commands
default:
    @just --list --unsorted

# --------------------------------------------------------------------------
# Step 1: Prepare (bump version, generate changelog, edit)
# --------------------------------------------------------------------------
prep version:
    @echo "=== Step 1: Prepare release {{ version }} ==="
    @echo ""
    just release::set-version {{ version }}
    @echo ""
    @mkdir -p tmp
    @echo "## [{{ version }}] - $(date +%Y-%m-%d)" > tmp/changelog-entry.md
    @echo "" >> tmp/changelog-entry.md
    @git cliff --unreleased --strip header 2>/dev/null >> tmp/changelog-entry.md || (echo "### Changes" >> tmp/changelog-entry.md && echo "" >> tmp/changelog-entry.md && git log $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD~20")..HEAD --oneline --no-merges | sed 's/^/- /' >> tmp/changelog-entry.md)
    @echo "" >> tmp/changelog-entry.md
    @echo ""
    @echo "Generated changelog entry:"
    @echo "─────────────────────────────────────"
    @cat tmp/changelog-entry.md
    @echo "─────────────────────────────────────"
    @echo ""
    @echo "Add this to CHANGELOG.md after line 4"
    @echo "Opening CHANGELOG.md in editor..."
    @${EDITOR:-code} CHANGELOG.md tmp/changelog-entry.md
    @echo ""
    @echo "Next: just release::check"

# --------------------------------------------------------------------------
# Step 2: Check (lint, typecheck, tests, gitleaks, sanity)
# --------------------------------------------------------------------------
check:
    @echo "=== Step 2: Pre-release checks ==="
    @echo ""
    @echo "Running lint..."
    just lint
    @echo ""
    @echo "Running typecheck..."
    just typecheck
    @echo ""
    @echo "Running tests..."
    just test
    @echo ""
    @echo "Scanning for secrets..."
    gitleaks detect --source . --verbose
    @echo ""
    @echo "Running sanity tests via Claude Code..."
    claude -p "/sanity retest=all"
    @echo ""
    @echo "=== All checks passed ==="
    @echo ""
    @echo "Next: just release::publish VERSION"

# --------------------------------------------------------------------------
# Step 3: Publish (build, publish, tag, docs - confirms each step)
# --------------------------------------------------------------------------
publish version:
    @echo "=== Step 3: Release {{ version }} ==="
    @echo ""
    @echo "This will:"
    @echo "  1. Build package"
    @echo "  2. Publish to PyPI"
    @echo "  3. Commit, tag v{{ version }}, push to GitHub"
    @echo "  4. Publish to MCP Registry"
    @echo "  5. Create GitHub release"
    @echo "  6. Deploy docs to GitHub Pages"
    @echo ""
    @read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
    @echo ""
    @echo "=== Building package ==="
    uv build
    @echo ""
    @read -p "Publish to PyPI? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
    @echo ""
    @echo "=== Publishing to PyPI ==="
    uv publish
    @echo ""
    @read -p "Commit, tag v{{ version }}, and push to GitHub? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
    @echo ""
    @echo "=== Committing and tagging ==="
    git add -A
    git commit -m "Release {{ version }}" || true
    git tag -a "v{{ version }}" -m "Release {{ version }}"
    git push origin main
    git push origin "v{{ version }}"
    @echo ""
    @read -p "Publish to MCP Registry? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
    @echo ""
    @echo "=== Publishing to MCP Registry ==="
    mcp-publisher publish
    @echo ""
    @read -p "Create GitHub release? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
    @echo ""
    @echo "=== Creating GitHub release ==="
    gh release create "v{{ version }}" --title "v{{ version }}" --notes-file tmp/release-notes.md || echo "Skipped (create tmp/release-notes.md or run: gh release create v{{ version }} manually)"
    @echo ""
    @read -p "Deploy docs to GitHub Pages? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
    @echo ""
    @echo "=== Deploying docs ==="
    uv run mkdocs gh-deploy --force
    @echo ""
    @echo "=== Release {{ version }} complete ==="
    @echo ""
    @echo "Verify at:"
    @echo "  - https://pypi.org/project/onetool-mcp/"
    @echo "  - https://registry.modelcontextprotocol.io"
    @echo "  - https://github.com/beycom/onetool/releases"
    @echo "  - https://onetool.beycom.online"

# ============================================================================
# HELPER TASKS
# ============================================================================

# Set version in pyproject.toml and server.json
set-version version:
    @echo "Setting version to {{ version }}"
    sed -i '' 's/^version = ".*"/version = "{{ version }}"/' pyproject.toml
    sed -i '' 's/"version": ".*"/"version": "{{ version }}"/g' server.json
    @echo "Updated pyproject.toml and server.json"

# Generate changelog since last tag (preview only)
changelog:
    @echo "=== Changes since last release ==="
    @git cliff --unreleased --strip header 2>/dev/null || git log $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD~20")..HEAD --oneline --no-merges
    @echo ""

# Run sanity tests only
sanity:
    @echo "=== Running sanity tests via Claude Code ==="
    claude -p "/sanity retest=all"

# ============================================================================
# INDIVIDUAL PUBLISH STEPS
# ============================================================================

# Build package only
build:
    uv build

# Publish to PyPI only
pypi:
    uv publish

# Publish to MCP Registry only
mcp:
    mcp-publisher publish

# Deploy docs only
docs:
    uv run mkdocs gh-deploy --force

# Create git tag and push
tag version:
    git add -A
    git commit -m "Release {{ version }}" || true
    git tag -a "v{{ version }}" -m "Release {{ version }}"
    git push origin main
    git push origin "v{{ version }}"
