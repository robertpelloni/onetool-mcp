# ctx Specification

## Purpose

Defines the `ctx` pack providing a smart-context store backed by SQLite+FTS5. The pack enables agents to store, index, search, and navigate large content blobs without filling the context window. Content is stored with a TTL, indexed asynchronously via BM25/FTS5, and accessible through a set of focused read/search/navigation tools.

## Requirements

### Requirement: Write Content to Context Store

The `ctx.write()` function SHALL store content immediately, begin background indexing, and return a handle with preview.

#### Scenario: Basic write
- **WHEN** `ctx.write("some content")` is called
- **THEN** it SHALL return a dict containing `handle`, `source`, `size_bytes`, `total_lines`, `content_type`, `preview`, `status`, and `usage`
- **AND** `status` SHALL be `"pending"` or `"indexing"` (never `"ready"` — indexing is async)
- **AND** `handle` SHALL be a short opaque string (e.g. 8 hex chars)
- **AND** `content_type` SHALL be `"markdown"` if the content contains markdown headings (`# ` lines), otherwise `"text"`

#### Scenario: Write with source label
- **WHEN** `ctx.write(content, source="webfetch:docs.example.com")` is called
- **THEN** `source` SHALL appear in the returned dict and be stored for `ctx.list`

#### Scenario: Write with intent
- **WHEN** `ctx.write(content, intent="how to authenticate")` is called
- **THEN** in addition to the standard response, it SHALL also include an `answer` field with an LLM-extracted focused answer
- **AND** if `ot_llm` is not configured it SHALL include an `answer_error` field instead of raising

#### Scenario: Write returns quickly
- **WHEN** `ctx.write(large_content)` is called with content >50KB
- **THEN** it SHALL return in under 100ms
- **AND** FTS5 indexing SHALL complete asynchronously in the background

#### Scenario: Preview lines
- **WHEN** `ctx.write(content)` is called
- **THEN** `preview` SHALL contain the first 5 non-empty lines of content
- **AND** `usage` SHALL be a dict of ready-to-run `ctx.*` calls containing the handle

---

### Requirement: Read Raw Content

The `ctx.read()` function SHALL return paginated raw content from a stored handle.

#### Scenario: Basic read with defaults
- **GIVEN** a stored handle `h`
- **WHEN** `ctx.read(h)` is called
- **THEN** it SHALL return lines 1–100 (default offset=1, limit=100)
- **AND** response SHALL include `lines`, `total_lines`, `returned`, `offset`, `has_more`, `progress`, `total_size_bytes`

#### Scenario: Read with offset and limit
- **GIVEN** a handle with 500 lines
- **WHEN** `ctx.read(h, offset=101, limit=50)` is called
- **THEN** it SHALL return lines 101–150

#### Scenario: Read with tail
- **WHEN** `ctx.read(h, tail=20)` is called
- **THEN** it SHALL return the last 20 lines
- **AND** if tail > total_lines, all lines SHALL be returned

#### Scenario: Read mode toc
- **WHEN** `ctx.read(h, mode="toc")` is called
- **THEN** it SHALL return a numbered section index equivalent to `ctx.toc(h)`

#### Scenario: Read mode meta
- **WHEN** `ctx.read(h, mode="meta")` is called
- **THEN** it SHALL return handle metadata: source, size_bytes, total_lines, status, created_at, access_count

#### Scenario: Unknown handle
- **GIVEN** handle `"badhandle"` does not exist
- **WHEN** `ctx.read("badhandle")` is called
- **THEN** it SHALL return an error message indicating handle not found

#### Scenario: Expired handle
- **GIVEN** a handle that has exceeded TTL
- **WHEN** `ctx.read(h)` is called
- **THEN** it SHALL return an error message indicating the handle has expired

---

### Requirement: BM25 Section Search

The `ctx.search()` function SHALL return BM25-ranked sections matching one or more queries with smart snippets and three-layer fallback.

#### Scenario: Basic search
- **GIVEN** a ready handle containing indexed content
- **WHEN** `ctx.search(h, queries=["authentication"])` is called
- **THEN** it SHALL return a list of sections ranked by BM25 relevance
- **AND** each section SHALL include `title`, `snippet`, `matchLayer`, and `score`

#### Scenario: Multi-query search
- **WHEN** `ctx.search(h, queries=["auth", "rate limits"])` is called
- **THEN** it SHALL return results for each query grouped by query

#### Scenario: Smart snippet extraction
- **WHEN** a section matches a query
- **THEN** `snippet` SHALL be a ±300-character window around the matched term positions
- **AND** SHALL NOT be an arbitrary prefix of the section

#### Scenario: Porter stemming layer
- **GIVEN** content containing "authentication"
- **WHEN** `ctx.search(h, queries=["authenticate"])` is called
- **THEN** it SHALL match via Porter stemming
- **AND** `matchLayer` SHALL be `"porter"`

#### Scenario: Trigram fallback
- **GIVEN** Porter stemming yields no results
- **WHEN** the query is a partial identifier like `"useEff"`
- **THEN** it SHALL match via trigram substring search
- **AND** `matchLayer` SHALL be `"trigram"`

#### Scenario: Fuzzy fallback
- **GIVEN** Porter and trigram both yield no results
- **WHEN** the query contains a typo like `"autentication"`
- **THEN** it SHALL apply Levenshtein correction and retry
- **AND** `matchLayer` SHALL be `"fuzzy"`

#### Scenario: No results — vocabulary hints
- **GIVEN** a query yields no results after all three layers
- **WHEN** `ctx.search(h, queries=["zxqvbfoo"])` is called
- **THEN** response SHALL include a `vocabulary` list of distinctive terms from the handle
- **AND** `sections` SHALL be an empty list

#### Scenario: Search while indexing
- **GIVEN** a handle with `status="indexing"`
- **WHEN** `ctx.search(h, queries=["foo"])` is called
- **THEN** it SHALL wait up to 2 seconds for indexing to complete
- **AND** if indexing completes within 2s, it SHALL return normal search results
- **AND** if still indexing after 2s, it SHALL return `{status: "indexing", retry_in: "~Xs"}`

#### Scenario: Search on failed handle
- **GIVEN** a handle with `status="failed"`
- **WHEN** `ctx.search(h, queries=["foo"])` is called
- **THEN** it SHALL return an error message with a `ctx.repair(handle)` hint

---

### Requirement: Regex Line Search

The `ctx.grep()` function SHALL perform regex line search with optional context lines.

#### Scenario: Basic grep
- **GIVEN** a handle with lines containing "error" and lines without
- **WHEN** `ctx.grep(h, pattern="error")` is called
- **THEN** it SHALL return only lines matching the regex pattern

#### Scenario: Grep with context lines
- **WHEN** `ctx.grep(h, pattern="TARGET", context=2)` is called
- **THEN** it SHALL return matching lines plus 2 lines before and after each match
- **AND** non-contiguous groups SHALL be separated by `---`

#### Scenario: Grep with fuzzy
- **WHEN** `ctx.grep(h, pattern="config", fuzzy=True)` is called
- **THEN** it SHALL use fuzzy matching to find similar content
- **AND** results SHALL be sorted by match score

---

### Requirement: Section Slicing

The `ctx.slice()` function SHALL extract content by section number, heading path, or line range.

#### Scenario: Slice by section number
- **GIVEN** a handle with a section index
- **WHEN** `ctx.slice(h, select=2)` is called
- **THEN** it SHALL return the content of section 2

#### Scenario: Slice by heading path
- **WHEN** `ctx.slice(h, select="Authentication")` is called
- **THEN** it SHALL return the section whose title contains "Authentication"

#### Scenario: Slice by line range
- **WHEN** `ctx.slice(h, select="50:100")` is called
- **THEN** it SHALL return lines 50–100 inclusive

#### Scenario: Section not found
- **WHEN** `ctx.slice(h, select="NonExistentSection")` is called
- **THEN** it SHALL return an error message indicating section not found

---

### Requirement: Table of Contents

The `ctx.toc()` function SHALL return a numbered section index with line ranges and vocabulary hints.

#### Scenario: Table of contents for markdown content
- **GIVEN** a ready handle containing markdown content with headings
- **WHEN** `ctx.toc(h)` is called
- **THEN** it SHALL return a numbered list of sections with titles and line ranges
- **AND** SHALL include vocabulary hints (top distinctive terms)

#### Scenario: Table of contents while indexing
- **GIVEN** a handle with `status="indexing"` or `"pending"`
- **WHEN** `ctx.toc(h)` is called
- **THEN** it SHALL return a preview based on raw content headings without waiting

---

### Requirement: LLM Extraction

The `ctx.transform()` function SHALL use `ot_llm` to synthesise a focused answer from stored content.

#### Scenario: Basic transform
- **GIVEN** `ot_llm` is configured and a ready handle
- **WHEN** `ctx.transform(h, intent="how to install")` is called
- **THEN** it SHALL return a focused text answer relevant to the intent

#### Scenario: JSON mode
- **WHEN** `ctx.transform(h, intent="list all endpoints", json_mode=True)` is called
- **THEN** it SHALL return a JSON-parseable string

#### Scenario: ot_llm not configured
- **GIVEN** `ot_llm` is not configured (no base_url or API key)
- **WHEN** `ctx.transform(h, intent="anything")` is called
- **THEN** it SHALL return a clear error message explaining that `ot_llm` must be configured
- **AND** SHALL NOT raise an unhandled exception

---

### Requirement: Append Content

The `ctx.append()` function SHALL add content to an existing handle and re-trigger background indexing.

#### Scenario: Basic append
- **GIVEN** a ready handle `h`
- **WHEN** `ctx.append(h, "additional content")` is called
- **THEN** the combined content SHALL be available via `ctx.read`
- **AND** `status` SHALL transition back to `"indexing"` while the index rebuilds

#### Scenario: Append to unknown handle
- **WHEN** `ctx.append("badhandle", "content")` is called
- **THEN** it SHALL return an error message indicating handle not found

---

### Requirement: List Active Handles

The `ctx.list()` function SHALL return all active (non-expired) handles with summary information.

#### Scenario: List all handles
- **WHEN** `ctx.list()` is called
- **THEN** it SHALL return a table of handles: handle, source, size, status, TTL remaining
- **AND** expired handles SHALL NOT appear

#### Scenario: Filter by source
- **WHEN** `ctx.list(source="webfetch")` is called
- **THEN** it SHALL return only handles whose source matches the pattern (substring)

#### Scenario: Filter by status
- **WHEN** `ctx.list(status="failed")` is called
- **THEN** it SHALL return only handles with that status

#### Scenario: Invalid status value
- **WHEN** `ctx.list(status="invalid_value")` is called
- **THEN** it SHALL raise `ValueError` immediately with a message listing valid values
- **AND** it SHALL NOT return a filtered (possibly empty) result silently

#### Scenario: Empty store
- **WHEN** no handles are active
- **THEN** `ctx.list()` SHALL return an empty list `[]`

---

### Requirement: Inspect Handle

The `ctx.inspect()` function SHALL return detailed metadata for a single handle.

#### Scenario: Inspect ready handle
- **GIVEN** a ready handle
- **WHEN** `ctx.inspect(h)` is called
- **THEN** it SHALL return: handle, source, size_bytes, total_lines, status, chunk_count, vocab_size, has_embeddings, ttl_remaining, access_count, is_file_pointer

#### Scenario: Inspect unknown handle
- **WHEN** `ctx.inspect("badhandle")` is called
- **THEN** it SHALL return an error message indicating handle not found

---

### Requirement: Session Statistics

The `ctx.stats()` function SHALL return session-level storage and savings metrics.

#### Scenario: Stats output
- **WHEN** `ctx.stats()` is called
- **THEN** it SHALL return: total_handles, handles_by_status (dict), total_bytes_stored, estimated_tokens_saved, db_size_bytes

---

### Requirement: Delete Handle

The `ctx.delete()` function SHALL remove a single handle and all associated data.

#### Scenario: Delete a handle
- **GIVEN** a stored handle `h`
- **WHEN** `ctx.delete(h)` is called
- **THEN** it SHALL remove the handle, content, chunks, vocabulary, and embeddings
- **AND** if `is_file=1`, the backing file SHALL also be unlinked
- **AND** subsequent `ctx.read(h)` SHALL return handle not found
- **AND** it SHALL return `{"deleted": h}`

#### Scenario: Delete unknown handle
- **WHEN** `ctx.delete("badhandle")` is called
- **THEN** it SHALL return `{"error": "Handle not found: badhandle"}`

---

### Requirement: Bulk Purge

The `ctx.purge()` function SHALL bulk-delete handles matching age, source, or status criteria.

#### Scenario: Default purge (older than 15 minutes)
- **WHEN** `ctx.purge()` is called with no arguments
- **THEN** it SHALL delete all handles created more than 15 minutes ago
- **AND** return `{"deleted": N, "bytes_freed": N}` where `bytes_freed` is the sum of `size_bytes` of deleted handles

#### Scenario: Purge by age
- **WHEN** `ctx.purge(minutes=60)` is called
- **THEN** it SHALL delete all handles created more than 60 minutes ago
- **AND** return a count of deleted handles

#### Scenario: Purge by source pattern
- **WHEN** `ctx.purge(source="webfetch")` is called
- **THEN** it SHALL delete all handles whose source matches "webfetch" AND are older than 15 minutes (default)

#### Scenario: Purge by status
- **WHEN** `ctx.purge(status="failed")` is called
- **THEN** it SHALL delete all handles with `status="failed"` AND older than 15 minutes (default)

#### Scenario: Purge all with source filter
- **WHEN** `ctx.purge(all=True, source="brave")` is called
- **THEN** it SHALL delete all handles whose source matches "brave" regardless of age
- **AND** handles from other sources SHALL NOT be deleted

#### Scenario: Purge all with status filter
- **WHEN** `ctx.purge(all=True, status="failed")` is called
- **THEN** it SHALL delete all handles with `status="failed"` regardless of age
- **AND** handles with other statuses SHALL NOT be deleted

#### Scenario: Purge with no matches
- **WHEN** no handles match the purge criteria
- **THEN** it SHALL return `{"deleted": 0, "bytes_freed": 0}`

#### Scenario: Zero or negative minutes raises
- **WHEN** `ctx.purge(minutes=0)` or `ctx.purge(minutes=-1)` is called
- **THEN** it SHALL raise `ValueError` with message containing "positive"

---

### Requirement: Repair Failed Handles

The `ctx.repair()` function SHALL rebuild the FTS5 index for failed or specified handles.

#### Scenario: Repair one handle
- **GIVEN** a handle with `status="failed"`
- **WHEN** `ctx.repair(h)` is called
- **THEN** it SHALL re-run the full indexing pipeline for that handle
- **AND** on success, `status` SHALL become `"ready"`

#### Scenario: Repair all failed
- **WHEN** `ctx.repair()` is called with no argument
- **THEN** it SHALL repair all handles with `status="failed"`
- **AND** return a count of repaired handles

---

### Requirement: Vacuum Database

The `ctx.vacuum()` function SHALL delete TTL-expired entries and compact the SQLite database.

#### Scenario: Vacuum removes expired entries
- **WHEN** `ctx.vacuum()` is called
- **THEN** it SHALL delete all handles past their TTL
- **AND** run SQLite `VACUUM` to compact the database
- **AND** return bytes freed

---

### Requirement: Flush All Handles

The `ctx.flush()` function SHALL delete all session handles unconditionally.

#### Scenario: Flush clears all handles
- **WHEN** `ctx.flush()` is called
- **THEN** all handles SHALL be deleted (content, chunks, vocabulary, embeddings, files)
- **AND** the database SHALL remain intact (schema not dropped)
- **AND** `ctx.list()` after flush SHALL return no active handles

---

### Requirement: Handle Status State Machine

Handles SHALL follow a defined status lifecycle.

#### Scenario: Status transitions
- **WHEN** `ctx.write` is called
- **THEN** handle status SHALL start as `"pending"`
- **AND** SHALL transition to `"indexing"` when the background thread starts
- **AND** SHALL transition to `"ready"` when FTS5 + vocabulary + optional embeddings complete
- **AND** SHALL transition to `"failed"` if any step in the pipeline raises an exception

#### Scenario: Stale indexing on restart
- **GIVEN** a handle with `status="indexing"` when the process exits
- **WHEN** the process restarts and `ctx.search` is called on that handle
- **THEN** it SHALL be treated as `"failed"` and return the repair hint

---

### Requirement: Configuration

The `ctx` pack SHALL support optional configuration via `onetool.yaml`.

#### Scenario: Default configuration
- **GIVEN** no `tools.ctx` block in `onetool.yaml`
- **WHEN** the ctx pack is used
- **THEN** TTL SHALL default to 3600 seconds (1 hour)
- **AND** embeddings SHALL be disabled (no API calls made)
- **AND** `max_inline_bytes` SHALL default to 1048576 (1MB)

#### Scenario: Custom TTL
- **GIVEN** `tools.ctx.ttl: 7200` in config
- **WHEN** a handle is written
- **THEN** its TTL SHALL be 7200 seconds

#### Scenario: Embedding model configured
- **GIVEN** `tools.ctx.embedding_model: "text-embedding-3-small"` in config
- **WHEN** a handle finishes indexing
- **THEN** the background pipeline SHALL also generate and store chunk embeddings
