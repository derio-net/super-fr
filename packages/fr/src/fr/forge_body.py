"""Name the usual reason a forge CLI printed a page where JSON belongs.

A forward-auth or SSO proxy in front of a forge answers `tea api` and `glab api`
with its login page. The CLI follows the redirect, so fr sees HTML on stdout
and a JSON decode error. This module is the one place that says so."""

from __future__ import annotations

import re

_REASON = (
    "an HTML body, not the forge's JSON: an SSO or forward-auth login page, "
    "most likely; exempt the instance's /api/ paths or use an internal URL"
)


def not_json_reason(out: str, stderr: str = "") -> str | None:
    """The named cause when *out* is an HTML page, else None."""
    if (out or "").lstrip().startswith("<") or "text/html" in (stderr or "").lower():
        return _REASON
    return None


def names_login_page(message: str) -> bool:
    """True when *message* already carries `not_json_reason`'s named cause."""
    return _REASON in message


# Control characters plus the bidi and format marks that reorder or hide text.
CONTROL = re.compile("[\x00-\x1f\x7f-\x9f\u200e\u200f\u202a-\u202e\u2066-\u2069]")

_READ_FAILURE_LIMIT = 300


def read_failure(url: str, exc: BaseException) -> str:
    """The one warning line for a PR whose state could not be read (adopt and push).

    The reason is the error's own first line, redacted and with control and bidi
    characters replaced, at most 300 characters, so a login-page error is named
    and nothing a forge echoed can hide text or carry a credential. `fr.debt` is
    imported here, not at module level: this module is a leaf the adapters import."""
    from fr.debt.render import redact

    def clean(text: str) -> str:
        return CONTROL.sub("?", redact(text))[:_READ_FAILURE_LIMIT]

    lines = str(exc).splitlines()
    reason = clean(lines[0] if lines else type(exc).__name__)
    # The url comes from the run cursor (forge-returned text): same treatment.
    return f"warning: could not read the state of PR {clean(url.splitlines()[0] if url else '')}: {reason}"
