"""Shared URL parsing helpers.

Single source for the tracking-issue URL pattern. Imported by `observe.py`
and `diff.py` so the regex lives in one place — drift between the two
parsers was the Family A bug class the v2 design exists to retire.

Covers all three supported backends' Issue URL shapes (see
docs/superpowers/specs/2026-07-09-multi-backend-git-host-adapters-design.md
§2): GitHub and Gitea both use `https://{host}/{repo}/issues/{n}`; GitLab
inserts a `-/` infix (`https://{host}/{repo}/-/issues/{n}`) and its `{repo}`
may itself contain nested subgroups (`group/subgroup/proj`), so the repo
capture is a LAZY `.+?` — greedily matching as little as possible and
expanding only until the mandatory `/issues/{n}$` (optionally `/-`-prefixed)
suffix matches — rather than a fixed two-segment `[^/]+/[^/]+`. A greedy
repo capture is ambiguous here: for a GitLab URL, `.+` would first try
swallowing the `-` into the repo name itself (since `(?:/-)?` can also
match empty), landing on the wrong, longer split. Lazy backtracking finds
the correct (shortest, leftmost) split in one pass instead. The host itself
is captured but discarded — no consumer needs it; backend identity is
resolved separately via `fr._hosts.detect_backend`.
"""

from __future__ import annotations

import re

ISSUE_URL_RE = re.compile(r"^https://([^/]+)/(.+?)(?:/-)?/issues/(\d+)$")

# Looser pattern for pulling just the issue number off the end of a URL or path.
# Used when we only care about the number (e.g. building a phase→issue map for
# the renderer) and don't want to fail loudly on an unexpected URL shape.
_ISSUE_NUM_RE = re.compile(r"/(?:-/)?issues/(\d+)/?$")


def parse_issue_url(url: str) -> tuple[str, int]:
    """('https://{host}/owner/repo/issues/N') -> ('owner/repo', N).

    Also accepts GitLab's `.../-/issues/N` shape (see module docstring).
    """
    m = ISSUE_URL_RE.match(url)
    if not m:
        raise ValueError(f"not a tracking issue url: {url}")
    return m.group(2), int(m.group(3))


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
