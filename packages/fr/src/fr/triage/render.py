"""`render` — one self-contained, deterministic, safe HTML board (spec §3.G).

Follows `fr.acceptance.report`'s pattern: pure Python, CSS and JS as module
constants, `html.escape` on every forge-sourced string.
"""

from __future__ import annotations

import html
import re

_CODE = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def inline(text: str) -> str:
    """Escape first, then allow exactly `code` and **bold** (spec §3.D)."""
    out = _CODE.sub(r"<code>\1</code>", esc(text))
    return _BOLD.sub(r"<strong>\1</strong>", out)
