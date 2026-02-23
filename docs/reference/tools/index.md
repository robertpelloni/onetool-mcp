# Tool Reference

**17 Packs. 129 Tools.**

Complete reference of all built-in tool packs and functions.

## Optional Extras

Tools are split into optional install extras. Install only what you need:

| Extra | Tools included |
|-------|---------------|
| *(core, always included)* | `file`, `mem`, `ot`, `forge`, `timer`, `llm`, age encryption for secrets at rest |
| `[util]` | `brave`, `convert`, `excel`, `ground` |
| `[dev]` | `context7`, `db`, `diagram`, `package`, `ripgrep`, `web`, `worktree` |
| `[all]` | All of the above |

```bash
uv tool install 'onetool-mcp[all]'       # everything
uv tool install 'onetool-mcp[util,dev]'  # most tools
```

## Tool Packs

| Pack | Extra | Description | Tool Count | Credits | Tools |
|------|-------|-------------|---|---------|-------|
| [**brave**](brave.md) | `[util]` | Web search via Brave Search API. | 5 | [brave-search-mcp-server](https://github.com/brave/brave-search-mcp-server) (MIT) | `image`, `news`, `search`, `search_batch`, `video` |
| [**context7**](context7.md) | `[dev]` | Library documentation lookup. | 2 | [context7](https://github.com/upstash/context7) (MIT) | `doc`, `search` |
| [**convert**](convert.md) | `[util]` | Convert PDF, Word, PowerPoint, Excel to Markdown. | 5 | MIT | `auto`, `excel`, `pdf`, `powerpoint`, `word` |
| [**db**](db.md) | `[dev]` | SQL database queries. | 3 | [mcp-alchemy](https://github.com/runekaagaard/mcp-alchemy) (MPL 2.0) | `query`, `schema`, `tables` |
| [**diagram**](diagram.md) | `[dev]` | Generate Mermaid, PlantUML, D2 diagrams. | 11 | [Kroki](https://kroki.io/) (MIT) | `batch_render`, `generate_source`, `get_diagram_instructions`, `get_diagram_policy`, `get_output_config`, `get_playground_url`, `get_render_status`, `get_template`, `list_providers`, `render_diagram`, `render_directory` |
| [**excel**](excel.md) | `[util]` | Full Excel control. | 24 | [openpyxl](https://github.com/theorchard/openpyxl) (MIT) | `add_sheet`, `cell_range`, `cell_shift`, `copy_range`, `create`, `create_table`, `delete_cols`, `delete_rows`, `formula`, `formulas`, `hyperlinks`, `info`, `insert_cols`, `insert_rows`, `merged_cells`, `named_ranges`, `read`, `search`, `sheets`, `table_data`, `table_info`, `tables`, `used_range`, `write` |
| [**file**](file.md) | core | Secure file operations with path boundary enforcement. | 10 | MIT | `copy`, `delete`, `edit`, `grep`, `info`, `list`, `move`, `read`, `search`, `slice`, `toc`, `tree`, `write` |
| [**forge**](forge.md) | core | Create, validate, and install extension tools and skill stubs. | 3 | MIT | `create_ext`, `install_skill`, `validate_ext` |
| [**ground**](ground.md) | `[util]` | Grounded search with sources. | 5 | [Google Gemini](https://ai.google.dev/) (MIT) | `dev`, `docs`, `reddit`, `search`, `search_batch` |
| [**llm**](llm.md) | core | AI-powered data transformation. | 2 | MIT | `transform`, `transform_file` |
| [**mem**](mem.md) | core | Persistent AI agent memory with semantic search. | 22 | MIT | `append`, `context`, `count`, `decay`, `delete`, `embed`, `export`, `flush`, `list`, `load`, `read`, `read_batch`, `restore`, `search`, `slice`, `snap`, `stats`, `toc`, `update`, `update_batch`, `write`, `write_batch` |
| [**ot**](ot.md) | core | Introspection and management tools. | 15 | MIT | `aliases`, `config`, `health`, `help`, `notify`, `packs`, `reload`, `result`, `security`, `server`, `servers`, `skills`, `snippets`, `stats`, `tools` |
| [**package**](package.md) | `[dev]` | Package version lookup and security audits. | 5 | MIT | `audit`, `models`, `npm`, `pypi`, `version` |
| [**ripgrep**](ripgrep.md) | `[dev]` | Fast regex file search. | 4 | [ripgrep](https://github.com/BurntSushi/ripgrep) (MIT) | `count`, `files`, `search`, `types` |
| [**timer**](timer.md) | core | Named stopwatch timers for performance measurement. | 4 | MIT | `clear`, `elapsed`, `list`, `start` |
| [**web**](web.md) | `[dev]` | Fetch and extract web content. | 2 | [trafilatura](https://github.com/adbar/trafilatura) (Apache 2.0) | `fetch`, `fetch_batch` |
| [**worktree**](worktree.md) | `[dev]` | Git worktree management for parallel agent tasks. | 14 | MIT | `add`, `checkout`, `clean`, `commit`, `diff`, `info`, `init`, `list`, `log`, `mark`, `message`, `prepare`, `remove`, `status` |
| | | **Total** | **136** | | |
