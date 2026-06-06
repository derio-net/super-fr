"""Shared URL parsing helpers.

Single source for the gh issue URL pattern. Imported by `observe.py`
and `diff.py` so the regex lives in one place — drift between the two
parsers was the Family A bug class the v2 design exists to retire.
"""

from __future__ import annotations

import re

ISSUE_URL_RE = re.compile(r"^https://github\.com/([^/]+/[^/]+)/issues/(\d+)$")

# Looser pattern for pulling just the issue number off the end of a URL or path.
# Used when we only care about the number (e.g. building a phase→issue map for
# the renderer) and don't want to fail loudly on an unexpected URL shape.
_ISSUE_NUM_RE = re.compile(r"/issues/(\d+)/?$")


def parse_issue_url(url: str) -> tuple[str, int]:
    """('https://github.com/owner/repo/issues/N') -> ('owner/repo', N)."""
    m = ISSUE_URL_RE.match(url)
    if not m:
        raise ValueError(f"not a github issue url: {url}")
    return m.group(1), int(m.group(2))


def is_cross_repo_spec(spec: str) -> bool:
    """True iff `spec` uses the cross-repo `<owner>/<repo>:<path>` notation.

    Same-repo specs are plain repo-relative paths (no colon). A spec is
    cross-repo iff it contains a ':' AND the part before the first ':' looks
    like 'owner/repo' (contains a '/'). Single source for this check so apply's
    reachability gate and `fr plan self-review` agree on it (#248).
    """
    return ":" in spec and "/" in spec.split(":", 1)[0]


def issue_number(url: str | None) -> int | None:
    """Extract the trailing Issue number from a URL or path. None if absent."""
    if not url:
        return None
    m = _ISSUE_NUM_RE.search(url)
    return int(m.group(1)) if m else None
