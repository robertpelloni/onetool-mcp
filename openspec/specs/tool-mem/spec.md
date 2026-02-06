# tool-mem Specification

## Purpose

Persistent memory for AI agents with DuckDB storage and OpenAI embeddings. Provides topic-based memory storage with semantic search, content dedup, secret redaction, and importance decay. Requires `OPENAI_API_KEY` in secrets.yaml.

## Requirements

### Requirement: Memory Storage

The `mem.write()` function SHALL store memories with topic, content, and metadata.

#### Scenario: Basic write
- **GIVEN** a topic and content
- **WHEN** `mem.write(topic="projects/onetool/rules", content="Always use keyword-only args")` is called
- **THEN** it SHALL store the memory with a generated UUID
- **AND** it SHALL generate an embedding for semantic search
- **AND** it SHALL compute a SHA-256 content hash for dedup

#### Scenario: Duplicate detection
- **GIVEN** a memory already exists with the same topic and content hash
- **WHEN** `mem.write()` is called with identical content for the same topic
- **THEN** it SHALL reject the write with a "Duplicate" message
- **AND** it SHALL return the existing memory ID

#### Scenario: Write from file
- **GIVEN** a file path
- **WHEN** `mem.write(topic="config", file="~/.onetool/config/onetool.yaml")` is called
- **THEN** it SHALL read content from the file
- **AND** store it as a memory

#### Scenario: Relevance validation
- **GIVEN** a relevance value outside 1-10
- **WHEN** `mem.write(topic="test", content="text", relevance=0)` is called
- **THEN** it SHALL return an error indicating relevance must be between 1 and 10

#### Scenario: File size limit
- **GIVEN** a file larger than 1MB
- **WHEN** `mem.write(topic="test", file="large_file.bin")` is called
- **THEN** it SHALL reject the write with a "file too large" error

#### Scenario: Batch write from glob
- **GIVEN** a glob pattern
- **WHEN** `mem.write_batch(topic="docs", glob_pattern="docs/**/*.md")` is called
- **THEN** it SHALL create a memory per file
- **AND** preserve directory structure relative to the glob root as subtopic (e.g., `docs/sub/file` not `docs/file`)

### Requirement: Memory Retrieval

The `mem.read()` function SHALL retrieve memories by topic or ID.

#### Scenario: Read by topic
- **GIVEN** a memory exists with the topic
- **WHEN** `mem.read(topic="projects/onetool/rules")` is called
- **THEN** it SHALL return the content (metadata included only when `meta=True`)
- **AND** increment the access count

#### Scenario: Read by ID
- **GIVEN** a memory ID
- **WHEN** `mem.read(id="abc-123")` is called
- **THEN** it SHALL return the memory regardless of topic

### Requirement: Batch Retrieval

The `mem.read_batch()` function SHALL retrieve full content for multiple memories.

#### Scenario: Read by topic prefix
- **GIVEN** memories exist under a topic prefix
- **WHEN** `mem.read_batch(topic="projects/onetool/agents/")` is called
- **THEN** it SHALL return full content for all matching memories
- **AND** increment access counts for each

#### Scenario: Read by IDs
- **GIVEN** a list of memory IDs
- **WHEN** `mem.read_batch(ids=["abc-123", "def-456"])` is called
- **THEN** it SHALL return full content for those specific memories

#### Scenario: IDs cannot combine with other filters
- **GIVEN** `ids` is provided alongside `topic`, `category`, or `tags`
- **WHEN** `mem.read_batch(ids=["abc"], category="rule")` is called
- **THEN** it SHALL return an error indicating ids cannot be combined with other filters

#### Scenario: Filter required
- **GIVEN** no filter parameters provided
- **WHEN** `mem.read_batch()` is called
- **THEN** it SHALL return an error requiring at least one filter

#### Scenario: Metadata headers
- **GIVEN** `meta=True`
- **WHEN** `mem.read_batch(topic="projects/", meta=True)` is called
- **THEN** each memory SHALL include a metadata header (topic, category, tags, etc.)

### Requirement: Memory Search

The `mem.search()` function SHALL search memories in three modes.

#### Scenario: Semantic search
- **GIVEN** a query string
- **WHEN** `mem.search(query="authentication patterns")` is called
- **THEN** it SHALL generate a query embedding
- **AND** rank results by cosine similarity

#### Scenario: Pattern search
- **GIVEN** a pattern query
- **WHEN** `mem.search(query="database", mode="pattern")` is called
- **THEN** it SHALL match using ILIKE on content and topic

#### Scenario: Hybrid search
- **GIVEN** a query with mode="hybrid"
- **WHEN** `mem.search(query="error handling", mode="hybrid")` is called
- **THEN** it SHALL combine semantic and pattern results via Reciprocal Rank Fusion

#### Scenario: Search extract length
- **GIVEN** a search query and content longer than the extract limit
- **WHEN** `mem.search(query="test", extract=50)` is called
- **THEN** result content extracts SHALL be truncated to 50 characters with "..."
- **AND** `extract=0` SHALL return full content without truncation
- **AND** default extract length SHALL come from config `search_extract` (default: 200)

#### Scenario: Topic and category filtering
- **GIVEN** optional topic and category filters
- **WHEN** `mem.search(query="rules", topic="projects/", category="rule")` is called
- **THEN** it SHALL restrict results to matching topic prefix and category

### Requirement: Memory Management

The `mem.update()`, `mem.append()`, and `mem.delete()` functions SHALL manage existing memories.

#### Scenario: Update single memory
- **GIVEN** a topic matching exactly one memory
- **WHEN** `mem.update(topic="projects/rules", content="new text")` is called
- **THEN** it SHALL update the content and re-generate the embedding
- **AND** it SHALL store the old content in memory_history

#### Scenario: Update rejects multiple matches
- **GIVEN** a topic matching multiple memories
- **WHEN** `mem.update()` is called
- **THEN** it SHALL return an error suggesting to use id= parameter

#### Scenario: Append content
- **GIVEN** an existing memory
- **WHEN** `mem.append(topic="rules", content="new rule")` is called
- **THEN** it SHALL append to existing content with separator
- **AND** store old content in history

#### Scenario: Delete by ID
- **GIVEN** a memory ID
- **WHEN** `mem.delete(id="abc-123")` is called
- **THEN** it SHALL delete the memory and its history

#### Scenario: Delete by topic requires confirm
- **GIVEN** a topic matching multiple memories
- **WHEN** `mem.delete(topic="projects/old/")` is called without confirm=True
- **THEN** it SHALL return a warning with the count
- **AND** require confirm=True to proceed

### Requirement: Secret Redaction

Content SHALL be automatically redacted before storage.

#### Scenario: API key redaction
- **GIVEN** content containing API keys (sk-..., ghp_..., AKIA...)
- **WHEN** stored via `mem.write()`
- **THEN** keys SHALL be replaced with [REDACTED:api_key] or similar

#### Scenario: Connection string redaction
- **GIVEN** content containing connection strings
- **WHEN** stored via `mem.write()`
- **THEN** credentials SHALL be redacted

#### Scenario: Redaction can be disabled
- **GIVEN** config `redaction_enabled: false`
- **WHEN** content is stored
- **THEN** no redaction SHALL be applied

### Requirement: Tag Validation

Tags SHALL be validated against a configurable whitelist.

#### Scenario: No whitelist allows all
- **GIVEN** empty tags_whitelist config
- **WHEN** any tags are provided
- **THEN** all tags SHALL be accepted

#### Scenario: Whitelist restricts tags
- **GIVEN** `tags_whitelist: ["project/*", "language"]`
- **WHEN** tag "forbidden" is provided
- **THEN** it SHALL raise a validation error

### Requirement: Context Loading

The `mem.context()` function SHALL load most-accessed memories.

#### Scenario: Hot cache
- **WHEN** `mem.context(topic="projects/onetool/", limit=5)` is called
- **THEN** it SHALL return the top-5 memories by access count
- **AND** increment their access counts

### Requirement: Batch Update

The `mem.update_batch()` function SHALL support search-and-replace.

#### Scenario: Dry run preview
- **WHEN** `mem.update_batch(search_text="old", replace_text="new", dry_run=True)` is called
- **THEN** it SHALL preview matching memories without modifying

#### Scenario: Apply changes
- **WHEN** `mem.update_batch(search_text="old", replace_text="new", dry_run=False)` is called
- **THEN** it SHALL update content, save history, and re-generate embeddings

### Requirement: Importance Decay

The `mem.decay()` function SHALL apply time-based importance decay.

#### Scenario: Decay formula
- **GIVEN** a memory with relevance, age, and access count
- **WHEN** decay is applied
- **THEN** new score = relevance * 0.5^(age/half_life) * (1 + log(access+1) * 0.1)
- **AND** result is clamped to 1-10

### Requirement: Export and Import

The `mem.export()` and `mem.load()` functions SHALL support YAML and Markdown formats.

#### Scenario: Export to YAML
- **WHEN** `mem.export(format="yaml")` is called
- **THEN** it SHALL output all memories in YAML format

#### Scenario: Export to Markdown
- **WHEN** `mem.export(format="markdown")` is called
- **THEN** it SHALL output memories grouped by topic

#### Scenario: Import from YAML
- **WHEN** `mem.load(file="backup.yaml")` is called
- **THEN** it SHALL import memories, skipping duplicates by default

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
    allowed_file_dirs: []
    exclude_file_patterns: [".git", "node_modules", "__pycache__", ".venv", "venv"]
```

## Schema

```sql
CREATE TABLE memories (
    id             VARCHAR PRIMARY KEY,
    topic          VARCHAR NOT NULL,
    content        TEXT NOT NULL,
    content_hash   VARCHAR NOT NULL,
    category       VARCHAR DEFAULT 'note',
    tags           VARCHAR[],
    relevance      INTEGER DEFAULT 5,
    access_count   INTEGER DEFAULT 0,
    created_at     TIMESTAMP DEFAULT now(),
    updated_at     TIMESTAMP DEFAULT now(),
    last_accessed  TIMESTAMP DEFAULT now(),
    embedding      FLOAT[1536]
);

CREATE TABLE memory_history (
    id             VARCHAR PRIMARY KEY,
    memory_id      VARCHAR NOT NULL,
    content        TEXT NOT NULL,
    updated_at     TIMESTAMP DEFAULT now()
);
```
