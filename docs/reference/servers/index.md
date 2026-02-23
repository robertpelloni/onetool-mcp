# Proxy Servers

Reference documentation for MCP proxy servers available in OneTool's shared `servers.yaml` template.

Proxy servers extend OneTool with external capabilities — browsers, APIs, code search, and cloud services. Each server runs as a subprocess (stdio) or connects over HTTP, and exposes its tools through the standard MCP interface.

## Available Servers

| Server | Type | Description |
|--------|------|-------------|
| [Chrome DevTools](chrome-devtools.md) | stdio | Browser automation and debugging via Chrome DevTools Protocol |
| [ChunkHound](chunkhound.md) | stdio | Regex and semantic code search for large codebases |
| [GitHub](github.md) | http | Official GitHub API — repos, issues, PRs, Actions |
| [Playwright](playwright.md) | stdio | Browser automation via accessibility tree (no vision needed) |

## Enabling a Server

All servers are defined in the shared `servers.yaml` template. Most are commented out by default. To enable one:

1. Add the server block to your project's `onetool.yaml` (or uncomment it in `servers.yaml`)
2. Complete any required setup (install binaries, add secrets)
3. Verify with `ot.servers()`
