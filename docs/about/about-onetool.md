# About OneTool

## MCP is Dead. Long Live MCP.

### The Kingdom

AI is the King. Every developer is using AI to build software now -  from vibe coding to agentic engineering -  and we're producing more software than ever before.

And MCP servers are the current **kings of AI coding**. MCP servers are remarkable: they extend your agent's capabilities into virtually any domain. With nearly 8,000 servers available on [PulseMCP](https://www.pulsemcp.com/) and every major vendor releasing their own server, most developers already have three or four registered. Some have dozens.

But here's the problem: **all kings collect taxes.**

### The King's Tax

Using an MCP Server comes with two significant problems.

#### Tool Tax

Like the kings of old, MCP servers rob the poor (you and me) and give the money to the rich (the AI giants like OpenAI, Microsoft and Anthropic). Each MCP Server consumes between 3K and 30K (looking at you, GitHub MCP!) tokens *per request*. Every single request.

This happens because the agent reads all the MCP Server instructions for every configured tool on every request. These "tool tokens" can easily cost a full-time engineer **$30 per month** -  even if they **never use the tools**.

The maths is brutal: If you're using Claude Opus 4.5 at $5 per million input tokens - 20 days × 10 conversations × 10 messages × 3K tokens = 6M input tokens = **$30** in tool tax. Monthly. For nothing.

Just read innocuously [Code execution with MCP: Building more efficient agents](https://www.anthropic.com/engineering/code-execution-with-mcp), where Anthropic openly stated: "This reduces the token usage from 150K tokens to 2K tokens -  a time and cost saving of 98.7%."

#### Context Rot

And then there's **context rot** -  the phenomenon where the agent's performance degrades as the context window fills ([Chroma Research, 2025](https://research.trychroma.com/context-rot)). Every tool description pushes valuable conversation history out of the context window. Your AI literally gets dumber as you add more tools.

## The Genesis

[Theo - t3.gg](https://www.youtube.com/@t3dotgg) had been shouting about MCP's flaws for months. I binge-watched his takedowns -  [MCP is the wrong abstraction](https://www.youtube.com/watch?v=bAYZjVAodoo&pp=0gcJCZEKAYcqIYzv), [Anthropic admits that MCP sucks](https://www.youtube.com/watch?v=1piFEKA9XL0), [Anthropic is trying SO hard to fix MCP](https://www.youtube.com/watch?v=hPPTrsUzLA8), [Anthropic gave MCP to the Linux Foundation](https://www.youtube.com/watch?v=5DeqL844pH0) -  and realised he was right. The question wasn't whether MCP was broken. It was how to fix it.

The problem was clear, yet nobody was building a simple, viable solution.

I was excited when Anthropic (the creators of the MCP standard) published [Code execution with MCP: Building more efficient agents](https://www.anthropic.com/engineering/advanced-tool-use), which clearly identified the issue. However, their solution was horrible -  the ["Tool Search Tool"](https://www.anthropic.com/engineering/advanced-tool-use). They essentially doubled down on the MCP Server tool tax, compounded by patchy client support across AI vendors and their multitude of products.

The next solution I looked at was the [Docker MCP Gateway](https://docs.docker.com/ai/mcp-catalog-and-toolkit/mcp-gateway/). However, it was so convoluted and limited that I was (almost) happy to pay the tool tax.

As a result, I limited myself to the absolute bare minimum: three MCP servers -  web search, package version checks, and Context7. One of the biggest issues with agentic engineering is that technology changes so quickly that the "base data" is often outdated. For example, code I wrote frequently failed because my AI coding buddy (GPT-5.2) replaced the GPT-5.2 model with GPT-4o (released in May 2024) because it was convinced GPT-5.2 did *not* exist.

So I was stuck: I needed MCP servers to work efficiently, but I didn't want to pay the tool tax or suffer from context rot.

## Eureka

It all came together on a train trip to work. All of a sudden, the pieces clicked into place.

Maybe I could solve it. Maybe I could help [Theo](https://www.youtube.com/@t3dotgg), along with [Max](https://www.youtube.com/@maximilian-schwarzmueller) (one of my favourite Udemy authors, who published [Don't bother with MCP](https://www.youtube.com/watch?v=olvnjDadACI)), along with Kelly ([Context Rot](https://www.youtube.com/watch?v=TUjQuC4ugak)), Dan ([MCP's Biggest Problem](https://www.youtube.com/watch?v=itS3f1Y52t0)), Cole ([The BIG Problem with MCP servers)](https://www.youtube.com/watch?v=1_z3h2r93OY)) -  and many, many others -  avoid the terrible tool tax while still enjoying amazing MCP servers like 

- [playwright](https://github.com/microsoft/playwright-mcp)
- [chrome-devtools](https://github.com/chromedevtools/chrome-devtools-mcp)
- [context7](https://github.com/upstash/context7)
- [github/github-mcp-server](https://github.com/github/github-mcp-server)

I am a developer. I work with code. My AI coding buddy (Claude Opus 4.5 at the time) was amazing at coding. It could write complex Python programs.

**What if Claude used code to call tools? What if tools were just code?**

And so OneTool was born -  **One MCP, many tools**.

To quote Gandalf the Wise:
["One tool to rule them all, one tool to find them, one tool to bring them all, and in the development bind them."](https://www.youtube.com/watch?v=lMSLM33PQDM&t=65s)

After six weeks of part-time hacking, vibing, coding and agentic engineering (which may be a topic for another time), I released [OneTool 1.0.0 (beta)](https://github.com/beycom/onetool-mcp).

## OneTool

### The core idea: stop making agents "call tools". Let them write code.

MCP servers expose tools to agents as detailed instructions on how to use the tool. The agent reads all these instructions and then selects the right tool. It's like reading the documentation for every Python library in your project, then writing: `print("Hello World")`.

So I tried something different. I converted the tools into a developer-friendly API, then asked an agent to **write code snippets** that call the APIs.

The results were striking.

Using this approach, agents could handle **unlimited tools** without paying the Tool Tax or suffering from context rot. But the goodness didn't stop there. Tool calls were now explicit. No more asking the agent, "please search the web for the latest React docs" -  you could just use `brave.search(query="latest react docs 2025")`. Tool calls could be batched, chained, included inside loops, and used just like any other code.

### OneTool: the only MCP Server you will ever need

OneTool is the one and only MCP you need to configure. No matter how many tools you use, you only need one MCP server.

This results in [**96% fewer tokens, 24× lower cost, and improved accuracy**](../learn/comparison.md).

And yes -  like any engineer -  I couldn't help engineering a few party tricks along the way.

### OneTool party tricks

#### No more guessing

Write Python like: `__ot brave.search(query="latest react docs 2025")`

You can see exactly what runs. No tool-selection guessing. No non-deterministic behaviour. No more guessing what the agent actually searched for.

#### Great Developer Experience (DX)

If you're now coding in your agent prompt, you need powerful snippets for reusable code templates with Jinja2 substitution, aliases for common tools, and an easy way to configure them (in a single, well-structured YAML file).

You'll also get tired of typing `query="..."`, so I added smart parameter prefixes: use `q` instead of `query`, `p` instead of `pattern`. Any unambiguous prefix works.

### Batteries included: 100+ tools, plus "smart tools"

OneTool includes [100+ tools](../reference/tools/index.md), including web search (Brave, Grounding, Firecrawl), web fetch using trafilatura, databases, file operations, diagrams, file conversions, and more - ready to use out of the box.

It even has "Smart Tools" -  [LLM-powered transformation](../reference/tools/llm.md). Delegate work to cheaper LLMs instead of using your expensive AI coding agent. For example: fetch a page, summarise it with Gemini-3-Flash ($0.50/M input tokens), then pass the result back to Claude Opus 4.5 ($5/M input tokens). That's a 10× saving.

Normally, with great power comes configurability challenges.

However, OneTool keeps it simple and consistent with sensible defaults: a single, well-structured [YAML config](../learn/configuration.md), with global and project scopes, and per-tool-pack configuration (timeouts, limits, models, etc).

You also get a range of meta tools to help with the coding aspects, plus [structured logging](../learn/extending/extension-tools.md#logging-with-logspan) and [runtime statistics](../reference/tools/ot.md#otstats) to track tool calls, success rates, context saved, and cost estimates.

### Security: powerful, with guardrails

OneTool is built for developers. It's very powerful -  so knowledge is your greatest protection. However, OneTool still includes multiple layers of security:

- Isolated [`secrets.yaml`](../reference/cli/onetool-config.md#secrets-configuration) - so you can share your configuration without leaking secrets
- [AST code validation](../learn/security.md) -  configurable permissions that warn or block risky function calls
- [Path boundaries](../learn/security.md#4-path-boundary-enforcement) -  ensures file operations are constrained to allowed directories, handles symlink resolution, and honours sensitive exclusions
- [Output sanitisation](../learn/security.md#7-output-sanitization-prompt-injection-protection) -  protection against indirect prompt injection via external content wrapping and sanitisation

### Extensible: build your own tools (and bring your existing MCP servers)

Every developer loves plugins, extensions, and ways to make tools even better. OneTool is highly configurable and extensible.

- [Scaffold tools](../learn/extending/extension-tools.md) -  enables you and your coding agent to build new tools as part of the conversation. New tools are just Python functions. Check out the [demo](https://youtu.be/AZz03Yw0s1E) of Claude building a Wikipedia fetcher in under three minutes.
- [MCP server proxy](../reference/cli/onetool-config.md#external-mcp-servers) - allows you to wrap any MCP Server with OneTool, configure it with YAML, and call it explicitly - without the tool tax and context rot.

### Testing, benchmarking, and proper engineering

To make it easy to develop new tool packs (groups of tools), OneTool includes a powerful [testing and benchmarking](../reference/cli/bench.md) harness that compares your tool against other MCP servers using a real LLM. Define tasks in YAML and get objective metrics: token counts, costs, accuracy scores, timing, and more.

OneTool was written with strong engineering practices:

- 1,200+ tests (smoke, unit, integration tiers)
- OpenSpec as a change proposal process (specs before code; architecture decisions documented)
- Python best practices: type hints, Ruff formatting/linting and other Python best practices

## Give it a try (without paying the tax)

If AI is the King, and MCP servers are your thing, then OneTool will help you stop paying the "tool tax" (around $30 per tool per month), avoid context rot, and unlock superpowers for you and your AI coding buddy.

Download and install it, and give your agentic engineering the boost it needs.

<a href="/learn/" class="btn btn--primary">Get Started with OneTool</a>


<a href="https://github.com/beycom/onetool-mcp" class="btn btn--secondary">OneTool on GitHub</a>

