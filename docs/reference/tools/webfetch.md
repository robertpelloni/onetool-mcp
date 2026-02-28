# Webfetch

Extracts main content from web pages, filtering navigation, ads, and boilerplate.

Short alias: `wf`

## Highlights

- Clean content extraction filtering navigation and ads
- Multiple output formats (markdown, text, json)
- Batch processing with concurrent execution
- Output truncation with max_length parameter
- URL validation with helpful error messages
- JSON-structured errors when using json output format
- Optional HTTP response metadata
- Non-HTML content (plain text, JSON, XML, CSV) returned directly without extraction

## Functions

| Function | Description |
|----------|-------------|
| `webfetch.fetch(url, ...)` | Fetch and extract content from a URL |
| `webfetch.fetch_batch(urls, ...)` | Fetch multiple URLs concurrently |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | str | URL to fetch content from |
| `output_format` | str | "markdown" (default), "text", "json" |
| `include_links` | bool | Include links in output |
| `include_images` | bool | Include image references |
| `include_tables` | bool | Include tables in output (default: True) |
| `include_comments` | bool | Include comments section |
| `include_formatting` | bool | Preserve headers/lists (default: True) |
| `include_metadata` | bool | Include HTTP metadata in JSON output |
| `favor_precision` | bool | Prefer accuracy over completeness |
| `favor_recall` | bool | Prefer completeness over accuracy |
| `fast` | bool | Skip fallback extraction for speed |
| `target_language` | str | Filter by ISO 639-1 language code |
| `max_length` | int | Truncate output to this length |
| `timeout` | float | Request timeout in seconds (defaults to config) |
| `use_cache` | bool | Use cached pages (default: True) |

Note: `favor_precision` and `favor_recall` are mutually exclusive.

## Configuration

### Required

- No required `tools.webfetch` settings.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.webfetch.timeout` | float | `30.0` | Request timeout in seconds. Range: `1.0-120.0`. |
| `tools.webfetch.max_length` | int | `50000` | Max extracted content length in characters. Range: `1000-500000`. |

```yaml
tools:
  webfetch:
    timeout: 30.0
    max_length: 50000
```

### Defaults

- If `tools.webfetch` is omitted, web fetch uses the built-in timeout and max length shown above.

## Examples

```python
# Fetch single URL
webfetch.fetch(url="https://example.com/article")

# Fetch with markdown output
webfetch.fetch(url="https://docs.python.org/3/tutorial/", output_format="markdown")

# Fast mode without fallback
webfetch.fetch(url="https://example.com/page", fast=True)

# JSON output with metadata
webfetch.fetch(
    url="https://example.com/article",
    output_format="json",
    include_metadata=True
)

# Precision mode for cleaner extraction
webfetch.fetch(url="https://example.com/page", favor_precision=True)

# Batch fetch multiple URLs
webfetch.fetch_batch(urls=[
    "https://example.com/page1",
    "https://example.com/page2"
])

# Batch with all options
webfetch.fetch_batch(
    urls=["https://example.com/page1", "https://example.com/page2"],
    include_links=True,
    favor_precision=True,
    fast=True
)

# Fetch plain text or JSON files (returned directly without extraction)
webfetch.fetch(url="https://example.com/data.json")
webfetch.fetch(url="https://example.com/robots.txt")
```
