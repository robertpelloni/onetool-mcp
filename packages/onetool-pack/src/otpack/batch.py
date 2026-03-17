"""Batch processing utilities for OneTool packs.

Provides concurrent execution helpers for tools that process multiple items.

Example:
    from otpack import batch_execute, normalize_items

    # Process URLs concurrently
    def fetch_one(url: str, label: str) -> tuple[str, str]:
        result = fetch(url)
        return label, result

    urls = ["https://a.com", ("https://b.com", "Custom Label")]
    normalized = normalize_items(urls)  # [(url, label), ...]
    results = batch_execute(fetch_one, normalized, max_workers=5)
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["batch_execute", "format_batch_results", "normalize_items"]

T = TypeVar("T")
R = TypeVar("R")


def normalize_items(
    items: list[str] | list[tuple[str, str]] | list[str | tuple[str, str]],
) -> list[tuple[str, str]]:
    """Normalize a list of items to (value, label) tuples.

    Accepts items as either:
    - A string (used as both value and label)
    - A tuple of (value, label)

    Args:
        items: List of items as strings or (value, label) tuples

    Returns:
        List of (value, label) tuples
    """
    normalized: list[tuple[str, str]] = []
    for item in items:
        if isinstance(item, str):
            normalized.append((item, item))
        else:
            normalized.append(item)
    return normalized


def batch_execute(
    func: Callable[[str, str], tuple[str, R]],
    items: list[tuple[str, str]],
    *,
    max_workers: int | None = None,
    preserve_order: bool = True,
) -> dict[str, R]:
    """Execute a function concurrently on multiple items.

    Runs the provided function on each item using a ThreadPoolExecutor.
    The function receives (value, label) and must return (label, result).

    Args:
        func: Function taking (value: str, label: str) and returning (label, result)
        items: List of (value, label) tuples (use normalize_items to prepare)
        max_workers: Maximum concurrent workers. Defaults to len(items) (up to 10)
        preserve_order: If True (default), results maintain input order

    Returns:
        Dict mapping labels to results
    """
    if not items:
        return {}

    if max_workers is None:
        max_workers = min(len(items), 10)

    results: dict[str, R] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(func, value, label): label for value, label in items
        }
        for future in as_completed(futures):
            label, result = future.result()
            results[label] = result

    if preserve_order:
        # Rebuild dict in original order
        ordered: dict[str, R] = {}
        for _, label in items:
            if label in results:
                ordered[label] = results[label]
        return ordered

    return results


def format_batch_results(
    results: dict[str, Any],
    items: list[tuple[str, str]],
    separator: str = "===",
) -> str:
    """Format batch results as labeled sections.

    Creates a formatted string with section headers for each result,
    preserving the original order from the items list.

    Args:
        results: Dict mapping labels to result strings
        items: Original list of (value, label) tuples for ordering
        separator: Section separator character(s) (default: "===")

    Returns:
        Formatted string with sections like "=== Label ===\\n{content}"
    """
    sections = []
    for _, label in items:
        if label in results:
            content = results[label]
            sections.append(f"{separator} {label} {separator}\n{content}")
    return "\n\n".join(sections)
