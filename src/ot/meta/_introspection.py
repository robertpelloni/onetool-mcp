"""Alias and snippet introspection functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ot.config import get_config
from ot.logging import LogSpan

if TYPE_CHECKING:
    from ot.meta._constants import InfoLevel

log = LogSpan


def aliases(
    *,
    pattern: str = "",
    info: InfoLevel = "min",
) -> list[dict[str, Any] | str]:
    """List aliases with optional filtering.

    Lists all configured aliases.
    Use pattern for substring filtering.

    Args:
        pattern: Filter aliases by name or target pattern (case-insensitive substring)
        info: Output verbosity level - "list" (names only), "min" (name -> target),
              or "full" (structured dict with name and target)

    Returns:
        List of alias names, strings, or dicts depending on info level

    Example:
        ot.aliases()
        ot.aliases(pattern="search")
        ot.aliases(info="list")
        ot.aliases(pattern="ws", info="full")
    """
    with log(span="ot.aliases", pattern=pattern or None, info=info) as s:
        cfg = get_config()

        if not cfg.alias:
            s.add("count", 0)
            return []

        # Filter by pattern or list all
        items = sorted(cfg.alias.items())
        if pattern:
            pattern_lower = pattern.lower()
            items = [(k, v) for k, v in items if pattern_lower in k.lower() or pattern_lower in v.lower()]

        s.add("count", len(items))

        # info="list" - just names
        if info == "list":
            return [k for k, v in items]

        # info="full" - structured dicts
        if info == "full":
            return [{"name": k, "target": v} for k, v in items]

        # info="min" (default) - "name -> target" strings
        return [f"{k} -> {v}" for k, v in items]


def snippets(
    *,
    pattern: str = "",
    info: InfoLevel = "min",
) -> list[dict[str, Any] | str]:
    """List snippets with optional filtering.

    Lists all configured snippets.
    Use pattern for substring filtering.

    Args:
        pattern: Filter snippets by name/description pattern (case-insensitive substring)
        info: Output verbosity level - "list" (names only), "min" (name: description),
              or "full" (complete definition with params, body, example)

    Returns:
        List of snippet names, strings, or dicts depending on info level

    Example:
        ot.snippets()
        ot.snippets(pattern="pkg")
        ot.snippets(info="list")
        ot.snippets(pattern="brv_research", info="full")
    """
    with log(span="ot.snippets", pattern=pattern or None, info=info) as s:
        cfg = get_config()

        if not cfg.snippets:
            s.add("count", 0)
            return []

        # Filter by pattern or list all
        items = sorted(cfg.snippets.items())
        if pattern:
            pattern_lower = pattern.lower()
            items = [
                (k, v) for k, v in items
                if pattern_lower in k.lower() or pattern_lower in (v.description or "").lower()
            ]

        s.add("count", len(items))

        # info="list" - just names
        if info == "list":
            return [k for k, v in items]

        # info="full" - complete definition for each snippet
        if info == "full":
            results: list[dict[str, Any] | str] = []
            for snippet_name, snippet_def in items:
                # Format output as YAML-like
                lines = [f"name: {snippet_name}"]

                if snippet_def.description:
                    lines.append(f"description: {snippet_def.description}")

                if snippet_def.params:
                    lines.append("params:")
                    for param_name, param_def in snippet_def.params.items():
                        param_parts = []
                        if param_def.default is not None:
                            param_parts.append(f"default: {param_def.default}")
                        if param_def.description:
                            param_parts.append(f'description: "{param_def.description}"')
                        lines.append(f"  {param_name}: {{{', '.join(param_parts)}}}")

                lines.append("body: |")
                for body_line in snippet_def.body.rstrip().split("\n"):
                    lines.append(f"  {body_line}")

                # Add example invocation
                lines.append("")
                lines.append("# Example:")

                # Build example with defaults
                example_args = []
                for param_name, param_def in snippet_def.params.items():
                    if param_def.default is not None:
                        continue  # Skip params with defaults in example
                    example_args.append(f'{param_name}="..."')

                if example_args:
                    lines.append(f"# ${snippet_name} {' '.join(example_args)}")
                else:
                    lines.append(f"# ${snippet_name}")

                results.append("\n".join(lines))

            return results

        # info="min" (default) - "name: description" strings
        return [f"{k}: {v.description or '(no description)'}" for k, v in items]
