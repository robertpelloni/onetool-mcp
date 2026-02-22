# Compare the Search

Compare OneTool search tools to Claude Code's built-in WebSearch.

Start with `ot.help()` to learn available tools and calling conventions.

Question: MCP resources vs tools — what's the difference?

Search tools to compare:
- OneTool: brave.search, ground.docs, ground.search, context7.search, context7.doc
- Claude: WebSearch

For MCP-specific questions, also try:
- `context7.doc(library_key="/websites/modelcontextprotocol_io_specification_2025-11-25", topic="resources vs tools")`
- `web.fetch_batch(urls=["https://modelcontextprotocol.info/docs/concepts/resources/", "https://modelcontextprotocol.info/docs/concepts/tools/"])`

Optimise each call for best results (count, format, links).
DO NOT answer the question — just run the searches and compare output.

Report as a markdown table:

| Tool | Speed (1-10) | Quality (1-10) | Best For | Call Used |
