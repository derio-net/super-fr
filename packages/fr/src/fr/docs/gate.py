"""One evaluation of the docs-currency gate, shared by `fr docs check` and
`deliver`'s derived `docs` witness (spec 2026-11-11-docs-currency R9).

The callers differ only in how they choose the base: the command resolves
`--base` or the remote default branch (R6); `deliver` uses the same base as
its proportionality witness. Everything after that is here, once.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fr.docs.check import Finding, check
from fr.docs.load import DocsEnvError, changed_paths, load_pages, tracked_files
from fr.docs.model import DocsConfig, Page


@dataclass(frozen=True)
class Outcome:
    """`changed` is None when only the structural checks ran."""

    pages: list[Page]
    findings: list[Finding]
    changed: list[str] | None


def evaluate(root: Path, config: DocsConfig, base: str | None) -> Outcome:
    """Check `config`'s pages against the change from `base` (None: structure only).

    Raises `DocsEnvError` for anything that is not a finding: no git, an
    unusable base, or a config that selects no page.
    """
    tracked = tracked_files(root)
    pages, errors = load_pages(root, config, tracked)
    if not pages and not errors:
        # A config that selects no page is a typo, never "nothing owed".
        raise DocsEnvError(
            f".fr/docs.yaml selects no page: `pages` {config.pages!r} matches no tracked file"
        )
    changed = None if base is None else changed_paths(root, base)
    return Outcome(pages, check(pages, errors, tracked, changed, config.must_cover), changed)
