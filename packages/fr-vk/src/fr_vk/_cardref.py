"""Consolidated VK card-title tag parsing and building.

Replaces 5+ independent regex copies across pr_state.py, workspaces.py,
and dispatch.py — the "Family A" duplicate-parser bug class the v2 design
already retired once for GitHub issue URLs (`fr._urls`); this is the same
fix applied to the VK card-title convention. See docs/superpowers/specs/
2026-07-09-multi-backend-git-host-adapters-design.md §2.

The wire format stays `"{tag}#{n}: [{repo}]"` — `tag` resolves per backend
via `TAG_FOR_BACKEND` rather than a wider rename, so an operator scanning
the VK board can tell which host a card belongs to, and existing GitHub
cards (`gh#N: [owner/repo]`) keep parsing unchanged (backward
compatibility for cards already on production VK boards is load-bearing,
not optional).
"""

from __future__ import annotations

import re

from fr._hosts import HostBackend

TAG_FOR_BACKEND: dict[HostBackend, str] = {"github": "gh", "gitlab": "gl", "gitea": "gt"}
BACKEND_FOR_TAG: dict[str, HostBackend] = {v: k for k, v in TAG_FOR_BACKEND.items()}

# Anchored at the start only — a free-text suffix (or a second bracketed
# token an operator typed) must not break the parse, matching the original
# per-file regexes' own tolerance (see _DONE_TITLE_RE's docstring in the
# pre-consolidation pr_state.py).
_CARD_TITLE_RE = re.compile(r"^(?P<tag>\w+)#(?P<number>\d+):\s*\[(?P<repo>[\w./-]+)\]")


def parse_card_title(title: str) -> tuple[str, str, int] | None:
    """Return `(backend_tag, repo, number)` from a `"{tag}#{n}: [{repo}]"`
    card title, or `None` if it doesn't match. `backend_tag` is returned
    as-is (not resolved through `BACKEND_FOR_TAG`) so callers that only
    need to compare tags (e.g. a mismatch guard) don't pay for a lookup
    they don't need; callers that need the `HostBackend` enum value look
    it up via `BACKEND_FOR_TAG[tag]`.
    """
    m = _CARD_TITLE_RE.match(title)
    if not m:
        return None
    return m.group("tag"), m.group("repo"), int(m.group("number"))


def build_card_title(backend: HostBackend, repo: str, number: int) -> str:
    """Render the canonical `"{tag}#{n}: [{repo}]"` card title for `backend`."""
    tag = TAG_FOR_BACKEND.get(backend, "gh")
    return f"{tag}#{number}: [{repo}]"
