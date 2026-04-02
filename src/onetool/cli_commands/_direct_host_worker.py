"""HTTP execution host worker process — launched by `onetool direct start`.

Invoked as: python -m onetool.cli_commands._direct_host_worker --config ... --port N --host H
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--secrets", type=Path, default=None)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    import ot.logging  # noqa: F401 — removes loguru's default stderr handler

    if args.config is not None:
        try:
            from ot.config.loader import get_config
            get_config(args.config, secrets_path=args.secrets)
        except Exception as e:
            print(f"Config error: {e}", file=sys.stderr)
            sys.exit(2)

    import uvicorn

    # Pre-warm tool registry so the first request is served from a warm cache
    try:
        from ot.executor.tool_loader import load_tool_registry
        load_tool_registry()
    except Exception as e:
        print(f"Warning: tool pre-warm failed: {e}", file=sys.stderr)

    from ot.direct_host import create_app
    app = create_app()

    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    except OSError as e:
        if "address already in use" in str(e).lower():
            print(f"Port {args.port} is already in use", file=sys.stderr)
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
