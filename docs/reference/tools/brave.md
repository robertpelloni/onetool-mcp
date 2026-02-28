# Brave Search

Web, news, image, and video search via Brave Search API.

Short alias: `br`

## Highlights

- Four search types: web, news, image, video
- Batch search with concurrent execution
- Query validation (400 char / 50 word limits)

## Functions

| Function | Description |
|----------|-------------|
| `brave.search(query, ...)` | General web search |
| `brave.news(query, ...)` | News articles (sorted by recency, most recent first) |
| `brave.image(query, ...)` | Image search |
| `brave.video(query, ...)` | Video search |
| `brave.search_batch(queries, ...)` | Multiple searches concurrently |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Search query (max 400 chars, 50 words) |
| `count` | int | Results per query (1-20) |
| `freshness` | str | "pd" (day), "pw" (week), "pm" (month), "py" (year), or "YYYY-MM-DDtoYYYY-MM-DD" date range |
| `safesearch` | str | "off", "moderate", "strict" |

## Requires

- `BRAVE_API_KEY` in secrets.yaml

## Configuration

### Required

- `BRAVE_API_KEY` must be set in `secrets.yaml`.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.brave.timeout` | float | `60.0` | Request timeout in seconds. Range: `1.0-300.0`. |

```yaml
tools:
  brave:
    timeout: 60.0
```

### Defaults

- If `tools.brave` is omitted, Brave uses the built-in timeout shown above.

## Examples

```python
# Web search
brave.search(query="python async tutorial", count=10)

# News with freshness filter
brave.news(query="AI announcements", freshness="pw")

# Batch search
brave.search_batch(queries=["react hooks", "vue composition api"])
```
