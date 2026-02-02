---
hide:
  - navigation
  - toc
---

<h1 class="sr-only">OneTool</h1>

<div class="hero">
<div class="hero__logo" role="img" aria-label="OneTool logo"></div>
<p class="hero__title">OneTool</p>
<p class="hero__tagline">One MCP, unlimited tools</p>
<div class="hero__buttons">
<a href="learn/" class="btn btn--primary">Learn OneTool</a>
<a href="reference/" class="btn btn--secondary">Reference</a>
</div>
</div>

---

## Features

<div class="bento" markdown>

<div class="card span-2 tall" markdown>

### :material-chart-line: 96% Token Savings

MCP servers consume 3-30K tokens before you start. OneTool uses ~2K tokens no matter how many packs or proxy servers you add.

No context rot. No token bloat. **24x lower cost.**

[:octicons-arrow-right-24: See comparison](learn/comparison.md)

</div>

<div class="card" markdown>

### :material-code-braces: Explicit Execution

Write Python, not tool definitions. You see exactly what runs.

```python
__ot brave.search(q="AI")
```

[:octicons-arrow-right-24: Learn more](learn/explicit-calls.md)

</div>

<div class="card" markdown>

### :material-package-variant: 100+ Tools

Search, web, database, files, diagrams, conversions—batteries included.

[:octicons-arrow-right-24: Browse tools](reference/tools/index.md)

</div>

<div class="card span-2" markdown>

### :material-server-network: MCP Server Proxy

Wrap any existing MCP server. Configure in YAML. Call explicitly. Pre-configured: Chrome DevTools, GitHub.

[:octicons-arrow-right-24: Learn more](learn/configuration.md#external-mcp-servers)

</div>

<div class="card" markdown>

### :material-shield-check: Security

AST validation blocks dangerous code. Configurable policies (Allow/Ask/Warn/Block). Path boundaries. Output sanitization.

[:octicons-arrow-right-24: Learn more](learn/security.md)

</div>

<div class="card" markdown>

### :material-cog: Developer Experience

Snippets with Jinja2. Aliases for common tools. Parameter prefixes. Single YAML config with three-tier inheritance.

[:octicons-arrow-right-24: Configuration](learn/configuration.md)

</div>

<div class="card" markdown>

### :material-puzzle: Extensibility

Drop a Python file, get a pack. Worker isolation via PEP 723. Scaffold CLI for templates.

[:octicons-arrow-right-24: Create tools](extending/creating-tools.md)

</div>

<div class="card" markdown>

### :material-chart-box: Observability

Structured logging with LogSpan. Runtime statistics. Automatic credential sanitization.

[:octicons-arrow-right-24: Learn more](extending/logging.md)

</div>

<div class="card span-2" markdown>

### :material-test-tube: Testing & Benchmarking

**bench** harness for real agent + MCP testing. Multi-prompt tasks. AI evaluators. Token counts, costs, accuracy scores.

[:octicons-arrow-right-24: Learn more](reference/cli/bench.md)

</div>

<div class="card" markdown>

### :material-check-circle: Quality

1,200+ tests. Type hints throughout. Ruff + Mypy. Built with OpenSpec.

[:octicons-arrow-right-24: Testing guide](extending/testing.md)

</div>

</div>
