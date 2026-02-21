# Timer

Named stopwatch timers for performance measurement across tool calls.

## Highlights

- Persistent timers across multiple tool calls
- Lap timing support (`elapsed()` keeps timer running)
- Human-readable duration formatting (ms, seconds, minutes)
- Store multiple timing results for comparison

## Functions

| Function | Description |
|----------|-------------|
| `ot_timer.start(name)` | Start or restart a named timer |
| `ot_timer.elapsed(name, store_as)` | Get elapsed time (lap behavior) |
| `ot_timer.list()` | Show all stored results and active timers |
| `ot_timer.clear(results)` | Clear running timers; optionally clear stored results |

## Key Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | `"_default"` | Timer name for identifying multiple timers |
| `store_as` | str | `None` | Optional key to store elapsed result for later retrieval |
| `results` | bool | `False` | If True, `clear()` also removes stored results |

## Examples

### Basic timing

```python
ot_timer.start(name="api_call")
# ... make API call ...
ot_timer.elapsed(name="api_call")
# {name: "api_call", elapsed_seconds: 1.234, elapsed_formatted: "1.234s", started_at: "..."}
```

### Lap timing

```python
ot_timer.start(name="workflow")
ot_timer.elapsed(name="workflow", store_as="step1")
# ... more work ...
ot_timer.elapsed(name="workflow", store_as="step2")
ot_timer.list()  # shows stored results + active timers
```

## Notes

- Timers persist across tool calls (useful for multi-step workflows)
- Uses `perf_counter()` for accurate elapsed time
- `elapsed()` keeps timer running (lap behavior)
- `clear()` removes timers but preserves stored results by default
- Results stored via `store_as` remain until session ends
