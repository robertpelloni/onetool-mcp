---
name: ot-playwright-mcp
description: Playwright MCP usage guide — browser automation via accessibility snapshots (no vision needed)
tags: [browser, playwright, automation]
---

# Playwright MCP Guide

## Key Tools

- **Navigation**: browser_navigate, browser_back, browser_forward, browser_wait
- **Interaction**: browser_click, browser_type, browser_select_option, browser_press_key
- **State**: browser_snapshot, browser_screenshot, browser_evaluate
- **Tabs**: browser_tab_list, browser_tab_new, browser_tab_select, browser_tab_close

## Element Highlighting (playwright_util pack)

- `playwright_util.inject_annotations()` — load inject.js into the page
- `playwright_util.highlight_element(selector=".btn", label="Click")` — annotate elements
- `playwright_util.scan_annotations()` — read user/Claude annotations
- `playwright_util.clear_annotations()` — remove all highlights
- `playwright_util.guide_user(task="...", steps=[...])` — multi-step guidance
- Users can annotate manually with Ctrl+I / Cmd+I in the browser.

## Usage Patterns

- Always take `browser_snapshot` after actions (preferred over screenshots)
- Standard flow: `browser_navigate` → `browser_snapshot` → `browser_click/type` → `browser_snapshot`
- Use `browser_evaluate` for custom JS execution
- Use `browser_screenshot` for visual verification when needed

## Options (add to args in servers.yaml)

- `--headless` — Run without visible browser window
- `--browser=firefox` — Use Firefox or WebKit instead of Chromium
- `--viewport=WxH` — Set viewport size (e.g., 1280x720)

## Common Mistakes to Avoid

- Don't assume elements exist — use `browser_snapshot` first
- Don't skip snapshots between actions
- Don't use `browser_screenshot` when `browser_snapshot` (accessibility tree) is sufficient

Full reference: https://onetool.beycom.online/reference/servers/playwright/
