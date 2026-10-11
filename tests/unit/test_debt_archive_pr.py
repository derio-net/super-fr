"""`fr debt archive-pr` (spec 2026-10-11-debt-engine R12) on a real git fixture, fake forge."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import debt_cmd
from fr.debt import sweep
from fr.debt.model import ArchivablePlan, DebtReport, PlanDebt
from fr.ghclient import UnsupportedForgeOperation
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient, FakeGhError

runner = CliRunner()
SLUG = "derio-net/widgets"


def _git(cwd: Path, *a: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *a], check=True, capture_output=True, text=True
    ).stdout.strip()


def _report(*plans: tuple[str, int | None]) -> DebtReport:
    arch = tuple(
        ArchivablePlan(name=n, command=f"fr archive docs/superpowers/plans/{n}", age_days=a)
        for n, a in plans
    )
    return DebtReport(plans=PlanDebt(archivable=arch), stale_days=14)


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(bare), str(work)], check=True)
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "t")
    for n in ("old-plan", "held-plan", "young-plan"):
        d = work / "docs/superpowers/plans" / n
        d.mkdir(parents=True)
        (d / "_meta.yaml").write_text("x: 1\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "plans")
    _git(work, "push", "-q", "origin", "main")
    _git(work, "remote", "set-head", "origin", "main")
    _git(work, "remote", "set-url", "origin", f"https://github.com/{SLUG}.git")
    _git(work, "config", f"url.{bare}.insteadOf", f"https://github.com/{SLUG}.git")
    gh = FakeGhClient()
    box = {"report": _report(("old-plan", 30), ("held-plan", 30), ("young-plan", 3), ("odd", None))}
    monkeypatch.setenv("VK_REPO_ROOT", str(work))
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    monkeypatch.delenv("FR_DEBT_TOKEN", raising=False)
    monkeypatch.setattr(debt_cmd, "_client", lambda root: gh)
    monkeypatch.setattr(debt_cmd, "_compute", lambda root, c, slug, days: box["report"])
    monkeypatch.setattr(
        debt_cmd,
        "_held",
        lambda root, n: ["x: Test Plan step(s) 2 missing", "    cmd"] if n == "held-plan" else [],
    )

    def archive(root: Path, name: str, env: dict) -> tuple[bool, str]:
        dst = root / "docs/superpowers/implemented/plans"
        dst.mkdir(parents=True, exist_ok=True)
        _git(
            root,
            "mv",
            f"docs/superpowers/plans/{name}",
            f"docs/superpowers/implemented/plans/{name}",
        )
        return True, ""

    monkeypatch.setattr(debt_cmd, "_archive_one", archive)
    return {"gh": gh, "work": work, "bare": bare, "box": box}


def _calls(gh: FakeGhClient, name: str) -> list[dict]:
    return [c for n, c in gh.calls if n == name]


def test_selection_has_the_merge_age_floor_and_skips_unknown_age() -> None:
    chosen = sweep.select(_report(("a", 30), ("b", 14), ("c", 15), ("d", None)))
    assert [p.name for p in chosen] == ["a", "c"]


def test_preview_pushes_and_opens_nothing(world: dict) -> None:
    r = runner.invoke(app, ["debt", "archive-pr"])
    assert r.exit_code == 0, r.output
    assert (
        "archive: old-plan" in r.output
        and "held: Test Plan outcomes missing: held-plan" in r.output
    )
    assert _calls(world["gh"], "create_pr") == []
    assert _git(world["bare"], "branch", "--list", sweep.BRANCH) == ""


def test_pushes_the_branch_and_opens_one_draft_pr_listing_held_plans(world: dict) -> None:
    r = runner.invoke(app, ["debt", "archive-pr", "--yes"])
    assert r.exit_code == 0, r.output
    assert _git(world["bare"], "branch", "--list", sweep.BRANCH) != ""
    (pr,) = _calls(world["gh"], "create_pr")
    assert pr["draft"] is True and pr["head"] == sweep.BRANCH and pr["base"] == "main"
    assert "`old-plan`" in pr["body"] and "held: Test Plan outcomes missing" in pr["body"]
    assert "`held-plan`" in pr["body"] and "young-plan" not in pr["body"]
    assert "CI will not run on this PR" in pr["body"]  # no FR_DEBT_TOKEN: the fallback note
    assert _git(world["work"], "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_fr_debt_token_is_preferred_and_the_note_changes(
    world: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FR_DEBT_TOKEN", "tok")
    assert runner.invoke(app, ["debt", "archive-pr", "--yes"]).exit_code == 0
    import os

    assert os.environ["GH_TOKEN"] == "tok"
    assert "CI runs on this PR" in _calls(world["gh"], "create_pr")[0]["body"]


def test_a_second_run_force_pushes_with_lease_and_refreshes_the_same_pr(world: dict) -> None:
    assert runner.invoke(app, ["debt", "archive-pr", "--yes"]).exit_code == 0
    gh = world["gh"]
    assert runner.invoke(app, ["debt", "archive-pr", "--yes"]).exit_code == 0
    assert len(_calls(gh, "create_pr")) == 1 and len(_calls(gh, "edit_pr")) == 1


def test_a_fork_pr_on_the_same_head_name_is_not_reused(world: dict) -> None:
    gh = world["gh"]
    gh.add_pr(SLUG, 50, head_ref=sweep.BRANCH, cross_repo=True)
    r = runner.invoke(app, ["debt", "archive-pr", "--yes"])
    assert r.exit_code == 0, r.output
    assert _calls(gh, "edit_pr") == [] and len(_calls(gh, "create_pr")) == 1
    assert "not from this repository" in r.output


def test_a_pr_permission_refusal_warns_with_both_remedies_and_exits_zero(world: dict) -> None:
    world["gh"].fail_on_mutation = 0
    r = runner.invoke(app, ["debt", "archive-pr", "--yes"])
    assert r.exit_code == 0, r.output
    assert "::warning::" in r.output and "Allow GitHub Actions" in r.output
    assert "FR_DEBT_TOKEN" in r.output


def test_a_forge_without_draft_prs_is_named_and_exits_zero(world: dict) -> None:
    def boom(*a, **k):  # noqa: ANN002, ANN003, ANN202
        raise UnsupportedForgeOperation("create_pr", "gitea")

    world["gh"].create_pr = boom
    r = runner.invoke(app, ["debt", "archive-pr", "--yes"])
    assert r.exit_code == 0 and "::warning::this forge cannot do `create_pr`" in r.output


def test_nothing_selected_exits_zero_without_touching_git(world: dict) -> None:
    world["box"]["report"] = _report(("young", 2))
    r = runner.invoke(app, ["debt", "archive-pr", "--yes"])
    assert r.exit_code == 0 and "No plan has been merged" in r.output
    assert _git(world["bare"], "branch", "--list", sweep.BRANCH) == ""


def test_a_dirty_checkout_is_refused(world: dict) -> None:
    (world["work"] / "docs/superpowers/plans/old-plan/_meta.yaml").write_text("x: 2\n")
    r = runner.invoke(app, ["debt", "archive-pr", "--yes"])
    assert r.exit_code == 1 and "uncommitted" in r.output


def test_the_identity_is_the_origin_remote_not_the_matrix(world: dict) -> None:
    m = world["work"] / "docs/acceptance"
    m.mkdir(parents=True)
    (m / "matrix.yaml").write_text("schema_version: 5\norg: evil\nrepo: elsewhere\nrows: []\n")
    r = runner.invoke(app, ["debt", "archive-pr", "--yes"])
    assert r.exit_code == 1 and "matrix names" in r.output
    assert _calls(world["gh"], "create_pr") == []


def test_forge_errors_are_class_exported() -> None:
    assert issubclass(FakeGhError, Exception)


def test_a_failed_archive_never_publishes_its_stderr_in_the_pr_body(
    world: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    def archive(root: Path, name: str, env: dict) -> tuple[bool, str]:
        if name == "old-plan":
            return False, "fatal: https://x-access-token:SECRET@github.com/o/r"
        _git(root, "mv", f"docs/superpowers/plans/{name}", f"docs/superpowers/plans/{name}-x")
        return True, ""

    world["box"]["report"] = _report(("old-plan", 30), ("other", 30))
    (world["work"] / "docs/superpowers/plans/other").mkdir()
    monkeypatch.setattr(debt_cmd, "_archive_one", archive)
    r = runner.invoke(app, ["debt", "archive-pr", "--yes"])
    assert "SECRET" not in r.output
    for pr in _calls(world["gh"], "create_pr"):
        assert "SECRET" not in pr["body"] and "x-access-token" not in pr["body"]
