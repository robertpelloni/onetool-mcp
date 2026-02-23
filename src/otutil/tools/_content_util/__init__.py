"""Shared content utilities for OneTool tools."""

from ._grep import grep_lines
from ._headings import HEADING_RE, build_toc, parse_headings
from ._slice import LINE_RANGE_RE, resolve_line_range, resolve_slice, selector_label

__all__ = [
    "HEADING_RE",
    "LINE_RANGE_RE",
    "build_toc",
    "grep_lines",
    "parse_headings",
    "resolve_line_range",
    "resolve_slice",
    "selector_label",
]
