# Knowledge

Portable SQLite knowledge bases with hybrid FTS5+vector search and AI synthesis. Short alias: `knowledge` (`kb`).

## Highlights

- Hybrid FTS5+vector search via `kb.search()` — keyword, semantic, or combined (hybrid) modes
- AI synthesis via `kb.ask()` — retrieves relevant chunks then synthesises a concise answer with source citations
- Personal annotations via `kb.write()` — store rules, notes, and mistakes alongside indexed content
- Link-graph traversal via `kb.related()` — follow markdown hyperlinks between topics

## Functions

| Function | Description |
|----------|-------------|
| `kb.write(topic, content, db, ...)` | Write a personal annotation to the knowledge database |
| `kb.read(topic, db, ...)` | Read a single entry by topic |
| `kb.update(topic, db, ...)` | Update an existing entry |
| `kb.append(topic, db, ...)` | Append content to an existing entry |
| `kb.delete(topic, db, ...)` | Delete an entry by topic |
| `kb.search(q, db, ...)` | Hybrid FTS5+vector search (mode: hybrid/semantic/keyword) |
| `kb.ask(q, db, ...)` | Retrieve relevant chunks and synthesise an AI answer |
| `kb.grep(pattern, db, ...)` | Regex/text search across all content |
| `kb.related(topic, db, ...)` | Find entries linked from or to a given topic |
| `kb.list(db, ...)` | List entries (returns meta only, no content) |
| `kb.toc(db, ...)` | Display table of contents for a database or topic prefix |
| `kb.slice(topic, db, ...)` | Extract a section from a large entry |
| `kb.stats(db)` | Chunk counts, embedding coverage, and file size |
| `kb.info(db)` | Database metadata, path, and version |
| `kb.dbs()` | List all configured knowledge databases |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | str | Search or question text |
| `db` | str | Database name (as configured under `tools.knowledge.kb`) |
| `topic` | str | Entry topic path (e.g. `python/tips/generators`) |
| `mode` | str | Search mode: `"hybrid"` (default), `"semantic"` (vector-only), `"keyword"` (FTS5-only) |
| `k` | int | Max results (default: `config.search_limit`) |
| `category` | str | Entry category filter — one of: `reference`, `rule`, `note`, `mistake` |
| `source` | str | Filter by `meta.source` prefix |
| `direction` | str | For `kb.related()`: `"out"` (links from topic), `"in"` (links to topic), `"both"` |
| `depth` | int | For `kb.related()`: traversal depth (default: 1) |

## Requires

- `OPENAI_API_KEY` in `secrets.yaml` (for embeddings and AI synthesis)
- `pip install sqlite-vec` (or `pip install onetool-mcp[util]`)
- `pip install python-frontmatter` (or `pip install onetool-mcp[util]`)

## Configuration

### Required

- `OPENAI_API_KEY` must be set in `secrets.yaml` for embeddings and `kb.ask()`.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.knowledge.model` | string | `""` | OpenAI embedding model. Falls back to `llm.embedding_model`; built-in default: `text-embedding-3-small`. |
| `tools.knowledge.base_url` | string | `""` | OpenAI-compatible API base URL. Empty = inherit from top-level `llm.base_url`. |
| `tools.knowledge.dimensions` | int | `1536` | Embedding dimensions. Must match the configured model. |
| `tools.knowledge.max_embedding_tokens` | int | `8191` | Max tokens per embedding input. |
| `tools.knowledge.embedding_batch_size` | int | `200` | Texts per embeddings API call. Range: `1-2048`. |
| `tools.knowledge.search_limit` | int | `10` | Default max search results. Range: `1-100`. |
| `tools.knowledge.search_extract` | int | `300` | Character limit for content extract in search results (`0` = full). |
| `tools.knowledge.enrich_model` | string | `""` | LLM model for `kb.ask()` synthesis. Empty = falls back to top-level `llm.model`. |
| `tools.knowledge.min_chunk_chars` | int | `200` | Minimum body characters per chunk. Chunks below threshold are merged. `0` disables. |

Project registry (under `tools.knowledge.kb`):

```yaml
tools:
  knowledge:
    model: text-embedding-3-small
    base_url: ""
    dimensions: 1536
    search_limit: 10
    search_extract: 300
    enrich_model: ""
    min_chunk_chars: 200
    kb:
      docs:
        db:
          path: kb/docs.db
          description: Scraped documentation
          embeddings_enabled: true
        scrape:
          output_base_dir: /path/to/scraped/docs
          sources:
            python:
              url: https://docs.python.org/3/
              url_prefix: /3/
```

### Defaults

- If `tools.knowledge.base_url` is empty, it inherits from the top-level `llm.base_url`.
- If `tools.knowledge.model` is empty, it inherits from `llm.embedding_model`.
- If `tools.knowledge.enrich_model` is empty, it falls back to `llm.model`.

## Examples

```python
# Search a knowledge base (hybrid FTS5+vector)
kb.search(q='context managers', db='docs')

# Keyword-only search with more results
kb.search(q='yield generator', db='docs', mode='keyword', k=20)

# AI synthesis — retrieves relevant chunks then answers
kb.ask(q='How do I configure authentication?', db='docs')

# Write a personal annotation
kb.write(topic='python/tips/loops', content='Use enumerate() for index access', db='docs', category='rule')

# Grep for a pattern across all content
kb.grep(pattern='def __init__', db='docs')

# Follow related topics via link graph
kb.related(topic='python/asyncio/tasks', db='docs', direction='out', depth=2)

# List all configured databases
kb.dbs()

# Check database stats
kb.stats(db='docs')

# Read a specific entry
kb.read(topic='python/tips/loops', db='docs')
```
