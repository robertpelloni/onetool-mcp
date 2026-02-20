# Chrome DevTools MCP

Browser automation, debugging, and element annotation via Chrome DevTools Protocol.

## Quick Start

No configuration required. DevTools launches a browser automatically on first use.

```python
# 1. Navigate to a page
devtools.navigate_page(url="https://example.com")

# 2. Take a screenshot
devtools.take_screenshot()

# 3. Highlight an element
chrome_devtools_util.inject_annotations()
chrome_devtools_util.highlight_element(selector="h1", label="Main heading")
```

That's it. The DevTools MCP server is pre-configured in OneTool's `servers.yaml` template.

## Concepts

### What is DevTools MCP?

Chrome DevTools MCP connects OneTool to a Chrome browser via the [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/). It provides 26 tools for:

- **Navigation** — open pages, manage tabs, wait for elements
- **Input** — click, type, fill forms, upload files
- **Debugging** — evaluate JavaScript, read console messages, inspect network requests
- **Performance** — trace rendering, analyse load times
- **Annotation** — highlight elements with visual overlays (via inject.js)

### When to Use DevTools vs Playwright

| Criteria | DevTools MCP | Playwright MCP |
|----------|-------------|----------------|
| Best for | Debugging, inspection, manual workflows | Automated testing, cross-browser |
| Browser | Chrome only | Chrome, Firefox, WebKit |
| Setup | Zero config (pre-configured) | Requires `npx @playwright/mcp` |
| Bot detection | Low (uses real Chrome profile) | Higher (automation flags) |
| Element annotation | `chrome_devtools_util` pack | `playwright_util` pack |

Both support the inject.js annotation system through their respective utility packs.

## Connection Modes

DevTools MCP supports three connection modes. Choose based on your needs.

### Isolated Mode (Default)

Uses a temporary Chrome profile that's cleaned up on close. Best for most tasks.

```yaml
# servers.yaml (default)
devtools:
  type: stdio
  command: npx
  args:
    - "-y"
    - "chrome-devtools-mcp@latest"
    - "--isolated"
    - "--viewport=1280x720"
```

### Remote Mode

Connect to an existing Chrome instance. Useful for debugging logged-in sessions or inspecting long-running apps.

**Setup:**

=== "macOS"

    ```bash
    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
      --remote-debugging-port=9222 \
      --user-data-dir=/tmp/chrome-debug
    ```

=== "Linux"

    ```bash
    google-chrome \
      --remote-debugging-port=9222 \
      --user-data-dir=/tmp/chrome-debug
    ```

=== "Windows"

    ```powershell
    & "C:\Program Files\Google\Chrome\Application\chrome.exe" `
      --remote-debugging-port=9222 `
      --user-data-dir=C:\temp\chrome-debug
    ```

Verify the connection:

```bash
curl http://localhost:9222/json/version
```

Then configure OneTool to connect:

```yaml
devtools:
  type: stdio
  command: npx
  args:
    - "-y"
    - "chrome-devtools-mcp@latest"
    - "--browserUrl=http://localhost:9222"
```

!!! note
    Chrome 136+ requires `--user-data-dir` for remote debugging.

### autoConnect Mode (Experimental)

Connects to any Chrome instance that has remote debugging enabled via `chrome://inspect`.

```yaml
devtools:
  type: stdio
  command: npx
  args:
    - "-y"
    - "chrome-devtools-mcp@latest"
    - "--autoConnect"
    - "--channel=beta"  # Required until Chrome M144 reaches stable
```

### Comparison

| Feature | Isolated | Remote | autoConnect |
|---------|----------|--------|-------------|
| Setup complexity | None | Medium | Low |
| Session persistence | No | Yes | Yes |
| Bot detection risk | Low | None | None |
| Security risk | Low | Medium | Medium |
| Requires running Chrome | No | Yes | Yes |

## Element Highlighting

OneTool includes inject.js v2.0, a visual annotation system that overlays labels and coloured borders on page elements. Two independent tool packs provide Python access:

- **`chrome_devtools_util`** — for the Chrome DevTools MCP server
- **`playwright_util`** — for the Playwright MCP server

!!! important
    These packs are independent. Each targets its own MCP server with no fallback between them. Use the pack that matches your connected server.

### Injection

Before highlighting, inject the annotation script into the page:

```python
chrome_devtools_util.inject_annotations()
# Returns: {"success": True, "ready": True, "version": "2.0.0"}
```

This is idempotent — calling it again on an already-injected page returns success without re-injecting.

### Programmatic Highlighting (Claude-to-User)

Highlight elements to show the user what to interact with:

```python
# Highlight a button
chrome_devtools_util.highlight_element(selector="button.submit", label="Click here")

# Use colour to indicate meaning
chrome_devtools_util.highlight_element(selector=".error", label="Error field", color="red")
chrome_devtools_util.highlight_element(selector=".success", label="Done", color="green")
```

Available colours: `orange` (default), `red`, `blue`, `green`.

### Manual Annotation (User-to-Claude)

Users can annotate elements directly in the browser:

1. Press ++ctrl+i++ (or ++cmd+i++ on macOS) to enter selection mode
2. Click an element to annotate it
3. Press ++ctrl+i++ again to exit selection mode

Claude can then read what the user selected:

```python
annotations = chrome_devtools_util.scan_annotations()
# Returns: [{"id": "sel-1", "label": "button", "selector": ".submit-btn", ...}]
```

### Clearing Annotations

Remove all annotations when done:

```python
chrome_devtools_util.clear_annotations()
# Returns: {"success": True, "cleared": 3}
```

### Guided Workflows

Highlight multiple elements at once to walk the user through a task:

```python
chrome_devtools_util.guide_user(
    task="Complete checkout",
    steps=[
        {"selector": "input[name='email']", "label": "1. Enter email"},
        {"selector": "input[name='card']", "label": "2. Card number"},
        {"selector": "button.pay", "label": "3. Pay now", "color": "green"},
    ],
)
```

### API Reference

Both packs expose the same 5 functions:

| Function | Description |
|----------|-------------|
| `inject_annotations()` | Load inject.js into the page (idempotent) |
| `highlight_element(selector, label, color, element_id)` | Highlight matching elements |
| `scan_annotations()` | Read all current annotations |
| `clear_annotations()` | Remove all annotations |
| `guide_user(task, steps)` | Highlight a sequence of elements |

For Chrome DevTools, use `chrome_devtools_util.*`. For Playwright, use `playwright_util.*`.

## Common Tasks

### 1. Fill a Form

**Goal:** Automate form submission on a web page.

**Prerequisites:** DevTools server connected, page loaded.

```python
devtools.navigate_page(url="https://example.com/signup")
devtools.wait_for(selector="form")
devtools.fill_form(values={
    "input[name='email']": "user@example.com",
    "input[name='password']": "secure123",
})
devtools.click(selector="button[type='submit']")
devtools.take_screenshot()
```

**Common issues:** Use `wait_for` before interacting — elements may not be ready yet.

### 2. Debug Authentication

**Goal:** Inspect a logged-in session without losing state.

**Prerequisites:** Chrome running in remote mode with an active session.

```python
# Check cookies
devtools.evaluate_script(expression="JSON.stringify(document.cookie)")

# Inspect network requests for auth headers
devtools.navigate_page(url="https://app.example.com/dashboard")
devtools.list_network_requests()
```

**Common issues:** Use remote mode to preserve the login session. Isolated mode starts fresh.

### 3. Detect Bot Protection

**Goal:** Check if a site detects automation.

**Prerequisites:** DevTools server connected.

```python
devtools.navigate_page(url="https://bot.sannysoft.com")
devtools.take_screenshot()
devtools.evaluate_script(expression="navigator.webdriver")
```

**Common issues:** If `navigator.webdriver` returns `true`, the site can detect automation. Use remote mode with a normal Chrome profile to avoid this.

### 4. Analyse Page Performance

**Goal:** Profile page load and rendering performance.

**Prerequisites:** DevTools server connected.

```python
devtools.performance_start_trace()
devtools.navigate_page(url="https://example.com")
devtools.wait_for(selector="body")
trace = devtools.performance_stop_trace()
devtools.performance_analyze_insight()
```

**Common issues:** Start the trace before navigation, not after.

### 5. Guide a User Through a Workflow

**Goal:** Visually walk the user through a multi-step process.

**Prerequisites:** inject.js loaded on the page.

```python
chrome_devtools_util.inject_annotations()
chrome_devtools_util.guide_user(
    task="Update profile",
    steps=[
        {"selector": "a[href='/settings']", "label": "1. Open Settings"},
        {"selector": "input[name='display_name']", "label": "2. Edit name"},
        {"selector": "button.save", "label": "3. Save", "color": "green"},
    ],
)
devtools.take_screenshot()
```

**Common issues:** Call `inject_annotations()` first. Elements must be visible in the viewport for overlays to render.

## Troubleshooting

### Browser won't launch

**Symptom:** Timeout on first DevTools tool call.

**Diagnostic:**
```bash
npx -y chrome-devtools-mcp@latest --isolated
```

**Solutions:**

- Ensure Chrome is installed
- Try `--channel=beta` if stable Chrome has issues
- Check firewall isn't blocking Chrome
- Increase `timeout` in servers.yaml (default: 120s)

### Can't connect to remote Chrome

**Symptom:** `browserUrl` connection refused.

**Diagnostic:**
```bash
curl http://localhost:9222/json/version
```

**Solutions:**

- Verify Chrome was launched with `--remote-debugging-port=9222`
- Add `--user-data-dir` (required since Chrome 136+)
- Check no other process is using port 9222

### Elements not found

**Symptom:** `wait_for` times out or `click` fails.

**Diagnostic:**
```python
devtools.take_screenshot()
devtools.evaluate_script(expression="document.querySelectorAll('.my-selector').length")
```

**Solutions:**

- Take a screenshot to see the actual page state
- The page may still be loading — increase wait time
- The selector may be inside an iframe — switch frames first
- The element may be dynamically rendered — wait for it specifically

### Highlights not showing

**Symptom:** `highlight_element` returns success but no visual overlay.

**Diagnostic:**
```python
chrome_devtools_util.scan_annotations()
```

**Solutions:**

- Call `inject_annotations()` first
- The element may be offscreen — scroll it into view
- Check the selector matches: `evaluate_script` with `document.querySelectorAll`

### Site detects automation

**Symptom:** CAPTCHAs, blocks, or different content.

**Solutions:**

- Switch to remote mode with a normal Chrome profile
- Avoid `--headless` (many sites check for headless)
- Add delays between actions to mimic human behaviour

### Chrome crashes or hangs

**Symptom:** Tools stop responding after extended use.

**Solutions:**

- Close unused pages: `devtools.list_pages()` then `devtools.close_page()`
- Restart: disconnect and reconnect the DevTools server
- Reduce `--viewport` size if memory-constrained

## FAQ

**Q: Do I need to install Chrome separately?**

Yes. DevTools MCP uses your system Chrome installation. Install Chrome from [google.com/chrome](https://www.google.com/chrome/) if not already present.

**Q: Can I use this with headless Chrome?**

Yes. Add `--headless=true` to the args in servers.yaml. Note that some sites detect headless mode.

**Q: Can I automate multiple tabs?**

Yes. Use `devtools.new_page()` to open tabs and `devtools.select_page()` to switch between them. `devtools.list_pages()` shows all open tabs.

**Q: How do I handle popups and dialogs?**

Use `devtools.handle_dialog(action="accept")` or `action="dismiss"`. Set this up before triggering the dialog.

**Q: Can I upload files?**

Yes. Use `devtools.upload_file(selector="input[type='file']", paths=["/path/to/file.pdf"])`.

**Q: What's the difference between `chrome_devtools_util` and `playwright_util`?**

They provide the same 5 annotation functions but target different MCP servers. `chrome_devtools_util` uses Chrome DevTools (`chrome-devtools.evaluate_script`), `playwright_util` uses Playwright (`playwright.evaluate`). They are completely independent — there is no fallback between them. Use whichever matches your connected server.

**Q: Can I use both DevTools and Playwright at the same time?**

Yes, if both servers are configured and connected. They control separate browser instances. Use `chrome_devtools_util.*` for the DevTools browser and `playwright_util.*` for the Playwright browser.

**Q: How do I resize the browser window?**

Use `devtools.resize_page(width=1920, height=1080)`. The default is set by `--viewport` in servers.yaml (1280x720).
