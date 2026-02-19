# Test Browser Annotation Packs

Smoke test `chrome_devtools_util` and `playwright_util` packs against live browser MCP servers.

## IMPORTANT: Testing Environment

**Do NOT manually interact with the browser during automated tests.** This includes:
- Pressing CMD-I/Ctrl+I to enter selection mode
- Clicking elements in the browser
- Accepting/dismissing dialogs

Manual testing should be done separately after automated tests complete.

## Prerequisites

Check which browser MCP servers are connected:

```python
ot.servers()
```

Expected: At least one of `devtools` or `playwright` should be connected.

## Setup: Chrome DevTools

```python
# 1. Create a new browser page
devtools.new_page(url="https://en.wikipedia.org/wiki/Anthropic")

# 2. Dismiss any existing dialogs (cleanup from previous tests)
try:
    devtools.handle_dialog(action="dismiss")
except:
    pass  # No dialog present, continue
```

## Setup: Playwright

```python
# 1. Create a new page and navigate
playwright.browser_navigate(url="https://en.wikipedia.org/wiki/Anthropic")

# 2. Dismiss any existing dialogs (cleanup from previous tests)
try:
    playwright.handle_dialog(action="dismiss")
except:
    pass  # No dialog present, continue
```

## Test: chrome_devtools_util

Run the full annotation cycle via Chrome DevTools:

```python
# 1. Inject (fresh)
r1 = chrome_devtools_util.inject_annotations()
# Expect: {success: true, ready: true, version: "2.0.0"}

# 2. Inject (idempotent)
r2 = chrome_devtools_util.inject_annotations()
# Expect: {success: true, ready: true, version: "2.0.0"}

# 3. Highlight with custom element_id and color
r3 = chrome_devtools_util.highlight_element(selector="a", label="Test link", color="blue", element_id="test-1")
# Expect: {success: true, count: >= 1, ids: ["test-1-0", "test-1-1", ...]}
# Note: Multiple matches get indexed IDs

# 4. Scan annotations
r4 = chrome_devtools_util.scan_annotations()
# Expect: list with annotations containing: id, label, selector, content, tagName, color
# Verify: len(r4) >= 1

# 5. Guide user (multi-step) - use simple selectors
r5 = chrome_devtools_util.guide_user(
    task="Navigate",
    steps=[
        {"selector": "h1", "label": "Step 1: Heading", "color": "orange"},
        {"selector": "p", "label": "Step 2: Paragraph", "color": "green"}
    ]
)
# Expect: {task: "Navigate", total: 2, highlighted: 2, results: [...]}

# 6. Clear all annotations
r6 = chrome_devtools_util.clear_annotations()
# Expect: {success: true, cleared: >= 1}

# 7. Verify cleared
r7 = chrome_devtools_util.scan_annotations()
# Expect: empty list []

# 8. Take screenshot for verification
devtools.take_screenshot()

# Print summary
{
    "inject": r1.get("version"),
    "idempotent": r2.get("ready"),
    "highlighted": r3.get("count"),
    "scanned": len(r4),
    "guide_steps": r5.get("highlighted"),
    "cleared": r6.get("cleared"),
    "final_count": len(r7)
}
```

## Test: playwright_util

Run the same cycle via Playwright:

```python
# 1. Inject (fresh)
p1 = playwright_util.inject_annotations()
# Expect: {success: true, ready: true, version: "2.0.0"}

# 2. Inject (idempotent)
p2 = playwright_util.inject_annotations()
# Expect: {success: true, ready: true, version: "2.0.0"}

# 3. Highlight with custom element_id and color
p3 = playwright_util.highlight_element(selector="a", label="Test link", color="blue", element_id="test-1")
# Expect: {success: true, count: >= 1, ids: ["test-1-0", "test-1-1", ...]}

# 4. Scan annotations
p4 = playwright_util.scan_annotations()
# Expect: list with annotations containing: id, label, selector, content, tagName, color
# Verify: len(p4) >= 1

# 5. Guide user (multi-step) - use simple selectors
p5 = playwright_util.guide_user(
    task="Navigate",
    steps=[
        {"selector": "h1", "label": "Step 1: Heading", "color": "orange"},
        {"selector": "p", "label": "Step 2: Paragraph", "color": "green"}
    ]
)
# Expect: {task: "Navigate", total: 2, highlighted: 2, results: [...]}

# 6. Clear all annotations
p6 = playwright_util.clear_annotations()
# Expect: {success: true, cleared: >= 1}

# 7. Verify cleared
p7 = playwright_util.scan_annotations()
# Expect: empty list []

# 8. Take screenshot for verification
playwright.take_screenshot()

# Print summary
{
    "inject": p1.get("version"),
    "idempotent": p2.get("ready"),
    "highlighted": p3.get("count"),
    "scanned": len(p4),
    "guide_steps": p5.get("highlighted"),
    "cleared": p6.get("cleared"),
    "final_count": len(p7)
}
```

## Expected results

Each pack should produce identical results (same structure, same field names). Differences in annotation IDs or counts are acceptable due to different browser instances.

### Key behaviors to verify:
- **Indexed IDs:** Multiple matching elements get indexed IDs (e.g., `test-1-0`, `test-1-1`)
- **Rich metadata:** Scan returns id, label, selector, content, tagName, color
- **Idempotency:** Re-injection doesn't fail or duplicate
- **Clean removal:** Clear followed by scan returns empty array
- **Multi-step guidance:** Each step gets its own ID namespace (e.g., `guide-0-0`, `guide-1-0`)

### Screenshot verification:
After tests complete, take a screenshot to verify clean state:
```python
devtools.take_screenshot()
```

## Troubleshooting

**Prompt dialog appears during testing:**
- **Cause:** User manually pressed CMD-I/Ctrl+I during test
- **Solution:** Run `devtools.handle_dialog(action="dismiss")` or `playwright.handle_dialog(action="dismiss")`
- **Prevention:** Do not interact with browser during automated tests

**"No page selected" error (DevTools):**
- **Solution:** Create a new page with `devtools.new_page(url="https://example.com")`
- Or list and select existing page: `devtools.list_pages()` → `devtools.select_page(page_id=N)`

**"The selected page has been closed" error:**
- **Solution:** The browser page was closed - create a new one with `devtools.new_page(url="...")`

**"Server not connected" error:**
- **Solution:** Check server status with `ot.servers()`
- If server is missing, skip that pack's tests and note in findings

**Empty scan results after highlighting:**
- **Solution:** Verify injection succeeded first: check `inject_annotations()` returns `success: true`
- Verify selector matches elements: Try simpler selectors like `"h1"` or `"p"`
- For Wikipedia, use: `"h1"`, `"p"`, `"a"`, `".mw-headline"` as reliable selectors

**Test URL:**
- **Use:** `https://en.wikipedia.org/wiki/Anthropic` - Stable, reliable, good variety of selectors
- **Avoid:** Complex SPAs or frequently changing pages

## UI Features

**CMD-I Annotation Prompt:** When users press CMD-I (or Ctrl+I) and click an element, a prompt dialog appears where they can enter a custom name for the annotation. The prompt defaults to the element's tag name (e.g., "button", "input") but allows full customization. Users can:
- Enter a custom label to create the annotation
- Leave empty to use the tag name as default
- Cancel to exit selection mode without creating an annotation

## Cleanup

After tests complete, clean up the browser state:

```python
# DevTools cleanup
try:
    chrome_devtools_util.clear_annotations()
    devtools.handle_dialog(action="dismiss")
except:
    pass

# Playwright cleanup
try:
    playwright_util.clear_annotations()
    playwright.handle_dialog(action="dismiss")
except:
    pass
```

## Write findings

Write comprehensive findings to `wip/test-output/browser-util-test.md`

### Required sections:
1. **Test Environment** - Date, servers tested, test page URL
2. **Test Results** - Pass/fail for each of 7 test steps per server
3. **Feature Verification** - Confirm inject.js v2.0.0 loaded
4. **Observations** - Strengths, issues, ID patterns
5. **Comparison** - Differences between chrome_devtools_util and playwright_util (if both tested)
6. **Screenshots** - Annotated states and clean final state
7. **Manual Testing Notes** - CMD-I prompt UI requires separate manual verification
8. **Conclusion** - Overall status, defects found (if any), recommendations
