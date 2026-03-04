"""Integration smoke tests for the claude_util pack.

Exercises real filesystem access — no subprocess or ctx calls.
"""

from __future__ import annotations

import re

import pytest


UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


@pytest.mark.integration
@pytest.mark.tools
class TestSessionIdLive:
    def test_session_id_returns_uuid_shaped_string(self) -> None:
        """session_id() should return a UUID or an Error: string in live env."""
        from ottools.claude_util import session_id

        result = session_id()

        assert isinstance(result, str)
        # Either a valid UUID or a clear error string
        is_uuid = UUID_RE.match(result) is not None
        is_error = result.startswith("Error:")
        assert is_uuid or is_error, f"Unexpected result: {result!r}"

    def test_session_id_is_uuid_in_active_claude_session(self) -> None:
        """When run inside an active Claude Code session, session_id() returns a UUID."""
        from ottools.claude_util import session_id

        result = session_id()

        # In CI without Claude Code, this may return an error — skip if so
        if result.startswith("Error:"):
            pytest.skip(f"No active Claude Code session: {result}")

        assert UUID_RE.match(result), f"Not a UUID: {result!r}"
