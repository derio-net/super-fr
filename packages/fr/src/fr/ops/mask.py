"""Masking identity values out of a reason line (spec 2026-10-22-fr-ops R5).

A check's reason is its last stdout line, which a careless probe can fill with the
credential it ran as. Every identity value is masked whole, line by line and token by
token (tokens of 6+ characters), each in its raw, base64 and URL-encoded forms; and a
base64-looking run in the line is decoded and masked when it carries any of those
pieces, so a truncated or re-wrapped encoding of a secret is caught too.
"""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Iterable
from urllib.parse import quote, quote_plus

MASK = "***"
MIN_TOKEN = 6
_B64_RUN = re.compile(r"[A-Za-z0-9+/_-]{16,}={0,2}")


def _pieces(value: str) -> set[str]:
    lines = {line.strip() for line in value.splitlines()}
    tokens = {t for t in value.split() if len(t) >= MIN_TOKEN}
    return {p for p in ({value.strip()} | lines | tokens) if p}


def _forms(piece: str) -> set[str]:
    raw = piece.encode()
    encoded = {base64.b64encode(raw).decode(), base64.urlsafe_b64encode(raw).decode()}
    forms = {piece, quote(piece, safe=""), quote_plus(piece)}
    forms |= encoded | {e.rstrip("=") for e in encoded}
    return {f for f in forms if f == piece or len(f) >= MIN_TOKEN}


def _decodes_to_a_piece(run: str, pieces: set[str]) -> bool:
    body = run.rstrip("=")
    padded = body + "=" * (-len(body) % 4)
    for altchars in (None, b"-_"):
        try:
            decoded = base64.b64decode(padded, altchars=altchars, validate=False)
        except (binascii.Error, ValueError):
            continue
        if any(p.encode() in decoded for p in pieces if len(p) >= MIN_TOKEN):
            return True
    return False


def mask(line: str, secrets: Iterable[str]) -> str:
    """`line` with every form of every secret replaced by `***`."""
    pieces: set[str] = set()
    for secret in secrets:
        if secret:
            pieces |= _pieces(secret)
    if not pieces:
        return line
    for form in sorted({f for p in pieces for f in _forms(p)}, key=len, reverse=True):
        line = line.replace(form, MASK)
    return _B64_RUN.sub(
        lambda m: MASK if _decodes_to_a_piece(m.group(0), pieces) else m.group(0), line
    )


def looks_like_a_body(line: str, limit: int = 200) -> bool:
    """A reason line that is a response body rather than a status: JSON-shaped, or long."""
    stripped = line.strip()
    return stripped.startswith(("{", "[")) or len(stripped) > limit
