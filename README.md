<p align="center">
  <!-- mcp-name: io.github.beycom/onetool-mcp -->
  <a href="https://github.com/beycom/onetool-mcp">
    <img src="https://raw.githubusercontent.com/beycom/onetool-mcp/main/docs/assets/logo.svg" alt="OneTool" width="80">
  </a>
</p>

<p align="center">
  <strong>🧿 One MCP for developers - No tool tax, no context rot.<br>100+ tools including Brave, Google, Context7, Excalidraw, AWS, Version Checker, Excel, File Ops, Database, Playwright, Chrome DevTools and many more.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/onetool-mcp/"><img alt="PyPI" src="https://img.shields.io/pypi/v/onetool-mcp"></a>
  <a href="https://github.com/beycom/onetool-mcp/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/license-GPLv3-blue"></a>
  <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue"></a>
  <a href="https://github.com/beycom/onetool-mcp/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/beycom/onetool-mcp"></a>
</p>

<p align="center">
  Works with Claude Code or any MCP client
</p>

---

## The Problem

Each MCP server consumes **3K-30K tokens per request**. Connect 5 servers and you've burned 55K tokens before the conversation starts. Connect 10+ and you're at 100K tokens.

The math is brutal: Claude Opus 4.5 at $5/M input tokens, 20 days × 10 conversations × 10 messages × 3K tokens = **$30/month per MCP server** - even if you never use the tools.

And then there's **context rot** - your AI literally gets dumber as you add more tools ([Chroma Research, 2025](https://research.trychroma.com/context-rot)).

## The Solution

OneTool is **one MCP server** that exposes tools as a Python API. Instead of reading tool definitions, your agent writes code:

```python
>>> brave.search(query="react docs 2026")
```

Configure one MCP server. Use unlimited tools.

> "Agents scale better by writing code to call tools instead. This reduces the token usage from 150,000 tokens to 2,000 tokens...a cost saving of 98.7%"
>
> — [Anthropic Engineering](https://www.anthropic.com/engineering/code-execution-with-mcp)

**96% fewer tokens. 30× lower cost. No context rot.**

[📖 Read the full story](https://onetool.beycom.online/about/about-onetool/)

---

## See It In Action

| Demo                                                   | Description                     |
| ------------------------------------------------------ | ------------------------------- |
| [Compare the Search](https://youtu.be/Dv-_dtHVU_A)     | Side-by-side token comparison   |
| [Build a Wikipedia Tool](https://youtu.be/AZz03Yw0s1E) | Create a custom tool in seconds |

---

## Install

Requires [uv](https://docs.astral.sh/uv/):

```bash
uv tool install onetool-mcp
onetool init -c ~/.onetool
```

Add to Claude Code:

```bash
claude mcp add onetool -- onetool --config ~/.onetool/onetool.yaml
```

Or manually add to `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "onetool": {
      "command": "onetool",
      "args": ["--config", "/Users/yourname/.onetool/onetool.yaml"]
    }
  }
}
```

That's it. All 100+ tools work out of the box.

Verify: `onetool init validate -c ~/.onetool/onetool.yaml`

[📖 Full installation guide](https://onetool.beycom.online/learn/installation/)

---

## Features

| Feature                 | Description                                            |
| ----------------------- | ------------------------------------------------------ |
| **96% Token Savings**   | ~2K tokens no matter how many tools you add            |
| **100+ Built-in Tools** | Web search, databases, file ops, diagrams, conversions |
| **Explicit Execution**  | See exactly what runs - `>>> brave.search(q="AI")`    |
| **MCP Server Proxy**    | Wrap existing MCP servers without the tool tax         |
| **Forge Tools**         | Build new tools as part of the conversation            |
| **Smart Tools**         | Delegate to cheaper LLMs (10× savings)                 |
| **Single YAML Config**  | Global configuration, per-pack settings, includes      |
| **Security Layers**     | AST validation, path boundaries, output sanitisation   |

---

## Tools

15+ packs, 100+ tools ready to use:

| Pack       | Tools                                   | Description            |
| ---------- | --------------------------------------- | ---------------------- |
| `brave`    | `search`, `news`                        | Web and news search    |
| `context7` | `search`, `doc`                         | Library documentation  |
| `convert`  | `pdf_to_md`, `docx_to_md`, `pptx_to_md` | Document conversion    |
| `db`       | `query`, `schema`, `tables`             | Database operations    |
| `diagram`  | `create`                                | Mermaid diagrams       |
| `excel`    | `read`, `write`, `query`                | Excel files            |
| `file`     | `read`, `write`, `list`, `search`       | File operations        |
| `ground`   | `search`                                | Google Grounding       |
| `llm`      | `transform`, `transform_file`           | LLM-powered transforms |
| `ot`       | `help`, `tools`, `stats`                | Introspection          |
| `package`  | `npm`, `pypi`, `cargo`                  | Package versions       |
| `ripgrep`  | `search`, `count`                       | Fast code search       |
| `forge`    | `create_ext`, `install_skills`, `validate_ext` | Generate new tools |
| `webfetch` | `fetch`, `fetch_batch`                  | Web fetching           |

[📖 Complete tools reference](https://onetool.beycom.online/reference/tools/) — full summary table with all 100+ tools

---

## MCP Server Proxy

Wrap any existing MCP server and call it explicitly - without the tool tax:

```yaml
# .onetool/onetool.yaml
servers:
  chrome-devtools:
    type: stdio
    command: npx
    args: ["-y", "@anthropic-ai/chrome-devtools-mcp@latest"]
  github:
    type: stdio
    command: npx
    args: ["-y", "@anthropic-ai/github-mcp-server@latest"]
```

```python
>>> mcp.call(server="github", tool="get_file_contents", arguments={"path": "README.md"})
```

[📖 Configuration guide](https://onetool.beycom.online/learn/configuration/#external-mcp-servers)

---

## Extending

Drop a Python file, get a pack. No registration, no config:

```python
# .onetool/tools/wiki.py
pack = "wiki"

def summary(*, title: str) -> str:
    """Get Wikipedia article summary."""
    import httpx
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
    return httpx.get(url).json().get("extract", "Not found")
```

```python
>>> wiki.summary(title="Python_(programming_language)")
```

[📖 Creating tools guide](https://onetool.beycom.online/learn/extending/extension-tools/)

---

## Documentation

- [Quickstart](https://onetool.beycom.online/learn/quickstart/) - 30 seconds to first tool call
- [Installation](https://onetool.beycom.online/learn/installation/) - All platforms
- [Configuration](https://onetool.beycom.online/learn/configuration/) - YAML schema
- [Tools Reference](https://onetool.beycom.online/reference/tools/) - All 100+ tools
- [Security](https://onetool.beycom.online/learn/security/) - Security layers
- [Extending](https://onetool.beycom.online/learn/extending/) - Build your own
- [Dev Docs](dev/index.md) - Internal developer documentation
- [Specifications](openspec/specs/INDEX.md) - OpenSpec specifications index

---

## References

- [Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) - Anthropic Engineering
- [Context Rot](https://research.trychroma.com/context-rot) - Chroma Research

---

## License

**GPLv3** - Will transition to **MIT** at v2.0.

---

## Support

If you find OneTool useful:

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Buy%20me%20a%20coffee-ff5e5b?logo=ko-fi)](https://ko-fi.com/beycom)
