# Release & Publish Guide

Internal guide for publishing new versions of OneTool.

---

## Release Workflow

Three steps: **prep → check → publish**

```bash
just release::prep 1.0.0b2      # Step 1: Bump version, generate changelog
# Edit CHANGELOG.md

just release::check             # Step 2: Lint, typecheck, tests, gitleaks, sanity

just release::publish 1.0.0b2   # Step 3: Build, publish, tag, docs
```

---

## Step 1: Prepare

```bash
just release::prep 1.0.0b2
```

- Updates version in `pyproject.toml` and `server.json`
- Generates changelog from git commits (via git-cliff)
- Opens `CHANGELOG.md` and `tmp/changelog-entry.md` in editor
- Copy/paste the generated entry into CHANGELOG.md

---

## Step 2: Check

```bash
just release::check
```

- Runs lint, typecheck, and all tests
- Scans for secrets with gitleaks
- Runs `/sanity retest=all` via `claude -p` CLI

---

## Step 3: Publish

```bash
just release::publish 1.0.0b2
```

Prompts before each step:
1. Build package (`uv build`)
2. Publish to PyPI (`uv publish`)
3. Commit, tag, push to GitHub
4. Publish to MCP Registry
5. Create GitHub release
6. Deploy docs to GitHub Pages

---

## Helper Tasks

```bash
just release::set-version 1.0.0b2  # Update version only
just release::changelog            # Preview changelog
just release::sanity               # Run sanity tests only
```

## Individual Publish Steps

```bash
just release::build     # uv build
just release::pypi      # uv publish
just release::tag 1.0.0b2  # Commit, tag, push
just release::mcp       # mcp-publisher publish
just release::docs      # mkdocs gh-deploy
```

---

## Verification Links

After release, verify at:
- PyPI: https://pypi.org/project/onetool-mcp/
- MCP Registry: https://registry.modelcontextprotocol.io
- GitHub: https://github.com/beycom/onetool/releases
- Docs: https://onetool.beycom.online

---

## Community Submissions (Major Releases)

For significant releases, submit to directories:

- https://smithery.ai/new
- https://mcpservers.org/submit
- PR to punkpeye/awesome-mcp-servers

See `plan/consult/register.md` for details.
