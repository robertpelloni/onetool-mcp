"""Shared fixtures for integration tests.

Loads API keys directly from project-root secrets.yaml.
Injects them into the runtime secret cache so tools get keys without
depending on the runtime secret resolver path resolution.

Also starts the Playwright MCP server connection (session-scoped) so that
whiteboard integration tests can run against a live browser.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from pathlib import Path

import pytest
import yaml

import ot.config.secrets as _secrets_module
from ot.config.loader import get_config, load_config
from ot.proxy.manager import get_proxy_manager

# tests/otdev/integration/tools/conftest.py → 5 parents to reach project root
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
_SECRETS_FILE = (
    _PROJECT_ROOT / "secrets.yaml"
    if (_PROJECT_ROOT / "secrets.yaml").exists()
    else _PROJECT_ROOT / ".onetool" / "secrets.yaml"
)

_secrets: dict[str, str] = {}
if _SECRETS_FILE.exists():
    with _SECRETS_FILE.open() as f:
        raw = yaml.safe_load(f) or {}
    _secrets = {k: str(v) for k, v in raw.items() if isinstance(k, str) and v is not None}


def get_test_secret(name: str) -> str | None:
    """Get a secret value for test skip checks.

    Args:
        name: Secret name (e.g., "CONTEXT7_API_KEY")

    Returns:
        Secret value or None if not found
    """
    return _secrets.get(name)


@pytest.fixture(autouse=True)
def _inject_secrets():
    """Inject test secrets into the runtime cache.

    Sets the module-level _secrets dict directly so all call sites
    (regardless of import style) resolve keys from secrets.yaml.
    """
    old = _secrets_module._secrets
    _secrets_module._secrets = _secrets
    yield
    _secrets_module._secrets = old


_TEST_CONFIG = _PROJECT_ROOT / "tests" / ".onetool" / "onetool.yaml"


@pytest.fixture(scope="session", autouse=True)
def _connect_playwright_proxy():
    """Start a background event loop and connect the proxy manager to Playwright.

    Session-scoped: runs once, stays connected for the entire test session.
    Fails the session immediately if the playwright server cannot connect.
    """
    # Initialize the global config singleton so proxy.connect can read env/secrets
    config = get_config(config_path=_TEST_CONFIG)
    if not config.servers:
        pytest.fail("No servers configured in test onetool.yaml — cannot run integration tests")

    proxy = get_proxy_manager()

    loop = asyncio.new_event_loop()
    ready = threading.Event()
    error: list[Exception] = []

    def _run_loop() -> None:
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(proxy.connect(config.servers))
        except Exception as exc:
            error.append(exc)
        finally:
            ready.set()
        # Keep the loop running so call_tool_sync / run_coroutine_threadsafe work
        loop.run_forever()

    thread = threading.Thread(target=_run_loop, daemon=True)
    thread.start()
    ready.wait(timeout=180)

    if error:
        pytest.fail(f"Playwright proxy connection failed: {error[0]}")
    if "playwright" not in proxy.servers:
        server_errors = proxy._errors  # noqa: SLF001
        pytest.fail(
            f"Playwright server not in proxy.servers after connect(). "
            f"Servers: {proxy.servers}, errors: {server_errors}"
        )

    yield

    # Teardown: shutdown proxy and stop the loop
    future = asyncio.run_coroutine_threadsafe(proxy.shutdown(), loop)
    with contextlib.suppress(Exception):
        future.result(timeout=10)
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)


__all__ = ["get_test_secret"]
