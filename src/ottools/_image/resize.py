"""In-memory image resize for model upload.

The original image bytes are never modified. Resize happens entirely in memory
and the resized bytes are used only for vision model uploads.
"""

from __future__ import annotations

import io
from typing import NamedTuple


class PreparedImage(NamedTuple):
    """Result of prepare_for_model."""

    model_bytes: bytes
    """PNG bytes ready for model upload (resized if necessary)."""

    original_dims: tuple[int, int]
    """Original (width, height) in pixels."""

    model_dims: tuple[int, int]
    """Model-upload (width, height) in pixels."""

    resized: bool
    """True if the image was resized to fit max_edge."""

    original_format: str
    """Detected source format (e.g. 'PNG', 'JPEG')."""


def prepare_for_model(raw_bytes: bytes, max_edge: int) -> PreparedImage:
    """Resize image in-memory (if needed) and encode to PNG for model upload.

    Preserves aspect ratio. The original ``raw_bytes`` are not modified.

    Args:
        raw_bytes: Original image bytes (any Pillow-supported format).
        max_edge: Maximum allowed longest edge in pixels. Images within this
            limit are encoded to PNG unchanged.

    Returns:
        PreparedImage with ``model_bytes`` (PNG), dimension info, and resize flag.
    """
    from PIL import Image

    img = Image.open(io.BytesIO(raw_bytes))
    original_format = img.format or "PNG"
    original_dims = (img.width, img.height)

    long_edge = max(img.width, img.height)
    if long_edge > max_edge:
        scale = max_edge / long_edge
        new_w = max(1, int(img.width * scale))
        new_h = max(1, int(img.height * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        model_dims: tuple[int, int] = (new_w, new_h)
        resized = True
    else:
        model_dims = original_dims
        resized = False

    # Normalise mode for clean PNG encoding
    if img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="PNG")

    return PreparedImage(
        model_bytes=buf.getvalue(),
        original_dims=original_dims,
        model_dims=model_dims,
        resized=resized,
        original_format=original_format,
    )
