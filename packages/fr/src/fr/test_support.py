"""Test-support assertions phase executors reach for (methodology restoration).

`assert_no_repo_mutation` is the ready-made answer to the #464 failure: a
draft test needing a git repo in a particular state ran `git rm --cached`
and `git commit` against the REAL checkout instead of a sandbox, and the
suite reported green throughout. Tests that need a repo sandbox it and wrap
the block in this assertion — drift fails loud, naming the paths.

`build_plan_journal` (bounded-executor-handoff, phase 1) is the measurement
harness's walking skeleton: it writes a synthetic plan journal through
`fr.journal.model.append_journal_entry` — the SAME writer `fr journal add`
calls — so a fixture built with it is a capture of the real serializer's
output, never a hand-rolled markdown guess that can drift from the format.

Deliberately light on dependencies: `fr.journal.model` needs pydantic (a core
dependency already, not the CLI stack), but pulls in neither `typer` nor
`rich`, so generated tests importing this module still avoid the CLI stack.
"""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fr.journal.model import JournalEntry, append_journal_entry, journal_path

__all__ = ["assert_no_repo_mutation", "build_plan_journal"]

GIT_TIMEOUT_SECONDS = 30.0
"""Mirrors `fr.artifacts.commit.GIT_TIMEOUT_SECONDS`: a git that never
returns (dead mount, credential prompt) must fail loud, never wedge."""


def _porcelain(repo_root: Path) -> str:
    """`git status --porcelain` for `repo_root`, or a loud failure."""
    try:
        done = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as e:
        raise AssertionError(
            f"`git status --porcelain` in {repo_root} did not finish within "
            f"{GIT_TIMEOUT_SECONDS:g}s — refusing to assert on an unreadable repo"
        ) from e
    if done.returncode != 0:
        raise AssertionError(
            f"`git status --porcelain` in {repo_root} failed: {done.stderr.strip()}"
        )
    return done.stdout


@contextmanager
def assert_no_repo_mutation(repo_root: Path) -> Iterator[None]:
    """Fail loud if the block changes `repo_root`'s git state.

    Compares full porcelain (tracked AND untracked): scratch files belong in
    `tmp_path`, not in the repo under test — a stray file left behind is
    drift too. The diff names the paths, so the failure points at the
    mutation instead of merely reporting "green but dirty".
    """
    before = _porcelain(repo_root)
    yield
    after = _porcelain(repo_root)
    if after != before:
        raise AssertionError(
            f"test mutated the repo under test ({repo_root}):\n"
            f"--- before\n{before}--- after\n{after}"
            "Sandbox the repo (a scratch clone or worktree) instead of "
            "operating on the real checkout."
        )


def _default_entry_id(entry: dict[str, Any], slug: str, index: int) -> str:
    """A collision-free default id for a fixture entry.

    Deliberately NOT a copy of `fr journal add`'s derivation
    (`sha1(kind|scope|slug|title|body)`): that one is content-addressed, which
    is right for the CLI — re-adding an identical entry is idempotent — and
    wrong for a fixture builder, whose whole job includes emitting N entries
    that differ only in `phase` or `state`. Under the CLI's rule those collide,
    `parse_journal` then rejects the file for duplicate ids, and the failure
    surfaces far from its cause. The entry's position disambiguates instead.
    """
    kind = entry["kind"]
    title = entry["title"]
    body = entry.get("body", "")
    seed = f"{kind}|plan|{slug}|{index}|{title}|{body}"
    return hashlib.sha1(seed.encode()).hexdigest()[:12]


def build_plan_journal(repo_root: Path, slug: str, entries: list[dict[str, Any]]) -> Path:
    """Write a synthetic plan journal at `repo_root` and return its path.

    `entries` uses `fr journal add`'s own vocabulary — dicts of
    `{kind, title, body, phase, state, id, resolves}` — and each is written
    through `append_journal_entry`, the same writer `fr journal add` and
    `fr journal resolve` call. The WRITER is shared; the default-id derivation
    deliberately is not (see `_default_entry_id`), and unlike the CLI this
    builder does not refuse a `resolves` pointing at an absent finding — a
    fixture may legitimately need that shape. A test that needs a plan journal in a
    particular shape (e.g. to exercise `compose_handoff`) builds one this way
    rather than formatting Markdown by hand, so the fixture cannot drift from
    what the real serializer produces.
    """
    path = journal_path(repo_root, "plan", slug)
    seen: set[str] = set()
    for index, e in enumerate(entries):
        eid = e.get("id") or _default_entry_id(e, slug, index)
        if eid in seen:
            raise ValueError(
                f"build_plan_journal: duplicate entry id {eid!r} at index {index}. "
                "parse_journal refuses a journal with duplicate ids, so writing "
                "one would fail later and elsewhere; give the entry an explicit "
                "distinct `id`."
            )
        seen.add(eid)
        entry = JournalEntry(
            kind=e["kind"],
            scope="plan",
            id=eid,
            created=e.get("created", "2026-01-01T00:00:00"),
            phase=e.get("phase"),
            title=e["title"],
            body=e.get("body", ""),
            state=e.get("state"),
            resolves=e.get("resolves"),
        )
        append_journal_entry(path, slug, entry)
    return path
