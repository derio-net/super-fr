"""Which issue an owed entry's `filed_as` names (spec 2026-11-15
owed-archive-side-effects §A).

`fr journal resolve` and the PR body's `## Owed actions discharged` section
both read `filed_as` through `own_issue`, so the issue resolve would close and
the issue the body closes at merge are always the same one.
"""

from __future__ import annotations

import re
from pathlib import Path

_SHORT_REF = re.compile(r"^#([0-9]+)$")
_LONG_REF = re.compile(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([0-9]+)$")
_URL_PATH = re.compile(
    r"^/([A-Za-z0-9_.][A-Za-z0-9_.-]*/[A-Za-z0-9_.-]+)/(?:-/)?issues/([0-9]+)/?$"
)


def shown(ref: str) -> str:
    """`ref` safe to echo (review p3-r5): printable ASCII as is, else its repr."""
    return ref if ref.isascii() and ref.isprintable() else repr(ref)


def own_issue(root: Path, ref: str, own: str) -> tuple[str, int] | str:
    """`(owner/repo, number)` when `filed_as` names an issue in `own` — THIS
    repo, from `owed_identity` (the origin remote) — else the reason it does
    not. `filed_as` comes from a committed journal, so it is untrusted: a ref
    naming another owner/repo, or a URL on another host or repo, is never acted
    on. The number is ASCII digits."""
    from urllib.parse import urlparse

    from fr import _hosts

    if (m := _SHORT_REF.match(ref)) is not None:
        repo, number = own, int(m.group(1))
    elif (m := _LONG_REF.match(ref)) is not None:
        repo, number = m.group(1), int(m.group(2))
    elif ref.startswith(("http://", "https://")):
        url = urlparse(ref)
        origin = _hosts.origin_hostname(root)
        host = (url.hostname or "").lower()
        if not origin or host != origin.lower():
            return (
                f"{shown(ref)} is on {shown(host) or 'no host'}, not this repo's forge "
                f"({origin or 'unknown'})"
            )
        if (m := _URL_PATH.match(url.path)) is None:
            return f"{shown(ref)} is not an issue URL"
        repo, number = m.group(1), int(m.group(2))
    else:
        return f"{shown(ref)} is not an issue reference"
    if repo.lower() != own.lower():
        return f"{shown(ref)} names {shown(repo)}, not this repo ({own})"
    return own, number


def discharge_travels(root: Path) -> bool:
    """Whether a discharge committed here reaches the forge with the branch's PR:
    true when fr's journals live in the product checkout (`placement: repo`). Under
    quiet and stealth the artifact root is outside it, so a discharge commit never
    travels with the PR: `fr journal resolve` closes the owed issue at once, and the
    PR body's `## Owed actions discharged` section and `deliver`'s check for it do
    not apply (spec 2026-11-15-owed-archive-side-effects R15)."""
    from fr.artifacts.paths import artifact_root

    return artifact_root(root).resolve() == root.resolve()
