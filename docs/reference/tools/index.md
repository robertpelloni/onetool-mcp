# Tool Reference

**23 Packs. 206 Tools.**

Complete reference of all built-in tool packs and functions.

## Optional Extras

Tools are split into optional install extras. Install only what you need:

| Extra | Tools included |
|-------|---------------|
| *(core, always included)* | `ot`, `ot_forge`, `ot_llm`, `ot_secrets`, `ot_timer` |
| `[util]` | `brave`, `convert`, `excel`, `file`, `ground`, `mem`, `tavily` |
| `[dev]` | `aws`, `chrome_util`, `context7`, `db`, `diagram`, `package`, `play_util`, `ripgrep`, `whiteboard`, `webfetch`, `worktree` |
| `[all]` | All of the above |

```bash
uv tool install 'onetool-mcp[all]'       # everything
uv tool install 'onetool-mcp[util,dev]'  # most tools
```

## Tool Packs

| Pack | Extra | Description | Tool Count | Credits | Tools |
|------|-------|-------------|---|---------|-------|
| [**AWS**](aws.md) | `[dev]` | AWS services via awslabs/mcp servers, activated on demand by role. | 17 | [awslabs/mcp](https://github.com/awslabs/mcp) (Apache 2.0) | `arn`, `attributes`, `check`, `login`, `mfa`, `packs`, `profile`, `profiles`, `refresh_packs`, `regions`, `roles`, `services`, `start_packs`, `stop_packs`, `use`, `values`, `whoami` |
| [**Brave**](brave.md) | `[util]` | Web search via Brave Search API. | 5 | [brave-search-mcp-server](https://github.com/brave/brave-search-mcp-server) (MIT) | `image`, `news`, `search`, `search_batch`, `video` |
| [**Chrome DevTools Util**](chrome-util.md) | `[dev]` | Visual element annotation for the Chrome DevTools MCP server. | 5 | MIT | `clear_annotations`, `guide_user`, `highlight_element`, `inject_annotations`, `scan_annotations` |
| [**Context7**](context7.md) | `[dev]` | Library documentation lookup. | 2 | [context7](https://github.com/upstash/context7) (MIT) | `doc`, `search` |
| [**Convert**](convert.md) | `[util]` | Convert PDF, Word, PowerPoint, Excel to Markdown. | 5 | MIT | `auto`, `excel`, `pdf`, `powerpoint`, `word` |
| [**DB**](db.md) | `[dev]` | SQL database queries. | 3 | [mcp-alchemy](https://github.com/runekaagaard/mcp-alchemy) (MPL 2.0) | `query`, `schema`, `tables` |
| [**Diagram**](diagram.md) | `[dev]` | Generate Mermaid, PlantUML, D2 diagrams. | 11 | [Kroki](https://kroki.io/) (MIT) | `batch_render`, `generate_source`, `get_diagram_instructions`, `get_diagram_policy`, `get_output_config`, `get_playground_url`, `get_render_status`, `get_template`, `list_providers`, `render_diagram`, `render_directory` |
| [**Excel**](excel.md) | `[util]` | Full Excel control. | 24 | [openpyxl](https://github.com/theorchard/openpyxl) (MIT) | `add_sheet`, `cell_range`, `cell_shift`, `copy_range`, `create`, `create_table`, `delete_cols`, `delete_rows`, `formula`, `formulas`, `hyperlinks`, `info`, `insert_cols`, `insert_rows`, `merged_cells`, `named_ranges`, `read`, `search`, `sheets`, `table_data`, `table_info`, `tables`, `used_range`, `write` |
| [**File**](file.md) | `[util]` | Secure file operations with path boundary enforcement. | 15 | MIT | `copy`, `delete`, `edit`, `grep`, `info`, `list`, `move`, `read`, `read_batch`, `search`, `slice`, `slice_batch`, `toc`, `tree`, `write` |
| [**Forge**](forge.md) | core | Create, validate, and install extension tools and skill stubs. | 3 | MIT | `create_ext`, `install_skills`, `validate_ext` |
| [**Ground**](ground.md) | `[util]` | Grounded search with sources. | 5 | [Google Gemini](https://ai.google.dev/) (MIT) | `dev`, `docs`, `reddit`, `search`, `search_batch` |
| [**LLM**](llm.md) | core | AI-powered data transformation. | 2 | MIT | `transform`, `transform_file` |
| [**Mem**](mem.md) | `[util]` | Persistent AI agent memory with semantic search. | 27 | MIT | `append`, `cache_clear`, `context`, `count`, `decay`, `delete`, `embed`, `export`, `flush`, `grep`, `list`, `load`, `read`, `read_batch`, `refresh`, `restore`, `search`, `slice`, `slice_batch`, `snap`, `stale`, `stats`, `toc`, `update`, `update_batch`, `write`, `write_batch` |
| [**OT Core**](ot.md) | core | Introspection and management tools. | 20 | MIT | `aliases`, `config`, `debug`, `health`, `help`, `notify`, `pack_info`, `packs`, `reload`, `result`, `security`, `server`, `servers`, `skills`, `snippet_info`, `snippets`, `stats`, `tool_info`, `tools`, `version` |
| [**OT Secrets**](secrets.md) | core | Age-encrypted secrets management. | 5 | MIT | `audit`, `encrypt`, `init`, `rotate`, `status` |
| [**Package**](package.md) | `[dev]` | Package version lookup and security audits. | 5 | MIT | `audit`, `models`, `npm`, `pypi`, `version` |
| [**Playwright Util**](play-util.md) | `[dev]` | Visual element annotation for the Playwright MCP server. | 5 | MIT | `clear_annotations`, `guide_user`, `highlight_element`, `inject_annotations`, `scan_annotations` |
| [**Ripgrep**](ripgrep.md) | `[dev]` | Fast regex file search. | 4 | [ripgrep](https://github.com/BurntSushi/ripgrep) (MIT) | `count`, `files`, `search`, `types` |
| [**Tavily**](tavily.md) | `[util]` | AI-powered web search and URL content extraction. | 5 | [Tavily](https://tavily.com/) (MIT) | `extract`, `extract_batch`, `research`, `search`, `search_batch` |
| [**Timer**](timer.md) | core | Named stopwatch timers for performance measurement. | 4 | MIT | `clear`, `elapsed`, `list`, `start` |
| [**WB (Whiteboard)**](whiteboard.md) | `[dev]` | Live diagram drawing on excalidraw.com via Playwright. | 18 | MIT | `clear`, `close`, `draw`, `embed_dsl`, `erase`, `fit`, `hard_reset`, `help`, `load`, `note`, `open`, `save`, `screenshot`, `scroll`, `share`, `style`, `sync`, `zoom` |
| [**Webfetch**](webfetch.md) | `[dev]` | Fetch and extract web content. | 2 | [trafilatura](https://github.com/adbar/trafilatura) (Apache 2.0) | `fetch`, `fetch_batch` |
| [**Worktree**](worktree.md) | `[dev]` | Git worktree management for parallel agent tasks. | 14 | MIT | `add`, `checkout`, `clean`, `commit`, `diff`, `info`, `init`, `list`, `log`, `mark`, `message`, `prepare`, `remove`, `status` |
