"""Tool info builders for local and proxy tools."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ot.meta._constants import InfoLevel


def _parse_docstring(doc: str | None) -> dict[str, Any]:
    """Parse docstring using docstring-parser library.

    Args:
        doc: Function docstring

    Returns:
        Dict with 'short', 'args', 'returns', and 'example' keys
    """
    from docstring_parser import parse as parse_docstring

    if not doc:
        return {"short": "", "args": [], "returns": "", "example": ""}

    parsed = parse_docstring(doc)

    # Extract example from examples section
    example = ""
    if parsed.examples:
        example = "\n".join(
            ex.description or "" for ex in parsed.examples if ex.description
        )

    # Format args as "name: description" strings
    args = [
        f"{p.arg_name}: {p.description or '(no description)'}" for p in parsed.params
    ]

    return {
        "short": parsed.short_description or "",
        "args": args,
        "returns": parsed.returns.description if parsed.returns else "",
        "example": example,
    }


def _truncate(s: str, n: int = 100) -> str:
    """Truncate string to n characters, appending … if cut."""
    return s[:n] + "…" if len(s) > n else s


def _build_tool_info(
    full_name: str, func: Any, source: str, info: InfoLevel
) -> dict[str, Any] | str:
    """Build tool info dict for a single tool.

    Args:
        full_name: Full tool name (e.g., "brave.search")
        func: The function object
        source: Source identifier (e.g., "local", "mcp:github")
        info: Output verbosity level ("list", "min", "full")

    Returns:
        Tool name string if info="list", otherwise dict with tool info
    """
    if info == "list":
        return full_name

    if func:
        try:
            sig = inspect.signature(func)
            signature = f"{full_name}{sig}"
        except (ValueError, TypeError):
            signature = f"{full_name}(...)"
        parsed = _parse_docstring(func.__doc__)
        description = parsed["short"]
    else:
        signature = f"{full_name}(...)"
        description = ""
        parsed = _parse_docstring(None)

    if info == "min":
        return {"name": full_name, "description": _truncate(description)}

    if info == "core":
        tool_info: dict[str, Any] = {
            "name": full_name,
            "signature": signature,
            "description": _truncate(description, 200),
        }
        if parsed["args"]:
            tool_info["args"] = parsed["args"]
        tool_info["source"] = source
        return tool_info

    # info == "full"
    tool_info = {
        "name": full_name,
        "signature": signature,
        "description": description,
    }
    # Include full documentation for LLM context
    if parsed["args"]:
        tool_info["args"] = parsed["args"]
    if parsed["returns"]:
        tool_info["returns"] = parsed["returns"]
    if parsed["example"]:
        tool_info["example"] = parsed["example"]
    tool_info["source"] = source
    return tool_info


def _schema_to_signature(full_name: str, schema: dict[str, Any]) -> str:
    """Convert JSON Schema to Python-like signature string.

    Args:
        full_name: Full tool name (e.g., "github.search")
        schema: JSON Schema dict with 'properties' and 'required' keys

    Returns:
        Signature string like "github.search(query: str, repo: str = '...')"
    """
    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    if not props:
        return f"{full_name}()"

    params: list[str] = []
    # Process required params first, then optional
    for prop_name in sorted(props.keys(), key=lambda k: (k not in required, k)):
        prop_def = props[prop_name]
        prop_type = prop_def.get("type", "Any")

        # Map JSON Schema types to Python-like types
        type_map = {
            "string": "str",
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            "array": "list",
            "object": "dict",
        }

        # Handle JSON Schema union types (e.g., ["string", "null"])
        if isinstance(prop_type, list):
            # Filter out "null" and map remaining types
            non_null = [t for t in prop_type if t != "null"]
            if non_null:
                mapped = [type_map.get(t, t) for t in non_null]
                py_type = " | ".join(mapped)
                if "null" in prop_type:
                    py_type = f"{py_type} | None"
            else:
                py_type = "None"
        else:
            py_type = type_map.get(prop_type, prop_type)

        if prop_name in required:
            params.append(f"{prop_name}: {py_type}")
        else:
            default = prop_def.get("default")
            if default is not None:
                params.append(f"{prop_name}: {py_type} = {default!r}")
            else:
                params.append(f"{prop_name}: {py_type} = ...")

    return f"{full_name}({', '.join(params)})"


def _parse_input_schema(schema: dict[str, Any]) -> list[str]:
    """Extract argument descriptions from JSON Schema properties.

    Args:
        schema: JSON Schema dict with 'properties' key

    Returns:
        List of "param_name: description" strings matching local tool format
    """
    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    args: list[str] = []
    # Process required params first, then optional
    for prop_name in sorted(props.keys(), key=lambda k: (k not in required, k)):
        prop_def = props[prop_name]
        description = prop_def.get("description", "(no description)")
        args.append(f"{prop_name}: {description}")

    return args


def _build_proxy_tool_info(
    full_name: str,
    description: str,
    input_schema: dict[str, Any],
    source: str,
    info: InfoLevel,
) -> dict[str, Any] | str:
    """Build tool info dict for a proxy tool using its input schema.

    Args:
        full_name: Full tool name (e.g., "github.search")
        description: Tool description from MCP server
        input_schema: JSON Schema for tool input
        source: Source identifier (e.g., "mcp:github")
        info: Output verbosity level ("list", "min", "full")

    Returns:
        Tool name string if info="list", otherwise dict with tool info
    """
    if info == "list":
        return full_name

    if info == "min":
        return {"name": full_name, "description": _truncate(description)}

    if info == "core":
        tool_info: dict[str, Any] = {
            "name": full_name,
            "signature": _schema_to_signature(full_name, input_schema),
            "description": _truncate(description, 200),
        }
        args = _parse_input_schema(input_schema)
        if args:
            tool_info["args"] = args
        tool_info["source"] = source
        return tool_info

    # info == "full"
    tool_info = {
        "name": full_name,
        "signature": _schema_to_signature(full_name, input_schema),
        "description": description,
    }

    # Include args if schema has properties with descriptions
    args = _parse_input_schema(input_schema)
    if args:
        tool_info["args"] = args

    tool_info["source"] = source
    return tool_info
