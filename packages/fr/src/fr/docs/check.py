"""The pure docs-currency check (spec 2026-11-11-docs-currency R3, R4, R5).

No git and no filesystem: pages, tracked files and changed paths come in,
findings go out. `changed=None` runs only the structural checks (R4, R5).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fr.docs.globs import match
from fr.docs.model import Page, PageError


@dataclass(frozen=True)
class Finding:
    """One thing wrong: `kind` is stale | dead-glob | bad-page | uncovered."""

    kind: str
    page: str
    paths: tuple[str, ...]
    message: str


def check(
    pages: Sequence[Page],
    page_errors: Sequence[PageError],
    tracked: Sequence[str],
    changed: Sequence[str] | None,
    must_cover: Sequence[str],
) -> list[Finding]:
    """Findings for `pages` against the tracked tree and the changed paths."""
    out: list[Finding] = [
        Finding("bad-page", e.path, (), f"{e.path}: {e.message}") for e in page_errors
    ]
    for page in pages:
        for glob in page.covers:
            if not any(match(glob, t) for t in tracked):
                out.append(
                    Finding(
                        "dead-glob",
                        page.path,
                        (glob,),
                        f"{page.path}: `covers` glob {glob!r} matches no tracked file",
                    )
                )
    for pattern in must_cover:
        for path in (t for t in tracked if match(pattern, t)):
            if not any(match(g, path) for p in pages for g in p.covers):
                out.append(
                    Finding(
                        "uncovered",
                        "",
                        (path,),
                        f"{path} matches must_cover {pattern!r} but no page covers it",
                    )
                )
    out = _dedupe_uncovered(out)
    if changed is not None:
        changed_set = set(changed)
        for page in pages:
            if page.path in changed_set:
                continue
            hit = tuple(
                c for c in changed if c != page.path and any(match(g, c) for g in page.covers)
            )
            if hit:
                out.append(
                    Finding(
                        "stale",
                        page.path,
                        hit,
                        f"{page.path} covers changed paths but was not changed: " + ", ".join(hit),
                    )
                )
    return out


def _dedupe_uncovered(findings: list[Finding]) -> list[Finding]:
    """One `uncovered` finding per file, however many `must_cover` globs match it."""
    seen: set[str] = set()
    kept: list[Finding] = []
    for f in findings:
        if f.kind == "uncovered":
            if f.paths[0] in seen:
                continue
            seen.add(f.paths[0])
        kept.append(f)
    return kept
