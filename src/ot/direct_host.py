"""HTTP execution host for `onetool direct`.

Exposes a single endpoint: POST /run
    Request:  {"command": "..."}
    Response: {"result": "...", "success": true|false}

Execution errors return HTTP 200 with success=false (not 500).
"""

from __future__ import annotations

from typing import Any


def create_app() -> Any:
    """Build and return the Starlette ASGI app."""
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def run_endpoint(request: Any) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"result": "invalid JSON body", "success": False}, status_code=400)

        command = body.get("command", "")
        if not command:
            return JSONResponse({"result": "'command' field is empty", "success": False}, status_code=400)

        from ot.executor.runner import execute_command, prepare_command
        from ot.utils import sanitize_output

        prepared = prepare_command(command)
        if prepared.error:
            return JSONResponse({"result": f"Error: {prepared.error}", "success": False})

        result = await execute_command(command, prepared_code=prepared.code, skip_validation=True)
        text = sanitize_output(result.result, enabled=result.should_sanitize, fmt=result.format)
        return JSONResponse({"result": text, "success": result.success})

    return Starlette(routes=[Route("/run", run_endpoint, methods=["POST"])])
