"""Shared implementation for browser annotation tool packs.

Not a tool pack itself — provides the core logic used by
``devtools_util`` and ``playwright_util``.

Uses inject.js v2.0 (bundled in ``ot.assets``).
"""

from __future__ import annotations

import json
from typing import Any

from ot.assets import get_inject_script
from ot.logging import LogSpan
from ot.proxy import get_proxy_manager


def _check_server(server: str) -> str | None:
    """Check if the MCP server is connected.

    Returns:
        Error message string if not connected, None if OK.
    """
    proxy = get_proxy_manager()
    if server not in proxy.servers:
        available = ", ".join(proxy.servers) or "none"
        return (
            f"Error: MCP server '{server}' not connected. "
            f"Available servers: {available}"
        )
    return None


def _extract_result(raw: str) -> str:
    """Extract the result value from an MCP tool response.

    MCP servers wrap results in markdown. This helper extracts just the value.

    Playwright format::

        ### Result
        <value>
        ### Ran Playwright code
        ...

    DevTools format::

        # evaluate_script response
        Script ran on page and returned:
        ```json
        <value>
        ```
    """
    # Playwright: "### Result\n<value>\n### ..."
    marker = "### Result\n"
    if raw.startswith(marker):
        value = raw[len(marker):]
        end = value.find("\n### ")
        if end != -1:
            value = value[:end]
        return value.strip()

    # DevTools: "# evaluate_script response\n...```json\n<value>\n```"
    json_fence = "```json\n"
    fence_start = raw.find(json_fence)
    if fence_start != -1:
        value = raw[fence_start + len(json_fence):]
        fence_end = value.find("\n```")
        if fence_end != -1:
            value = value[:fence_end]
        return value.strip()

    return raw


def _eval_js(server: str, tool: str, expression: str) -> str:
    """Evaluate a JavaScript expression in the browser and return its result.

    Wraps the expression in an arrow function: ``() => { return <expr>; }``.

    Args:
        server: MCP server name (e.g. ``"devtools"``, ``"playwright"``).
        tool: Eval tool name on that server (e.g. ``"evaluate_script"``).
        expression: JavaScript expression to evaluate.

    Returns:
        String result from the browser.
    """
    proxy = get_proxy_manager()
    fn = f"() => {{ return {expression}; }}"
    raw = proxy.call_tool_sync(server, tool, {"function": fn})
    return _extract_result(raw)


def _exec_js(server: str, tool: str, script: str) -> str:
    """Execute a JavaScript script in the browser (no return value expected).

    Wraps the script in an arrow function: ``() => { <script> }``.

    Args:
        server: MCP server name (e.g. ``"devtools"``, ``"playwright"``).
        tool: Eval tool name on that server.
        script: JavaScript code to execute.

    Returns:
        String result from the browser (typically empty or undefined).
    """
    proxy = get_proxy_manager()
    fn = f"() => {{ {script} }}"
    raw = proxy.call_tool_sync(server, tool, {"function": fn})
    return _extract_result(raw)


_CHECK_JS = (
    "({"
    "  ready: !!(window.__inspector && window.__inspector.isReady()),"
    "  version: window.__inspector ? window.__inspector.version : null"
    "})"
)


def inject_annotations(
    server: str, tool: str, pack_name: str
) -> dict[str, Any]:
    """Inject the annotation script into the current browser page.

    Args:
        server: MCP server name.
        tool: Eval tool name on that server.
        pack_name: Calling pack's name (for LogSpan).

    Returns:
        Dict with ``success``, ``ready``, and ``version`` fields.
    """
    with LogSpan(span=f"{pack_name}.inject_annotations") as s:
        err = _check_server(server)
        if err:
            s.add(error=err)
            return {"success": False, "ready": False, "version": None, "error": err}

        try:
            # Check if already injected
            check = _eval_js(server, tool, _CHECK_JS)
            try:
                state = json.loads(check)
            except (json.JSONDecodeError, TypeError):
                state = {"ready": False, "version": None}

            if state.get("ready"):
                s.add(action="already_injected", version=state.get("version"))
                return {
                    "success": True,
                    "ready": True,
                    "version": state.get("version"),
                }

            # Inject the script and verify
            _exec_js(server, tool, get_inject_script())
            verify = _eval_js(server, tool, _CHECK_JS)

            try:
                result = json.loads(verify)
            except (json.JSONDecodeError, TypeError):
                result = {"ready": False, "version": None}

            success = bool(result.get("ready"))
            s.add(action="injected", success=success, version=result.get("version"))
            return {
                "success": success,
                "ready": result.get("ready", False),
                "version": result.get("version"),
            }
        except Exception as e:
            s.add(error=str(e))
            return {"success": False, "ready": False, "version": None, "error": str(e)}


def highlight_element(
    server: str,
    tool: str,
    pack_name: str,
    *,
    selector: str,
    label: str,
    color: str = "orange",
    element_id: str | None = None,
) -> dict[str, Any]:
    """Highlight elements matching a CSS selector.

    Args:
        server: MCP server name.
        tool: Eval tool name on that server.
        pack_name: Calling pack's name (for LogSpan).
        selector: CSS selector for the target element(s).
        label: Text label displayed on the highlight overlay.
        color: Colour scheme - ``orange``, ``red``, ``blue``, or ``green``.
        element_id: Optional custom annotation ID.

    Returns:
        Dict with ``success``, ``count``, and ``ids`` fields.
    """
    with LogSpan(
        span=f"{pack_name}.highlight_element",
        selector=selector,
        label=label,
        color=color,
    ) as s:
        err = _check_server(server)
        if err:
            s.add(error=err)
            return {"success": False, "count": 0, "ids": [], "error": err}

        try:
            id_arg = json.dumps(element_id) if element_id else "null"
            js = (
                f"window.__inspector.addAnnotation("
                f"{json.dumps(selector)}, {id_arg}, {json.dumps(label)}, {json.dumps(color)})"
            )
            raw = _eval_js(server, tool, js)
            try:
                result = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                result = {"success": False, "count": 0, "ids": [], "error": raw}

            s.add(success=result.get("success"), count=result.get("count", 0))
            return result
        except Exception as e:
            s.add(error=str(e))
            return {"success": False, "count": 0, "ids": [], "error": str(e)}


def scan_annotations(
    server: str, tool: str, pack_name: str
) -> list[dict[str, Any]]:
    """Read all current annotations from the page.

    Args:
        server: MCP server name.
        tool: Eval tool name on that server.
        pack_name: Calling pack's name (for LogSpan).

    Returns:
        List of annotation dicts.
    """
    with LogSpan(span=f"{pack_name}.scan_annotations") as s:
        err = _check_server(server)
        if err:
            s.add(error=err)
            return []

        try:
            raw = _eval_js(
                server, tool, "window.__inspector.scanAnnotations()"
            )
            try:
                annotations = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                annotations = []

            s.add(count=len(annotations))
            return annotations
        except Exception as e:
            s.add(error=str(e))
            return []


def clear_annotations(
    server: str, tool: str, pack_name: str
) -> dict[str, Any]:
    """Remove all annotations and visual highlights from the page.

    Args:
        server: MCP server name.
        tool: Eval tool name on that server.
        pack_name: Calling pack's name (for LogSpan).

    Returns:
        Dict with ``success`` and ``cleared`` count.
    """
    with LogSpan(span=f"{pack_name}.clear_annotations") as s:
        err = _check_server(server)
        if err:
            s.add(error=err)
            return {"success": False, "cleared": 0, "error": err}

        try:
            raw = _eval_js(
                server, tool, "window.__inspector.clearAnnotations()"
            )
            try:
                result = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                result = {"success": False, "cleared": 0}

            s.add(success=result.get("success"), cleared=result.get("cleared", 0))
            return result
        except Exception as e:
            s.add(error=str(e))
            return {"success": False, "cleared": 0, "error": str(e)}


def guide_user(
    server: str,
    tool: str,
    pack_name: str,
    *,
    task: str,
    steps: list[dict[str, str]],
) -> dict[str, Any]:
    """Highlight a sequence of elements to guide the user through a task.

    Args:
        server: MCP server name.
        tool: Eval tool name on that server.
        pack_name: Calling pack's name (for LogSpan).
        task: Short description of the guided task.
        steps: List of step dicts with ``selector``, ``label``, optional ``color``.

    Returns:
        Dict with ``task``, ``total``, ``highlighted``, and ``results``.
    """
    with LogSpan(
        span=f"{pack_name}.guide_user", task=task, stepCount=len(steps)
    ) as s:
        err = _check_server(server)
        if err:
            s.add(error=err)
            return {"task": task, "total": len(steps), "highlighted": 0, "results": [], "error": err}

        results = []
        highlighted = 0

        for i, step in enumerate(steps):
            selector = step["selector"]
            label = step["label"]
            color = step.get("color", "orange")
            step_id = f"guide-{i}"

            try:
                id_js = json.dumps(step_id)
                js = (
                    f"window.__inspector.addAnnotation("
                    f"{json.dumps(selector)}, {id_js}, {json.dumps(label)}, {json.dumps(color)})"
                )
                raw = _eval_js(server, tool, js)
                try:
                    result = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    result = {"success": False, "count": 0, "ids": [], "error": raw}
            except Exception as e:
                result = {"success": False, "count": 0, "ids": [], "error": str(e)}

            results.append(
                {"step": i, "selector": selector, "label": label, **result}
            )
            if result.get("success"):
                highlighted += 1

        s.add(highlighted=highlighted, total=len(steps))
        return {
            "task": task,
            "total": len(steps),
            "highlighted": highlighted,
            "results": results,
        }
