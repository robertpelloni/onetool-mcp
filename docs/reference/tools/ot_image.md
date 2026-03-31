# OT Image

Load images and ask vision questions via an OpenAI-compatible API.

Short alias: `img`

## Highlights

- Load images from file paths, URLs, or the clipboard once; reference by handle for follow-up questions
- Ask multiple questions in a single model call — answers returned as paired question/answer list
- Structured summaries (text, mode, type, colours) extracted and cached in `meta.json`
- Clipboard shortcuts `clip_ask()` and `clip_view()` — no handle juggling needed
- Content-hash deduplication — loading the same image twice returns the existing handle
- Session LRU cache keeps resized model bytes in-memory to avoid repeated disk reads
- Storage at `.onetool/images/` persists across sessions; `purge()` cleans up by age

## Functions

| Function | Description |
|----------|-------------|
| `img.load(img, ...)` | Load a single image; return a stable handle |
| `img.load_batch(img, ...)` | Load multiple images from a glob or list |
| `img.ask(img, q, ...)` | Ask one or more questions about an image |
| `img.clip_ask(q, ...)` | Shorthand: ask about the current clipboard image |
| `img.clip_view()` | Shorthand: structured summary of the current clipboard image |
| `img.summary(img)` | Extract and cache a structured summary of an image |
| `img.list()` | List all loaded images with metadata |
| `img.delete(handle)` | Delete an image and free session cache |
| `img.purge(...)` | Delete images by age or delete all |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `img` | str | Image source: file path, `"https://..."` URL, `"clip"` for clipboard, or `"#handle"` to reference an existing handle |
| `handle` | str | Custom handle name for `load()` (e.g. `"logo"`). Omit for auto-generated `img_<8hex>` |
| `q` | str \| list[str] | Question(s) to ask. Multiple questions are batched into one model call |
| `max_edge` | int | Max longest edge in pixels for in-memory model resize. Default: `1568` |
| `all` | bool | `purge(all=True)` deletes all images regardless of age |
| `minutes` | int | `purge(minutes=N)` deletes images older than N minutes. Default: `15` |

## Requires

- A vision model: set `tools.ot_image.model` or the top-level `llm.model` for `ask()`, `summary()`, `clip_ask()`, and `clip_view()`.
- `OPENAI_API_KEY` in `secrets.yaml` for vision model calls.

## Configuration

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.ot_image.model` | str | `""` | Vision model for `ask()` and `summary()`. Falls back to `llm.model` |
| `tools.ot_image.base_url` | str | `""` | OpenAI-compatible base URL. Falls back to `llm.base_url` |
| `tools.ot_image.max_edge` | int | `1568` | Maximum longest edge (pixels) for model-upload resize |
| `tools.ot_image.session_cache_size` | int | `10` | In-memory LRU cache cap (number of images) |

```yaml
# Minimal — inherits model and base_url from top-level llm: block
llm:
  base_url: https://openrouter.ai/api/v1
  model: google/gemini-2-flash-preview

# Override just for ot_image (optional)
tools:
  ot_image:
    model: openai/gpt-4o-mini   # overrides llm.model for vision calls only
    max_edge: 1568
    session_cache_size: 10
```

### Defaults

- If `tools.ot_image` is omitted, `load()` and `list()` work without config. `ask()` and `summary()` require a model via `tools.ot_image.model` or `llm.model`.
- `model` and `base_url` fall back to the top-level `llm:` config block. API key is always read from the `OPENAI_API_KEY` secret.

## Examples

```python
# Load from file and ask a question
result = img.load(img="~/screenshots/dashboard.png")
img.ask(img=result["handle"], q="What is the main metric shown?")

# Ask multiple questions in one call
img.ask(
    img="~/screenshots/dashboard.png",
    q=["What framework is shown?", "Is this dark mode?"]
)

# Load with a custom handle name
img.load(img="~/assets/logo.png", handle="logo")
img.ask(img="#logo", q="What colour is the logo?")

# Clipboard shortcuts (no load step needed)
img.clip_ask(q="Extract all text from this screenshot")
img.clip_view()

# Structured summary — cached after first call
img.summary(img="#logo")

# Load a batch from glob
img.load_batch(img="~/screenshots/*.png")

# Load a batch from a list
img.load_batch(img=["~/a.png", "~/b.png"])

# List all loaded images
img.list()

# Delete a single image
img.delete(handle="#img_a3f7b2c4")

# Purge images older than 1 hour
img.purge(minutes=60)

# Purge all images
img.purge(all=True)
```

## See Also

- [Vision comparison: img.ask vs direct attachment](../../results/compare-vision.md) — benchmark showing accuracy and token cost trade-offs
