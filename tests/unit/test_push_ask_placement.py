"""`git.push: ask` finds an fr-debugging session's journal under every placement (review
pr1431-r9).

With no spec-driven run, `fr push` and `fr pr create` record the operator's approval in
the debug journal the branch added. Under quiet and stealth that journal lives at the
placement's feature root, never on the product branch, so it is found through the
resolver. Every repo is a local sandbox with bare remotes.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands.push_cmd import approval_journal
from fr.git_policy.ask import ApprovalJournal
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.placement import quiet, stealth
from typer.testing import CliRunner

from tests.unit.settings_repo import make_repo
from tests.unit.stealth_repo import make_tracking, stealth_home
from tests.unit.test_placement_quiet import QUIET, push_fr_branch

__all__ = ["stealth_home"]

SLUG = "2026-11-13-flaky-thing"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FR_REPO_ROOT", raising=False)
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    quiet._CACHE.clear()


def _journal(ws: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["journal", "add", "--scope", "debug", "--slug", SLUG, "--kind", "discovery",
         "--title", "the root cause", "--body", "x"],
        env={**os.environ, "FR_REPO_ROOT": str(ws)},
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def test_quiet_finds_the_debug_journal_on_fr(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    ws = HostWorktreeTarget(repo).up(profile=None, branch="fix/q").worktree
    _journal(ws)
    assert approval_journal(ws) == ApprovalJournal("debug", SLUG)


def test_stealth_finds_the_debug_journal_in_the_tracking_repo(tmp_path: Path) -> None:
    target = make_repo(tmp_path)
    track = make_tracking(tmp_path)
    ws = (
        HostWorktreeTarget(target)
        .up(profile=None, branch="fix/s", stealth=stealth.parse_ref(f"{track}@main"))
        .worktree
    )
    _journal(ws)
    assert approval_journal(ws) == ApprovalJournal("debug", SLUG)


def test_quiet_with_no_debug_journal_says_so(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    ws = HostWorktreeTarget(repo).up(profile=None, branch="fix/n").worktree
    found = approval_journal(ws)
    assert isinstance(found, str) and "added no debug journal" in found
