# Context Store

TTL-expiring, BM25-indexed storage for large tool outputs. Replace context-window saturation with targeted retrieval.

## TL;DR

- Store content with `ctx.write()` and get a handle in ~1ms.
- Retrieve with `ctx.read()`, `ctx.search()`, `ctx.grep()`, `ctx.slice()`, and `ctx.toc()`.
- Transform with `ctx.transform()` (requires ot_llm pack).
- Maintain with `ctx.append()`, `ctx.inspect()`, `ctx.list()`, `ctx.stats()`, `ctx.delete()`, and `ctx.purge()`.

## Highlights

- Handles large outputs (API responses, logs, docs) without saturating the context window
- BM25 search with three-layer fallback: Porter FTS5 → trigram FTS5 → Levenshtein correction
- ~1ms write latency — indexing runs in a background daemon thread
- TTL-expiring handles (default 3600s); no-expiry with `ttl=0`
- Large content (>256KB) spills to disk automatically; handle stays the same
- Regex and fuzzy grep with context lines
- Section slicing by number, heading, or line range
- Optional semantic embeddings via ot_llm (when configured)
- Pure stdlib — no external dependencies

## Functions

| Function | Description |
|----------|-------------|
| `ctx.write(content, source, intent)` | Store content, return handle + preview |
| `ctx.append(handle, content)` | Append content and re-index |
| `ctx.read(handle, offset, limit, tail, mode)` | Paginated raw content, metadata, or TOC |
| `ctx.toc(handle)` | Numbered section index with vocabulary hints |
| `ctx.search(handle, queries, limit)` | BM25 section search with three-layer fallback |
| `ctx.grep(handle, pattern, context, fuzzy)` | Regex or fuzzy line search |
| `ctx.slice(handle, select)` | Extract by section number, heading, or line range |
| `ctx.transform(handle, intent, json_mode)` | LLM extraction via ot_llm (optional) |
| `ctx.list(source, status)` | All active handles with summary |
| `ctx.inspect(handle)` | Detailed metadata for one handle |
| `ctx.stats()` | Session storage metrics |
| `ctx.delete(handle)` | Remove one handle |
| `ctx.purge(all, minutes, source, status)` | Bulk-delete handles and compact DB |

## Key Parameters

### `ctx.write()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `content` | str | Content to store |
| `source` | str | Optional label (e.g. "brave", "api") for filtering |
| `intent` | str | Optional intent — calls ot_llm immediately and returns `answer` field |

Returns a dict with `handle`, `size_bytes`, `total_lines`, `preview` (first 5 lines), and `usage` (ready-to-use call strings).

### `ctx.read()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `handle` | str | Handle from ctx.write() |
| `offset` | int | 1-indexed starting line (default 1) |
| `limit` | int | Max lines to return (default 100) |
| `tail` | int | Return last N lines; overrides offset/limit |
| `mode` | str | `"toc"` → section index; `"meta"` → metadata only |

### `ctx.search()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `handle` | str | Handle from ctx.write() |
| `queries` | list[str] | One or more search queries |
| `limit` | int | Max results per query (default 5) |

Returns sections with `title`, `snippet`, `score`, and `matchLayer` (`porter`/`trigram`/`fuzzy`).

### `ctx.grep()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `handle` | str | Handle from ctx.write() |
| `pattern` | str | Regex pattern (or plain text if `fuzzy=True`) |
| `context` | int | Lines before/after each match (default 0) |
| `fuzzy` | bool | Use SequenceMatcher instead of regex |

### `ctx.slice()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `handle` | str | Handle from ctx.write() |
| `select` | int or str | Section number (int), line range `"N:M"`, or heading substring |

### `ctx.purge()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `all` | bool | Bypass the age filter — delete all matching handles regardless of age |
| `minutes` | int | Delete handles older than N minutes (default 15) |
| `source` | str | Delete handles matching source substring |
| `status` | str | Delete handles with this status |

With no arguments, deletes handles older than 15 minutes, then compacts the DB.

## Configuration

Ctx reads from `onetool.yaml` under `tools.ctx`:

```yaml
tools:
  ctx:
    ttl: 3600           # Handle TTL in seconds (0 = no expiry)
    max_inline_bytes: 1048576  # Spill to file above this size (default 1MB)
    embedding_model: ""  # Optional: ot_llm model for semantic embeddings
```

## Examples

```python
# Store API response and search it
h = ctx.write(big_json_output, source="api")
ctx.search(h["handle"], queries=["error", "timeout"])

# Read a log file page-by-page
h = ctx.write(log_content, source="logs")
ctx.read(h["handle"], offset=1, limit=50)
ctx.read(h["handle"], offset=51, limit=50)

# Get the last 20 lines
ctx.read(h["handle"], tail=20)

# TOC navigation
ctx.toc(h["handle"])
ctx.slice(h["handle"], select="Installation")  # by heading
ctx.slice(h["handle"], select=3)               # by section number
ctx.slice(h["handle"], select="10:25")         # by line range

# Grep with context
ctx.grep(h["handle"], pattern=r"ERROR|WARN", context=2)

# LLM extraction (requires ot_llm pack)
ctx.transform(h["handle"], intent="list all API endpoints as JSON", json_mode=True)

# Maintenance
ctx.list()                           # all active handles
ctx.stats()                          # storage metrics
ctx.purge()                          # delete expired handles + compact
ctx.purge(all=True)                  # wipe everything
ctx.purge(status="failed")           # remove failed indexing handles
ctx.purge(minutes=60)                # remove handles older than 1 hour
ctx.delete(h["handle"])              # remove one handle
```
