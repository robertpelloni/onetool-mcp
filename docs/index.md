---
hide:
  - navigation
  - toc
---

<h1 class="sr-only">OneTool</h1>

<div class="hero">
<div class="hero__logo" role="img" aria-label="OneTool logo"></div>
<p class="hero__title">OneTool</p>
<p class="hero__tagline">🧿 One MCP, unlimited tools</p>
<div class="hero__buttons">
<a href="learn/" class="btn btn--primary">Learn OneTool</a>
<a href="reference/" class="btn btn--secondary">Reference</a>
</div>
</div>


## **The Problem**

### Tool Tax
Each MCP Server consumes between 3K and 30K (looking at you, GitHub MCP!) in tokens **per request**. Every single request.
The maths is brutal: If you're using Claude Opus 4.5 at $5 per million input tokens - 20 days × 10 conversations × 10 messages × 3K tokens = 6M input tokens. You waste approx. **$30 in Tool Tax per MCP Server, per month**.

### Context Rot
And then there's **context rot** -  the phenomenon where the agent's performance degrades as the context window fills ([Chroma Research, 2025](https://research.trychroma.com/context-rot)). Every tool description pushes valuable conversation history out of the context window. Your AI literally **gets dumber as you add more tools**.

## **The Solution**

OneTool is **one MCP server** that exposes tools as a Python API. Instead of reading tool definitions, your agent writes code  - `brave.search(q="react docs")`  - and OneTool runs it.

Configure one MCP Server. Use unlimited tools. 

**96% fewer tokens. 24× lower cost. No context rot. 100+ tools, extensible and configurable**

[:octicons-arrow-right-24: Read the full story](about/about-onetool.md)

## Features

<div class="bento" markdown>

<div class="card span-2 tall" markdown>

### :material-chart-line: 96% Token Savings

MCP servers consume 3-30K tokens before you start. OneTool uses ~2K tokens no matter how many tools and MCP servers you add. No tool tax. No context rot. **24× lower cost.**

!!! quote ""
    "Agents scale better by writing code to call tools instead. This reduces the token usage from 150,000 tokens to 2,000 tokens...a cost saving of 98.7%"
     - [Anthropic Engineering](https://www.anthropic.com/engineering/code-execution-with-mcp)

[:octicons-arrow-right-24: See comparison](learn/comparison.md)

</div>

<div class="card" markdown>

### :material-code-braces: Code, Not Tool Calls

Agents are excellent at writing code. OneTool tool calls can be batched, chained, and used just like any other Python function.

[:octicons-arrow-right-24: Learn more](learn/explicit-calls.md)

</div>

<div class="card" markdown>

### :material-eye: Explicit Execution

Write Python, not tool definitions. You see exactly what runs. No more guessing.

```python
__ot brave.search(q="AI")
```

</div>

<div class="card" markdown>

### :material-puzzle: Scaffold Tools

Build new tools as part of the conversation. New tools are just Python functions. Drop a file, get a pack.

[:octicons-arrow-right-24: Create tools](learn/extending/extension-tools.md)

</div>

<div class="card" markdown>

### :material-server-network: MCP Server Proxy

Wrap any existing MCP server. Configure in YAML. Call explicitly - without the Tool Tax. Pre-configured: Chrome DevTools, GitHub.

[:octicons-arrow-right-24: Use other MCP servers](reference/cli/onetool-config.md#external-mcp-servers)

</div>

<div class="card" markdown>

### :material-cog: Great Developer Experience

Snippets with Jinja2. Aliases for common tools. Parameter prefixes (`q` for `query`). Single YAML config.

</div>

<div class="card span-2" markdown>

### :material-file-cog: Configuration

Single, well-structured [YAML config](learn/configuration.md) with global and project scopes. Per-pack settings for timeouts, limits, models.

</div>

<div class="card" markdown>

### :material-chart-box: Observability

Meta tools for introspection. [Structured logging](learn/extending/extension-tools.md#logging-with-logspan) with LogSpan. [Runtime statistics](reference/tools/ot.md#otstats) for costs and success rates.

</div>

<div class="card span-2" markdown>

### :material-package-variant: 100+ Tools

Web search (Brave, Grounding), web fetch with trafilatura, databases, file operations, diagrams, conversions - ready to use.

[:octicons-arrow-right-24: Browse tools](reference/tools/index.md)

</div>

<div class="card span-2" markdown>

### :material-robot: Smart Tools

Delegate to cheaper agents. Fetch a page, summarise with Gemini Flash ($0.50/M), pass back to Opus ($5/M). **10× savings.**

[:octicons-arrow-right-24: Smart Tools](reference/tools/llm.md)

</div>

<div class="card span-2" markdown>

### :material-shield-check: Security

Multiple layers built in: isolated [`secrets.yaml`](reference/cli/onetool-config.md#secrets-configuration), [AST validation](learn/security.md#2-allowlist-based-code-validation), [path boundaries](learn/security.md#6-path-boundary-enforcement), [output sanitisation](learn/security.md#9-output-sanitization-prompt-injection-protection).

</div>

<div class="card span-2" markdown>

### :material-test-tube: Testing & Benchmarking

The **bench** harness compares tools against other MCP servers using a real agent. Define tasks in YAML. Get objective metrics: token counts, costs, accuracy scores, timing.

[:octicons-arrow-right-24: The Bench Tool](reference/cli/bench.md)

</div>

<div class="card span-4" markdown>

### :material-check-circle: Engineering Practices

1,200+ tests (smoke, unit, integration). OpenSpec for change proposals - specs before code. Type hints throughout. Ruff + Mypy.

</div>

</div>
