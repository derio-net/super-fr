"""`fr debt archive-pr` with the REAL `fr archive` subprocess (phase 4 review p4-r9),
and the failure paths that must leave the checkout as they found it (p4-r5)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import debt_cmd
from fr.debt import sweep
from fr.debt.model import ArchivablePlan, DebtReport, PlanDebt
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient, FakeGhError
from tests.unit.test_archive_branch import _base, _commit, _plan

runner = CliRunner()
SLUG = "derio-net/widgets"


def _git(cwd: Path, *a: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *a], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    repo = _base(tmp_path)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _plan(repo, "2026-01-01-old", ticked=True)
    _commit(repo, "plan")
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "remote", "set-head", "origin", "main")
    bare = tmp_path / "origin.git"
    _git(repo, "remote", "set-url", "origin", f"https://github.com/{SLUG}.git")
    _git(repo, "config", f"url.{bare}.insteadOf", f"https://github.com/{SLUG}.git")
    gh = FakeGhClient()
    report = DebtReport(
        plans=PlanDebt(
            archivable=(ArchivablePlan(name="2026-01-01-old", command="x", age_days=40),)
        ),
        stale_days=14,
    )
    monkeypatch.setenv("VK_REPO_ROOT", str(repo))
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    monkeypatch.delenv("FR_DEBT_TOKEN", raising=False)
    monkeypatch.setattr(debt_cmd, "_client", lambda root: gh)
    monkeypatch.setattr(debt_cmd, "_compute", lambda root, c, slug, days: report)
    return {"gh": gh, "repo": repo, "bare": bare}


def _calls(gh: FakeGhClient, name: str) -> list[dict]:
    return [c for n, c in gh.calls if n == name]


def test_the_real_fr_archive_moves_the_plan_and_the_sweep_opens_a_draft_pr(world: dict) -> None:
    r = runner.invoke(app, ["debt", "archive-pr", "--yes"])
    assert r.exit_code == 0, r.output
    (pr,) = _calls(world["gh"], "create_pr")
    assert pr["draft"] is True and "`2026-01-01-old`" in pr["body"]
    tree = _git(world["bare"], "ls-tree", "-r", "--name-only", sweep.BRANCH)
    assert "docs/superpowers/implemented/plans/2026-01-01-old/_meta.yaml" in tree
    assert "docs/superpowers/plans/2026-01-01-old/_meta.yaml" not in tree
    assert _git(world["repo"], "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_a_failed_archive_leaves_nothing_staged_or_untracked(
    world: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo: Path = world["repo"]

    def half_done(root: Path, name: str, env: dict) -> tuple[bool, str]:
        _git(root, "mv", f"docs/superpowers/plans/{name}", f"docs/superpowers/plans/{name}-x")
        (root / "docs" / "stray.md").write_text("left behind\n")
        return False, "boom"

    monkeypatch.setattr(debt_cmd, "_archive_one", half_done)
    r = runner.invoke(app, ["debt", "archive-pr", "--yes"])
    assert r.exit_code == 0, r.output
    assert _git(repo, "status", "--porcelain", "--untracked-files=all") == ""
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert not (repo / "docs" / "stray.md").exists()
    assert _calls(world["gh"], "create_pr") == []


def test_an_untracked_file_under_docs_is_refused_at_entry(world: dict) -> None:
    (world["repo"] / "docs" / "scratch.md").write_text("mine\n")
    r = runner.invoke(app, ["debt", "archive-pr", "--yes"])
    assert r.exit_code == 1 and "uncommitted" in r.output
    assert (world["repo"] / "docs" / "scratch.md").read_text() == "mine\n"


def test_a_refused_push_names_its_own_remedy(world: dict) -> None:
    _git(world["repo"], "remote", "set-url", "--push", "origin", "/nonexistent/none.git")
    _git(world["repo"], "config", "--unset", f"url.{world['bare']}.insteadOf")
    r = runner.invoke(app, ["debt", "archive-pr", "--yes"])
    assert r.exit_code == 0, r.output
    assert "could not push" in r.output and "contents:write" in r.output
    assert "Allow GitHub Actions" not in r.output
    assert _calls(world["gh"], "create_pr") == []


def test_only_a_permission_refusal_gets_the_actions_setting_remedy(world: dict) -> None:
    def refuse(*a: object, **k: object) -> None:
        raise FakeGhError(
            "HTTP 403: GitHub Actions is not permitted to create or approve pull requests"
        )

    world["gh"].create_pr = refuse
    r = runner.invoke(app, ["debt", "archive-pr", "--yes"])
    assert "Allow GitHub Actions" in r.output and "FR_DEBT_TOKEN" in r.output


def test_any_other_pr_error_gets_the_generic_category(world: dict) -> None:
    def fail(*a: object, **k: object) -> None:
        raise FakeGhError("HTTP 500: upstream exploded")

    world["gh"].create_pr = fail
    r = runner.invoke(app, ["debt", "archive-pr", "--yes"])
    assert r.exit_code == 0
    assert "forge error" in r.output and "Allow GitHub Actions" not in r.output


def test_held_tolerates_a_missing_plan_and_the_fence_cannot_be_closed(tmp_path: Path) -> None:
    assert debt_cmd._held(tmp_path, "no-such-plan") == []
    plan = ArchivablePlan(name="p", command="x", age_days=30)
    s = sweep.Sweep(archived=[plan], held=[(plan, ["why", "    ``` injected"])])
    body = sweep.pr_body(s, stale_days=14, own_token=True)
    assert body.count("```") == 2  # only the fence the renderer opened and closed


def test_bidi_and_format_characters_are_stripped_from_echoed_text() -> None:
    assert debt_cmd._clean("a‮b⁦c‏d‎") == "a?b?c?d?"
