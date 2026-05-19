# OneTool MCP - Project Memory

## 1. Project Overview & Vision
*   **Name:** `onetool-mcp`
*   **Vision:** OneTool is designed to be **one single MCP server** that exposes an entire ecosystem of tools as a Python API. Instead of registering dozens of individual MCP tools (which inflates prompt tokens and causes "context rot"), agents write Python code to call tools explicitly (e.g., `brave.search(query="react docs 2026")`).
*   **Key Claims:** 96% token savings (~2K tokens regardless of how many tools are added), 30x lower cost, and explicit execution transparency.
*   **Capabilities:** 100+ built-in tools across 27+ packs including web search (Brave, Tavily), AWS proxy (dynamic proxying of 57+ AWSlabs servers), databases, file operations, drawing/whiteboard (Excalidraw/Mermaid), context stores, memory stores, and image vision via dedicated models.

## 2. Architecture & Execution Routing
*   **Core Execution:** The server operates a Python execution environment (`fastmcp` + `mcp`) where an agent can pass Python snippets. The server dynamically resolves these statements to tool calls.
*   **Tool Packs:** Tools are grouped into "packs" (e.g., `ot_image`, `brave`, `db`, `mem`, `ctx`). Some packs are core, others require extras (`[util]`, `[dev]`, `[scrape]`).
*   **Proxy Flow:** It can proxy existing MCP servers (e.g., GitHub, Chrome DevTools) directly without incurring the tool definition token tax.
*   **Registry System:** Uses AST-based tool discovery.
*   **Security Model:** A four-layer defense system including AST validation, path boundaries, and output sanitization to safely execute code snippets.

## 3. Technology Stack
*   **Python:** >= 3.12 (Strict typing, `ruff` for linting/formatting, `mypy` for type checking).
*   **Core Dependencies:** `fastmcp`, `mcp`, `httpx`, `pydantic` & `pydantic-settings` (config), `loguru` (logging/telemetry), `typer` (CLI).
*   **Package Management:** Built heavily around `uv`.
*   **Build/Task Runner:** Uses `just` (not `make`). `just check` runs lint, typecheck, and tests. `just test` runs unit tests (`pytest`).
*   **Testing:** `pytest` with extensive mocking (`unittest.mock.patch`). Tests are strictly separated (e.g., `tests/ottools/unit/tools/test_image.py`). Constraints exist, like never using `example.com` in tests.

## 4. Coding Standards & Development Patterns
*   **No Backward Compatibility:** A strict rule stated in `CLAUDE.md`. Removed API values, parameter names, or config keys must raise clear errors immediately. No `_legacy`, shims, or aliases.
*   **Logging:** Uses a custom `LogSpan` pattern for adding rich context and timing to logs.
*   **Documentation:** High emphasis on "Single Source of Truth" (DRY). Documentation is split strictly into:
    *   `dev/project/`: OneTool-specific domain knowledge (Architecture, Brand, Guides).
    *   `dev/practices/`: Generic development workflows (Git, CLI patterns, Testing).
    *   `dev/agents/`: Quick references for AI agents (`hints.md`, `project-map.md`).
*   **OpenSpec Workflow:** Major changes to user-facing behavior, contracts, or tool definitions require the OpenSpec workflow (`/opsx:new`) prior to implementation.

## 5. Recent Changes (v2.2.3)
*   **Linux Clipboard Support:** The `ot_image` pack initially lacked Linux clipboard support, throwing a `NotImplementedError`. This was resolved in version 2.2.3 by implementing subprocess calls to system tools (`wl-paste` for Wayland and `xclip` for X11) as a robust fallback to Pillow's native grab functionality which only supports Windows/macOS.
*   **Documentation Scaffolding:** Missing high-level project management files (`VISION.md`, `ROADMAP.md`, `TODO.md`, `HANDOFF.md`, `DEPLOY.md`, `VERSION.md`, etc.) were scaffolded to provide a complete workspace context for agents. Detailed deep analysis and library inventories were populated in `HANDOFF.md`.