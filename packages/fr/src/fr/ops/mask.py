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
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from urllib.parse import quote, quote_plus

MASK = "***"
MIN_TOKEN = 6
REASON_MAX = 200
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


def passthrough_values(names: Sequence[str], environ: Mapping[str, str] | None = None) -> list[str]:
    """The values `env_passthrough` hands a probe, as secrets to mask. A value under
    `MIN_TOKEN` characters (`DEBUG=1`) is not one: masking it would mask every `1`."""
    env = os.environ if environ is None else environ
    return [v for n in names if len(v := env.get(n, "").strip()) >= MIN_TOKEN]


def sanitise_reason(line: str, secrets: Iterable[str], *, typed: bool = False) -> str:
    """THE one sanitiser for an op reason that is printed or recorded (R5, R7): every
    secret (identity and `env_passthrough` values) masked, whitespace collapsed to one
    line, and `""` for a line that looks like a response body, whoever the probe ran
    as; the caller then reports only the exit code. A `typed` reason (an operator's
    attest note, not a probe's output) is judged by its length alone (p3-r8)."""
    line = " ".join(mask(line, secrets).split())
    if typed:
        return "" if len(line) > REASON_MAX else line
    return "" if looks_like_a_body(line, REASON_MAX) else line


OUTPUT_LINES = 40
OUTPUT_LINE_MAX = 200
EVIDENCE_LINES = 3
EVIDENCE_MAX = 300


def last_line(out: str) -> str:
    """The last non-blank line of a probe's stdout, stripped: the line a reason used."""
    lines = [line for line in out.splitlines() if line.strip()]
    return lines[-1].strip() if lines else ""


def clip_output(out: str, secrets: Iterable[str]) -> str:
    """A checked probe's output for the screen: the last `OUTPUT_LINES` lines, secrets
    masked, each line clipped to `OUTPUT_LINE_MAX` characters."""
    lines = mask(out.rstrip(), secrets).splitlines()[-OUTPUT_LINES:]
    return "\n".join(line.rstrip()[:OUTPUT_LINE_MAX] for line in lines).strip("\n")


def evidence_lines(out: str, secrets: Iterable[str]) -> str:
    """The recordable evidence: the last `EVIDENCE_LINES` status lines of `out`, each
    through the reason sanitiser's own rules (secrets masked, whitespace collapsed, a
    body-shaped or over-`OUTPUT_LINE_MAX` line dropped — review p2-r1, p2-r2), joined
    with `; ` and clipped to `EVIDENCE_MAX` characters. The only part of a probe's
    output ever committed, so a JSON body or a token a server printed never is; `""`
    when no status line is left (the caller then records "no output")."""
    secrets = list(secrets)
    kept = [" ".join(mask(line, secrets).split()) for line in _status_lines(out)]
    kept = [line for line in kept if line and not looks_like_a_body(line, OUTPUT_LINE_MAX)]
    return "; ".join(kept[-EVIDENCE_LINES:])[:EVIDENCE_MAX]


_MEMBER = re.compile(r"""^\s*(?:"[^"]*"|'[^']*')\s*:""")
"""A JSON/YAML member line (`"token": …`), the inside of a pretty-printed body."""


def _status_lines(out: str) -> list[str]:
    """*out*'s lines with every body removed as a BLOCK, not line by line (security
    review): a line opening `{`/`[` starts a body that runs until its brackets balance,
    so the members of an indented, multi-line JSON document never survive as lines of
    their own; a stray member line or a lone closer is dropped too."""
    kept: list[str] = []
    depth = 0
    for line in out.splitlines():
        stripped = line.strip()
        if depth == 0 and not stripped.startswith(("{", "[")):
            if not _MEMBER.match(stripped) and stripped not in ("}", "]", "},", "],"):
                kept.append(line)
            continue
        depth = max(0, depth + _bracket_delta(stripped))
    return kept


def _bracket_delta(line: str) -> int:
    """Net `{`/`[` minus `}`/`]` on *line*, ignoring brackets inside double-quoted strings."""
    delta, quoted, escaped = 0, False, False
    for ch in line:
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == '"':
            quoted = not quoted
        elif not quoted and ch in "{[":
            delta += 1
        elif not quoted and ch in "}]":
            delta -= 1
    return delta
