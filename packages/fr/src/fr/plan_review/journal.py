"""Journal reads for the plan self-review and the refactor gate."""

from __future__ import annotations

from pathlib import Path

from fr._urls import is_cross_repo_spec
from fr.journal.model import JournalEntry, JournalScope
from fr.parser import Plan


def journal_entries(repo_root: Path, scope: JournalScope, slug: str) -> list[JournalEntry]:
    """The entries of the *scope* journal *slug*, read-resolved (active else archived,
    like `render`/`check`). A missing or unparseable journal holds no entries: its own
    `fr journal check` owns malformed files. The one journal read of self-review and of
    the refactor gate (spec 2026-11-27-plan-ops-split R3)."""
    from fr.journal.model import JournalParseError, parse_journal, resolve_journal_read_path

    path = resolve_journal_read_path(repo_root, scope, slug)
    if not path.is_file():
        return []
    try:
        return parse_journal(path.read_text())
    except JournalParseError:
        return []


def _spec_journal_slug(plan: Plan) -> str | None:
    """The slug of the plan's same-repo spec journal, or None (no repo, no
    spec, a cross-repo spec — whose journal lives in its own repo — or a
    spec ref that is not a `.md` path)."""
    from fr.journal.model import spec_journal_slug

    spec = plan.meta.spec
    if plan.repo_root is None or not spec or spec in ("none", "null", "—", "-"):
        return None
    if is_cross_repo_spec(spec):
        return None
    stem = spec.rsplit("/", 1)[-1]
    if not stem.endswith(".md"):
        return None
    return spec_journal_slug(stem[: -len(".md")])


def _spec_journal_entries(plan: Plan) -> list[JournalEntry]:
    """The plan's spec-journal entries, read-resolved (active else archived,
    like `render`/`check`: a decision outlives the spec it was logged
    against). A missing or unparseable journal holds no entries — its own
    `fr journal check` owns malformed files. Shared by the skeleton override
    and the phase-split decisions, so the two read the journal one way."""
    slug = _spec_journal_slug(plan)
    if slug is None or plan.repo_root is None:
        return []
    return journal_entries(plan.repo_root, "spec", slug)
