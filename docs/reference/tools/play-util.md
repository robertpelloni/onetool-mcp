# Playwright Util

Visual element annotation for the [Playwright MCP](../servers/playwright.md) server — highlight elements, guide users through workflows, and let users point Claude to elements with ++ctrl+i++.

Short alias: `play`

## Tools

### `inject_annotations()`

Loads inject.js v2.0 into the current page. Must be called before any other annotation function. Idempotent — re-calling on an already-injected page returns success without re-injecting.

```python
play_util.inject_annotations()
# Returns: {"success": True, "ready": True, "version": "2.0.0"}
```

### `highlight_element(selector, label, color, element_id)`

Highlights all elements matching a CSS selector with a labelled overlay box.

```python
play_util.highlight_element(selector="button.submit", label="Click here")
play_util.highlight_element(selector=".error", label="Fix this", color="red")
```

Available colours: `orange` (default), `red`, `blue`, `green`.

### `scan_annotations()`

Returns all current annotations on the page — both those added programmatically and those added by the user via selection mode.

```python
annotations = play_util.scan_annotations()
# Returns: [{"id": "sel-1", "label": "My note", "selector": ".some-el",
#            "content": "...", "tagName": "span", "color": "orange"}, ...]
```

### `clear_annotations()`

Removes all annotations and overlays from the page.

```python
play_util.clear_annotations()
# Returns: {"success": True, "cleared": 3}
```

### `guide_user(task, steps)`

Highlights a sequence of elements at once so the user can see a full workflow in one view.

```python
play_util.guide_user(
    task="Complete checkout",
    steps=[
        {"selector": "input[name='email']", "label": "1. Enter email"},
        {"selector": "input[name='card']",  "label": "2. Card number"},
        {"selector": "button.pay",          "label": "3. Pay now", "color": "green"},
    ],
)
```

## Manual Selection Mode (Ctrl+I / Cmd+I)

Users can annotate elements directly in the browser without writing any code:

1. Press ++ctrl+i++ (or ++cmd+i++ on macOS) to enter selection mode — the cursor changes to a crosshair
2. Hover over elements to preview the selection highlight
3. Click an element — a prompt appears to enter a custom label
4. Press ++ctrl+i++ again (or cancel the prompt) to exit selection mode

Claude reads the result with `scan_annotations()`:

```python
play_util.inject_annotations()
# ... tell user to press Ctrl+I and click the element they mean ...
annotations = play_util.scan_annotations()
# Use annotations[0]["selector"] to interact with what they picked
```

## Usage Patterns

- Always call `inject_annotations()` first — other functions silently fail if inject.js is not loaded
- Use `highlight_element` to show the user what to interact with next
- Use `guide_user` for multi-step workflows — all steps visible at once
- Use `scan_annotations` after the user has used Ctrl+I to read their selections
- Call `clear_annotations()` between tasks to avoid stale overlays

## Configuration

### Required

- No required `tools.play_util` settings.

### Optional

- This pack does not define any pack-specific keys under `tools.play_util`.

### Defaults

- OneTool uses the built-in defaults for annotation behavior.
- Requires the `playwright` MCP server. Enable it in `servers.yaml` (persistent):

```yaml
playwright:
  enabled: true
```

Or enable for the current session only: `ot.server(enable="playwright")`

## Examples

### Guide a user through a form

```python
playwright.browser_navigate(url="https://myapp.com/settings")
play_util.inject_annotations()
play_util.guide_user(
    task="Update your profile",
    steps=[
        {"selector": "input[name='display_name']", "label": "1. Edit name"},
        {"selector": "input[name='email']",         "label": "2. Confirm email"},
        {"selector": "button[type='submit']",        "label": "3. Save", "color": "green"},
    ],
)
playwright.browser_take_screenshot()
```

### Let a user point Claude to an element

```python
play_util.inject_annotations()
# Ask user to press Ctrl+I and click the element they want
annotations = play_util.scan_annotations()
# annotations[0]["selector"] contains the CSS selector of what they clicked
```

### Highlight an error field

```python
play_util.inject_annotations()
play_util.highlight_element(selector="#email-error", label="Fix this", color="red")
playwright.browser_take_screenshot()
play_util.clear_annotations()
```
