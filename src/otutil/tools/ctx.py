"""Smart context store for OneTool tool outputs.

TTL-expiring, BM25-indexed storage for large tool outputs.
Replace context-window saturation with targeted retrieval.

Tools:
    write    - Store content, get handle + preview (~1ms)
    read     - Paginated raw content, TOC, or metadata
    search   - BM25 section search with three-layer fallback
    grep     - Regex / fuzzy line search with context
    slice    - Extract by section number, heading, or line range
    toc      - Numbered section index with vocabulary hints
    ask      - Multi-question LLM query over stored content (optional)
    append   - Add content and rebuild index
    list     - All active handles
    inspect  - Detailed metadata for one handle
    stats    - Session storage metrics
    delete   - Remove one handle
    purge    - Delete handles (expired, all, or by filter) + compact DB
"""
from __future__ import annotations

# Pack for dot notation: ot_context.write() or ctx.write() (short alias)
pack = "ot_context"

# No external dependencies — uses stdlib sqlite3 only
__ot_requires__: dict[str, str] = {}

__all__ = [
    "append", "ask", "delete", "grep", "inspect", "list", "purge", "read",
    "search", "slice", "stats", "toc", "write",
]

from ot.ctx import (
    ctx_append as append,
)
from ot.ctx import (
    ctx_ask as ask,
)
from ot.ctx import (
    ctx_delete as delete,
)
from ot.ctx import (
    ctx_grep as grep,
)
from ot.ctx import (
    ctx_inspect as inspect,
)
from ot.ctx import (
    ctx_list as list,
)
from ot.ctx import (
    ctx_purge as purge,
)
from ot.ctx import (
    ctx_read as read,
)
from ot.ctx import (
    ctx_search as search,
)
from ot.ctx import (
    ctx_slice as slice,
)
from ot.ctx import (
    ctx_stats as stats,
)
from ot.ctx import (
    ctx_toc as toc,
)
from ot.ctx import (
    ctx_write as write,
)
