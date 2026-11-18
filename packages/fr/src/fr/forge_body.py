"""Name the usual reason a forge CLI printed a page where JSON belongs.

A forward-auth or SSO proxy in front of a forge answers `tea api` and `glab api`
with its login page. The CLI follows the redirect, so fr sees HTML on stdout
and a JSON decode error. This module is the one place that says so."""

from __future__ import annotations

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
