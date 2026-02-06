# Memory

Persistent memory for AI agents with DuckDB storage and semantic search.

## Highlights

- Topic-based memory with path hierarchy (`projects/onetool/rules`)
- Semantic, pattern, and hybrid (RRF) search modes
- SHA-256 content dedup prevents duplicate storage
- Automatic secret/PII redaction on write
- History tracking on updates for rollback
- Importance decay based on age and access patterns
- YAML and Markdown export/import

## Functions

| Function | Description |
|----------|-------------|
| `mem.write(topic, content, ...)` | Store a memory |
| `mem.write_batch(topic, glob_pattern, ...)` | Bulk store from files (preserves directory structure) |
| `mem.read(topic, id)` | Read full content of a single memory |
| `mem.read_batch(topic, ids, ...)` | Read full content of multiple memories |
| `mem.search(query, mode, ...)` | Search memories (returns meta + truncated extract) |
| `mem.list_memories(topic, category)` | List memories (returns meta only, no content) |
| `mem.count(topic, category)` | Count memories |
| `mem.delete(topic, id, confirm)` | Delete memories |
| `mem.update(topic, content, id)` | Update a memory |
| `mem.append(topic, content, id)` | Append to a memory |
| `mem.context(topic, limit)` | Load hot cache context |
| `mem.update_batch(search_text, replace_text, ...)` | Batch search-and-replace |
| `mem.decay(dry_run)` | Apply importance decay |
| `mem.stats()` | Show statistics |
| `mem.export(format, topic, output)` | Export to YAML or Markdown |
| `mem.load(file, overwrite)` | Import from YAML |

## Retrieval Functions

The retrieval functions return different levels of detail:

| Function | Returns | Use when |
|----------|---------|----------|
| `mem.list_memories()` | Meta only (topic, category, relevance, access count, size, tags, id) | Browsing what's stored |
| `mem.search()` | Meta + truncated extract (default 200 chars, configurable via `extract`) | Finding relevant memories |
| `mem.read()` | Full content for a single memory (optionally with meta header via `meta=True`) | Reading one specific memory |
| `mem.read_batch()` | Full content for multiple memories with dividers | Reading several memories at once |

## Key Parameters

### `mem.write()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `topic` | str | Topic path using `/` separator |
| `content` | str | Memory content text |
| `category` | str | One of: rule, context, decision, mistake, discovery, note |
| `tags` | list | Optional tags for categorisation |
| `relevance` | int | Importance 1-10, enforced (default: 5) |
| `file` | str | Read content from file instead (max 1MB) |

### `mem.write_batch()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `topic` | str | Base topic path (relative file path appended as subtopic) |
| `glob_pattern` | str | Glob pattern to match files (e.g., "docs/**/*.md") |
| `category` | str | Category for all memories (default: note) |
| `tags` | list | Tags applied to all memories |
| `relevance` | int | Relevance score for all memories (default: 5) |

### `mem.search()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Search query text |
| `mode` | str | "semantic" (default), "pattern", or "hybrid" |
| `topic` | str | Topic prefix filter |
| `category` | str | Category filter |
| `limit` | int | Max results (default: config search_limit) |
| `tags` | list | Tag filter (matches any) |
| `extract` | int | Content extract char limit (default: config search_extract, 0 = full) |

### `mem.read_batch()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `topic` | str | Topic prefix filter |
| `ids` | list | Specific memory IDs to read |
| `category` | str | Category filter |
| `tags` | list | Tag filter (matches any) |
| `meta` | bool | Include metadata headers (default: False) |
| `limit` | int | Max results (default: 50) |

At least one filter (`topic`, `ids`, `category`, or `tags`) is required. Note: `ids` cannot be combined with other filters (`topic`, `category`, `tags`).

### `mem.update_batch()`

| Parameter | Type | Description |
|-----------|------|-------------|
| `search_text` | str | Text to find |
| `replace_text` | str | Replacement text |
| `topic` | str | Optional topic prefix scope |
| `dry_run` | bool | Preview only (default: True) |

## Configuration

```yaml
tools:
  mem:
    db_path: ~/.onetool/mem.db
    model: text-embedding-3-small
    base_url: https://openrouter.ai/api/v1
    dimensions: 1536
    search_limit: 10
    search_extract: 200
    redaction_enabled: true
    redaction_patterns: []
    tags_whitelist: []
    decay_half_life_days: 30
```

## Topic Hierarchy

Topics use `/` as separator for path-based hierarchy:

```
projects/onetool/rules
projects/onetool/decisions
learnings/python
learnings/duckdb
```

Filtering with trailing `/` matches all children: `topic="projects/"` matches everything under projects.

## Categories

| Category | Use |
|----------|-----|
| `rule` | Rules and constraints |
| `context` | Background information |
| `decision` | Architectural decisions |
| `mistake` | Errors and lessons learned |
| `discovery` | New findings |
| `note` | General notes (default) |

## Examples

```python
# Store a rule
mem.write(topic="projects/onetool/rules", content="Use keyword-only args", category="rule")

# Bulk store from files (preserves directory structure)
mem.write_batch(topic="docs", glob_pattern="docs/**/*.md", category="context")

# Search semantically
mem.search(query="authentication patterns")

# Pattern search with topic filter
mem.search(query="database", mode="pattern", topic="projects/")

# Search with longer extract
mem.search(query="rules", extract=500)

# Search with full content (no truncation)
mem.search(query="rules", extract=0)

# Read all memories under a topic
mem.read_batch(topic="projects/onetool/agents/")

# Read specific memories by ID with metadata
mem.read_batch(ids=["abc-123", "def-456"], meta=True)

# Load context for session
mem.context(topic="projects/onetool/", limit=10)

# Export backup
mem.export(format="yaml", output="memories.yaml")

# Batch update
mem.update_batch(search_text="old_name", replace_text="new_name", dry_run=False)

# Apply importance decay
mem.decay(dry_run=False)
```

## Requirements

- `OPENAI_API_KEY` in secrets.yaml for embedding generation
- DuckDB (bundled with OneTool)
