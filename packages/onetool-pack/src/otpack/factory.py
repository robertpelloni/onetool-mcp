"""Factory utilities for lazy client initialization.

Provides thread-safe lazy initialization patterns for API clients.

Example:
    from otpack import lazy_client

    # Define a client factory
    def create_my_client():
        from mylib import Client
        api_key = get_secret("MY_API_KEY")
        return Client(api_key=api_key)

    # Create a lazy-initialized getter
    get_client = lazy_client(create_my_client)

    # Use it anywhere - initialized once, thread-safe
    client = get_client()
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["LazyClient", "lazy_client"]

T = TypeVar("T")


def lazy_client(
    factory: Callable[[], T | None],
    *,
    allow_none: bool = False,
) -> Callable[[], T | None]:
    """Create a thread-safe lazy-initialized client getter.

    Wraps a factory function with double-checked locking to ensure
    the client is created exactly once, even under concurrent access.

    Args:
        factory: Callable that creates and returns the client instance
        allow_none: If True, cache None results. If False (default), retry
                   factory on each call when it returns None.

    Returns:
        A callable that returns the lazily-initialized client
    """
    client: T | None = None
    initialized = False
    lock = threading.Lock()

    def get_client() -> T | None:
        nonlocal client, initialized

        # Fast path: already initialized
        if initialized:
            return client

        # Slow path: acquire lock and initialize
        with lock:
            # Double-check after acquiring lock
            if initialized:
                return client

            result = factory()

            # Cache result if successful or allow_none is True
            if result is not None or allow_none:
                client = result
                initialized = True

            return result

    def reset() -> None:
        """Reset the cached client, forcing re-initialization on next call."""
        nonlocal client, initialized
        with lock:
            client = None
            initialized = False

    get_client.reset = reset  # type: ignore[attr-defined]

    return get_client


class LazyClient:
    """Class-based lazy client for more complex initialization patterns.

    Useful when you need to pass the factory as a method or need
    additional client management features.
    """

    def __init__(
        self,
        factory: Callable[[], T | None],
        *,
        allow_none: bool = False,
    ) -> None:
        """Initialize the lazy client wrapper.

        Args:
            factory: Callable that creates the client
            allow_none: If True, cache None results
        """
        self._factory = factory
        self._allow_none = allow_none
        self._client: T | None = None
        self._initialized = False
        self._lock = threading.Lock()

    def get(self) -> T | None:
        """Get the client, initializing if necessary.

        Returns:
            The client instance, or None if not available
        """
        if self._initialized:
            return self._client  # type: ignore[return-value]

        with self._lock:
            if self._initialized:
                return self._client

            result = self._factory()

            if result is not None or self._allow_none:
                self._client = result
                self._initialized = True

            return result  # type: ignore[return-value]

    def reset(self) -> None:
        """Reset the client, forcing re-initialization on next access."""
        with self._lock:
            self._client = None
            self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if the client has been initialized."""
        return self._initialized
