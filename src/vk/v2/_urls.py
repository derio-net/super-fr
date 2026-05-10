"""Shared URL parsing helpers.

Single source for the gh issue URL pattern. Imported by `observe.py`
and `diff.py` so the regex lives in one place — drift between the two
parsers was the Family A bug class the v2 design exists to retire.
"""

from __future__ import annotations

import re

ISSUE_URL_RE = re.compile(r"^https://github\.com/([^/]+/[^/]+)/issues/(\d+)$")


def parse_issue_url(url: str) -> tuple[str, int]:
    """('https://github.com/owner/repo/issues/N') -> ('owner/repo', N)."""
    m = ISSUE_URL_RE.match(url)
    if not m:
        raise ValueError(f"not a github issue url: {url}")
    return m.group(1), int(m.group(2))
