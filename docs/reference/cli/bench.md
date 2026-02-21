# bench

Real agent + MCP testing. Define tasks in YAML, get objective metrics: token counts, costs, accuracy scores, timing.

## Usage

```bash
bench [COMMAND] [OPTIONS]
```

## Commands

### run

Run benchmark tasks from a YAML file.

```bash
bench run FILE [OPTIONS]
```

#### Options

| Option | Description |
|--------|-------------|
| `-c, --config PATH` | Path to `onetool.yaml` configuration file |
| `-s, --secrets PATH` | Path to secrets file (LLM API keys) |
| `--tui` | Interactive TUI for selecting benchmark files |
| `--csv` | Export results to CSV in `tmp/result-YYYYMMDD-HHMM.csv` |
| `-o, --output PATH` | Write results to YAML file |
| `--scenario NAME` | Run only scenarios matching NAME |
| `--task NAME` | Run only tasks matching NAME |
| `--tag TAG` | Run only tasks with matching tag |
| `-v, --verbose` | Show detailed per-call metrics |
| `--dry-run` | Validate config without making API calls |
| `--trace` | Show timestamped request/response cycle for debugging |
| `--no-color` | Disable colored output (for CI/CD compatibility) |

## Task Types

| Type | Description |
|------|-------------|
| `type: direct` | Direct MCP tool invocation (no LLM) |
| `type: harness` | LLM benchmark with MCP servers (default) |

## Examples

```bash
# Run comparison benchmark
bench run demo/bench/compare.yaml

# Run tool benchmark
bench run demo/bench/tool_db.yaml
```

## Benchmark File Structure

```yaml
defaults:
  timeout: 60
  model: openai/gpt-5-mini

evaluators:
  accuracy:
    model: openai/gpt-5-mini
    prompt: |
      Evaluate this response.
      Response: {response}
      Return JSON: {"score": <0-100>, "reason": "<explanation>"}

scenarios:
  - name: Search Test
    tasks:
      - name: "search:base"
        server:              # No server = baseline
        evaluate: accuracy
        prompt: "Search for AI news"

      - name: "search:onetool"
        server: onetool
        evaluate: accuracy
        prompt: |
          >>> brave.search(query="AI news")

servers:
  onetool:
    type: stdio
    command: uv
    args: ["run", "onetool"]
```

### Multi-Prompt Tasks

Use `---PROMPT---` delimiter to split a task into sequential prompts. Each prompt completes its agentic loop before the next begins, with conversation history accumulating.

```yaml
- name: multi-step-task
  server: onetool
  prompt: |
    >>>
    ```python
    npm = package.version(registry="npm", packages={"express": "4.0.0"})
    ```
    Return the latest version.
    ---PROMPT---
    >>>
    ```python
    pypi = package.version(registry="pypi", packages={"httpx": "0.20.0"})
    ```
    Return the latest version.
    ---PROMPT---
    Summarize both versions as: "express: [version], httpx: [version]"
```

## Configuration

| File | Location | Purpose |
|------|----------|---------|
| `bench.yaml` | `.onetool/bench.yaml` or `~/.onetool/bench.yaml` | Benchmark harness config |
| `bench-secrets.yaml` | `.onetool/bench-secrets.yaml` or `~/.onetool/bench-secrets.yaml` | LLM API keys (OPENAI_API_KEY, etc.) |

**Resolution:** `BENCH_CONFIG` env var → project → global

**Note:** Benchmark API keys (for running LLMs) go in `bench-secrets.yaml`, not `secrets.yaml` (which is for tool API keys).

## Output

Benchmarks produce:
- Token counts (input, output, total)
- Cost estimates (USD)
- Timing information
- Evaluation scores

## Demo Project

The `demo/` folder provides sample configurations and data for testing.

### Structure

```
demo/
  .onetool/
    onetool.yaml      # MCP server config
    bench.yaml        # Benchmark harness config
    bench-secrets.yaml  # LLM API keys for benchmarks
  bench/              # Benchmark YAML files
  data/               # Sample data (northwind.db, downloaded via setup)
```

### Running with Demo Config

```bash
# Run benchmarks
bench run demo/bench/compare.yaml

# Or use justfile
just demo::bench bench/compare.yaml   # run with CSV output
just demo::bench --tui                # interactive TUI picker
```

### Benchmark Files

| File | Description |
|------|-------------|
| `compare.yaml` | Compare base vs MCP vs OneTool responses |
| `tool_db.yaml` | Database tool benchmark |

## Prompting Best Practices

Two rules prevent 90% of tool-calling problems:

```yaml
system_prompt: |
  Never retry successful tool calls to get "better" results.
  If a tool call fails, report the error - do not compute the result yourself.
```

**Why:**

- **No retries on success:** Agents sometimes want to "improve" results by calling the same tool again. This wastes tokens and can cause loops.
- **No manual computation on failure:** When a tool fails, agents often try to compute the answer themselves. This defeats the purpose of using tools.

### Batch Operations

For multiple related queries, use batch functions:

```python
# Instead of multiple calls
brave.search(query="topic 1")
brave.search(query="topic 2")

# Use batch
brave.search_batch(queries=["topic 1", "topic 2"])
```

### Token Efficiency

- Use `>>>` for simple calls
- Use code fences for multi-step operations
- Prefer batch operations over multiple calls