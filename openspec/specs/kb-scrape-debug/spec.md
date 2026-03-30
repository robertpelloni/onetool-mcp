# KB Scrape Debug Flag Specification

## Purpose

Defines the `--debug` flag for `onetool kb scrape`, which performs a real crawl and writes per-page debug artifacts alongside the normal output. Also defines config threshold warnings emitted unconditionally on every scrape run.

---

## Requirements

### Requirement: --debug flag for kb scrape
`onetool kb scrape <project> --debug` SHALL perform a real crawl and write per-page debug artifacts alongside the normal output.

#### Scenario: Debug artifacts written for each page
- **WHEN** `onetool kb scrape <project> --debug` is run
- **THEN** for each crawled page (ok, empty, or failed), the command SHALL write a `._debug/<slug>/` directory inside the source `output_dir` containing:
  - `cleaned.html` — post-JS rendered HTML (`page.cleaned_html`)
  - `raw.html` — pre-JS raw HTML (`page.html`)
  - `screenshot.png` — screenshot decoded from base64 (only written if screenshot data is non-empty)
  - `meta.json` — JSON object with fields: `url`, `status_code`, `redirected_url`, `links` (object with `internal_count`, `external_count`, `internal` list, `external` list), `console_messages`, `js_execution_result`, `error_message`

#### Scenario: Empty pages get debug artifacts
- **WHEN** `--debug` is active and a crawled page returns no extractable content
- **THEN** debug artifacts SHALL still be written for that page so the operator can inspect `cleaned.html` and `raw.html` to diagnose the cause

#### Scenario: Failed pages get debug artifacts
- **WHEN** `--debug` is active and a page fails to load (`page.success == False`)
- **THEN** debug artifacts SHALL still be written; `cleaned.html` and `raw.html` MAY be empty; `meta.json` SHALL include the `error_message`

#### Scenario: screenshot captured only when --debug is active
- **WHEN** `--debug` is NOT passed
- **THEN** `screenshot=True` SHALL NOT be added to the crawler config and no `._debug/` directory SHALL be written

#### Scenario: --debug and --max-pages combine for test runs
- **WHEN** `onetool kb scrape <project> --max-pages 3 --debug` is run
- **THEN** the scrape SHALL stop after 3 pages per source and debug artifacts SHALL be written for each of those pages

---

### Requirement: Config threshold warnings on every scrape run
`onetool kb scrape` SHALL print config threshold warnings at run start for each source, unconditionally (not gated behind any flag).

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
