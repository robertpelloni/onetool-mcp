# LLM Tools

LLM-powered data transformation tools. Takes input data and a prompt, uses an LLM to process/transform it.

## Highlights

- Single function for any data transformation
- Configurable model via OpenRouter or OpenAI-compatible API
- Chain with other tools for structured output extraction

## Functions

| Function | Description |
|----------|-------------|
| `ot_llm.transform(data, prompt, ...)` | Transform data using LLM instructions |
| `ot_llm.transform_file(prompt, in_file, out_file, ...)` | Transform file content and write to output |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `data` | any | Data to transform (converted to string) |
| `prompt` | str | Instructions for transformation |
| `in_file` | str | Input file path (for transform_file) |
| `out_file` | str | Output file path (for transform_file) |
| `model` | str | AI model to use (uses `ot_llm.model` from config) |
| `json_mode` | bool | If True, request JSON output format (default: False) |

## Requires

Configuration (tool not available until all are set):
- `OPENAI_API_KEY` in secrets.yaml
- `ot_llm.base_url` in onetool.yaml (e.g., `https://openrouter.ai/api/v1`)
- `ot_llm.model` in onetool.yaml (e.g., `openai/gpt-5-mini`)

## Examples

```python
# Extract structured data from search results
ot_llm.transform(
    data=brave.search(query="gold price today"),
    prompt="Extract the current gold price in USD/oz as a single number"
)

# Convert to YAML format
ot_llm.transform(
    data=some_data,
    prompt="Return ONLY valid YAML with fields: name, price, url"
)

# Summarize content
ot_llm.transform(
    data=web.fetch(url="https://example.com/article"),
    prompt="Summarize the main points in 3 bullet points"
)

# Get JSON output with json_mode
ot_llm.transform(
    data=raw_data,
    prompt="Extract name and email fields",
    json_mode=True
)

# Transform a file
ot_llm.transform_file(
    prompt="Convert this markdown to reStructuredText format",
    in_file="README.md",
    out_file="README.rst"
)
```

## Configuration

Add to `onetool.yaml`:

```yaml
tools:
  ot_llm:
    base_url: https://openrouter.ai/api/v1
    model: openai/gpt-5-mini
    timeout: 30        # API timeout in seconds (default: 30)
    max_tokens: 4096   # Maximum tokens in response (optional)
```
