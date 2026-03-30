# KB Scrape Dry-Run Specification

## Purpose

Defines config threshold warnings for `onetool kb scrape`, emitted unconditionally on every run, and the `crawl_strategy` field for sources and projects.

---

## Requirements

### Requirement: Config threshold warnings
`onetool kb scrape` SHALL print config threshold warnings at run start for each source on every invocation (not only during `--dry-run`).

#### Scenario: Large crawl warning
- **WHEN** `max_pages > 500` for a source
- **THEN** the command SHALL print `⚠  max_pages=N — large crawl` before crawling begins

#### Scenario: Deep crawl warning
- **WHEN** `depth > 4` for a source
- **THEN** the command SHALL print `⚠  depth=N — deep crawl, may be slow` before crawling begins

#### Scenario: No url_prefix warning
- **WHEN** `url_prefix == ""` for a source
- **THEN** the command SHALL print `⚠  no url_prefix — entire domain will be crawled` before crawling begins

#### Scenario: Aggressive rate warning
- **WHEN** `delay_min < 0.5` for a source
- **THEN** the command SHALL print `⚠  delay_min=N — aggressive rate; may trigger blocks` before crawling begins

#### Scenario: seed_urls ignored warning
- **WHEN** `seed_urls` is non-empty AND `crawl_strategy` is `bfs`, `dfs`, or `best_first`
- **THEN** the command SHALL print `⚠  seed_urls is set but crawl_strategy=<strategy> — seed_urls will be ignored` before crawling begins

---

### Requirement: crawl_strategy field
Sources and projects SHALL support a `crawl_strategy` field: `bfs` (default), `dfs`, `best_first`, or `seed_urls`.

#### Scenario: seed_urls strategy skips deep crawl
- **WHEN** `crawl_strategy: seed_urls` is set on a source
- **THEN** `run_scrape()` SHALL fetch the explicit `seed_urls` list instead of running a deep crawl, and SHALL NOT run BFS/DFS
- **AND** `seed_urls` MUST be non-empty or `resolve_source()` SHALL raise `ValueError`

#### Scenario: Real scrape with seed_urls shows correct total
- **WHEN** `crawl_strategy: seed_urls` and a real scrape is running
- **THEN** the progress bar denominator SHALL be `len(seed_urls)`, not `max_pages`
- **AND** for BFS/DFS/best_first strategies the denominator SHALL remain `max_pages`
