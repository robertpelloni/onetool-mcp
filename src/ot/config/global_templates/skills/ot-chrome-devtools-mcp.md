---
name: devtools-guide
description: Chrome DevTools MCP usage guide — browser automation and debugging via Chrome DevTools Protocol
tags: [browser, devtools, automation]
---

# Chrome DevTools MCP Guide

## Tools (26 total)

- **Input**: click, drag, fill, fill_form, handle_dialog, hover, press_key, upload_file
- **Navigation**: close_page, list_pages, navigate_page, new_page, select_page, wait_for
- **Emulation**: emulate, resize_page
- **Performance**: performance_start_trace, performance_stop_trace, performance_analyze_insight
- **Network**: get_network_request, list_network_requests
- **Debug**: evaluate_script, get_console_message, list_console_messages, take_screenshot, take_snapshot

## Connection Modes

- **Isolated** (default): temp profile, auto-launched and auto-cleaned. Best for most tasks.
  `args: ["--isolated"]`
- **Remote**: connect to existing Chrome (preserves login sessions).
  `args: ["--browserUrl=http://127.0.0.1:9222"]`
  Requires Chrome launched with: `--remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug`
- **autoConnect** (experimental): auto-attach to any Chrome with remote debugging.
  `args: ["--autoConnect", "--channel=beta"]`

## Element Highlighting (chrome_devtools_util pack)

- `chrome_devtools_util.inject_annotations()` — load inject.js into the page
- `chrome_devtools_util.highlight_element(selector=".btn", label="Click")` — annotate elements
- `chrome_devtools_util.scan_annotations()` — read user/Claude annotations
- `chrome_devtools_util.clear_annotations()` — remove all highlights
- `chrome_devtools_util.guide_user(task="...", steps=[...])` — multi-step guidance
- Users can annotate manually with Ctrl+I / Cmd+I in the browser.

## Usage Patterns

- Browser launches automatically on first tool use (no manual startup needed)
- Always use take_screenshot after actions for visual verification
- Standard flow: `navigate_page` → `wait_for` → `click/fill` → `take_screenshot`
- For forms: `fill_form` is more reliable than multiple `fill` calls
- Debug JS errors: `list_console_messages` after page interactions
- Performance analysis: `performance_start_trace` → actions → `performance_stop_trace` → `performance_analyze_insight`
- Network debugging: `list_network_requests` after page load

## Common Mistakes to Avoid

- Don't assume elements exist — use `wait_for` before interacting
- Don't skip screenshots — they're essential for debugging failures
- Don't use multiple `fill` calls when `fill_form` would work better
