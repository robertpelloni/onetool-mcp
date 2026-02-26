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
    info: InfoLevel = "default",
) -> list[dict[str, Any] | str]:
    """List aliases with optional filtering.

    Lists all configured aliases.
    Use pattern for substring filtering.

    Args:
        pattern: Filter aliases by name or target pattern (case-insensitive substring)
        info: Output verbosity level - "min" (names only), "default" (structured
              dicts with name and target, default), or "full" (same as default)

    Returns:
        List of alias names (info="min") or dicts (info="default"/"full")

    Example:
        ot.aliases()
        ot.aliases(pattern="search")
        ot.aliases(info="min")
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

        # info="min" - just names
        if info == "min":
            return [k for k, v in items]

        # info="default" and "full" - structured dicts
        return [{"name": k, "target": v} for k, v in items]


def snippets(
    *,
    pattern: str = "",
    info: InfoLevel = "default",
) -> list[dict[str, Any] | str]:
    """List snippets with optional filtering.

    Lists all configured snippets.
    Use pattern for substring filtering.

    Args:
        pattern: Filter snippets by name/description pattern (case-insensitive substring)
        info: Output verbosity level - "min" (names only), "default" (name +
              description dicts, default), or "full" (name + description + params)

    Returns:
        List of snippet names (info="min") or dicts (info="default"/"full")

    Example:
        ot.snippets()
        ot.snippets(pattern="pkg")
        ot.snippets(info="min")
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

        # info="min" - just names
        if info == "min":
            return [k for k, v in items]

        # info="full" - name + description + params summary
        if info == "full":
            results: list[dict[str, Any] | str] = []
            for snippet_name, snippet_def in items:
                entry: dict[str, Any] = {
                    "name": snippet_name,
                    "description": snippet_def.description or "(no description)",
                }
                if snippet_def.params:
                    entry["params"] = list(snippet_def.params.keys())
                results.append(entry)
            return results

        # info="default" - name + description dicts
        return [
            {"name": k, "description": v.description or "(no description)"}
            for k, v in items
        ]


def snippet_info(
    *,
    name: str = "",
    info: InfoLevel = "default",
) -> dict[str, Any]:
    """Get detailed info for a single snippet.

    Returns description, params, body, and example.

    Args:
        name: Snippet name (without $ prefix, e.g., "brv_research")
        info: Output verbosity level - "min" (name + description + param names),
              "default" (+ param details + example, default), or "full"
              (+ body template)

    Returns:
        Snippet info dict

    Example:
        ot.snippet_info(name="brv_research")
        ot.snippet_info(name="c7", info="full")
    """
    with log(span="ot.snippet_info", name=name or None, info=info) as s:
        cfg = get_config()

        if not cfg.snippets or name not in cfg.snippets:
            s.add("found", False)
            available = sorted(cfg.snippets.keys()) if cfg.snippets else []
            return {
                "error": f"Snippet '{name}' not found.",
                "available": available,
            }

        snippet_def = cfg.snippets[name]
        s.add("found", True)

        if info == "min":
            entry: dict[str, Any] = {
                "name": name,
                "description": snippet_def.description or "(no description)",
            }
            if snippet_def.params:
                entry["params"] = list(snippet_def.params.keys())
            return entry

        # Build example invocation
        example_args = []
        for param_name, param_def in snippet_def.params.items():
            if param_def.default is None:
                example_args.append(f'{param_name}="..."')
        example = f"${name}"
        if example_args:
            example += " " + " ".join(example_args)

        # Build params detail
        params_detail: dict[str, Any] = {}
        for param_name, param_def in snippet_def.params.items():
            param_entry: dict[str, Any] = {}
            if param_def.default is not None:
                param_entry["default"] = param_def.default
            if param_def.description:
                param_entry["description"] = param_def.description
            params_detail[param_name] = param_entry

        if info == "default":
            return {
                "name": name,
                "description": snippet_def.description or "(no description)",
                "params": params_detail,
                "example": example,
            }

        # info == "full"
        return {
            "name": name,
            "description": snippet_def.description or "(no description)",
            "params": params_detail,
            "body": snippet_def.body,
            "example": example,
        }
