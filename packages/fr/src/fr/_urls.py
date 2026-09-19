"""Shared URL parsing helpers.

Single source for the tracking-issue URL pattern. Imported by `observe.py`
and `diff.py` so the regex lives in one place — drift between the two
parsers was the Family A bug class the v2 design exists to retire.

Covers all three supported backends' Issue URL shapes (see
docs/superpowers/specs/2026-07-09-multi-backend-git-host-adapters-design.md
§2): GitHub and Gitea both use `https://{host}/{repo}/issues/{n}`; GitLab
inserts a `-/` infix (`https://{host}/{repo}/-/issues/{n}`) and, since its
work-items migration, hands back `/-/work_items/{n}` for the very same Issue —
that is what `GET projects/:id/issues` reports as `web_url` (captured live
2026-09-19; gitlab.com behaves the same, so this is not a self-hosted or a
glab quirk). Both GitLab spellings are accepted: `fr` stores whatever URL the
API gave it, and `observe`/`diff`/`render` read that URL back, so rejecting
the shape GitLab actually returns made `fr apply` work exactly once per repo
and crash on every run after (gh-486). Its `{repo}`
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

# `work_items` is GitLab-only, but it is accepted with or without the `-/`
# infix for the same reason the infix itself is optional: this parser's job is
# to read back a URL some forge handed us, not to police which spellings a
# forge is allowed to emit.
_ISSUE_ROUTE = r"(?:issues|work_items)"

ISSUE_URL_RE = re.compile(rf"^https://([^/]+)/(.+?)(?:/-)?/{_ISSUE_ROUTE}/(\d+)$")

# Looser pattern for pulling just the issue number off the end of a URL or path.
# Used when we only care about the number (e.g. building a phase→issue map for
# the renderer) and don't want to fail loudly on an unexpected URL shape.
_ISSUE_NUM_RE = re.compile(rf"/(?:-/)?{_ISSUE_ROUTE}/(\d+)/?$")


def parse_issue_url(url: str) -> tuple[str, int]:
    """('https://{host}/owner/repo/issues/N') -> ('owner/repo', N).

    Also accepts GitLab's `.../-/issues/N` and `.../-/work_items/N` shapes —
    the latter is what GitLab's API returns for an Issue today (see module
    docstring).
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
