"""`fr plan ...` CLI-layer behaviour (the library is covered by test_plan_ops.py)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    (repo / "README.md").write_text("x\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)
    return repo


def test_plan_create_reports_a_foreign_wrapper_on_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The warning is fr's own output, not Python's last-resort log handler (gh#610 r2)."""
    repo = _git_repo(tmp_path)
    wrapper = repo / "scripts" / "validate-plans.sh"
    wrapper.parent.mkdir()
    foreign = "#!/usr/bin/env bash\n# our own house validator\nexit 0\n"
    wrapper.write_text(foreign)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")

    res = CliRunner().invoke(
        app,
        ["plan", "create", "--slug", "2026-05-10-foreign", "--target-repo", "o/r"],
    )

    assert res.exit_code == 0, res.output
    assert wrapper.read_text() == foreign
    assert "warning:" in res.stderr
    assert "validate-plans.sh" in res.stderr


# --- gh#610 §3.C: fr plan commits its own writes ------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _feature_repo(tmp_path: Path) -> Path:
    repo = _git_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feat/p")
    return repo


_PHASES = """
- number: 1
  title: One
  tag: agentic
  tier: standard
  tasks:
    - number: 1
      title: T
      steps:
        - {id: P1.T1.S1, text: do it}
"""


def _create(repo: Path, tmp_path: Path, slug: str = "2026-09-25-p"):
    phases = tmp_path / "phases.yaml"
    phases.write_text(_PHASES)
    return CliRunner().invoke(
        app,
        [
            "plan", "create", "--slug", slug, "--target-repo", "o/r",
            "--phases-file", str(phases),
        ],
    )  # fmt: skip


def test_plan_create_commits_the_plan_journal_and_wrapper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _feature_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    (repo / "unrelated.md").write_text("executor's own work\n")
    _git(repo, "add", "--", "unrelated.md")

    res = _create(repo, tmp_path)

    assert res.exit_code == 0, res.output
    # Outcome, not cadence (operator steer, p3-steer): fr's record paths are
    # clean when the command returns, whatever number of commits it took —
    # never "exactly one commit containing all three".
    assert _git(repo, "status", "--porcelain", "--", "docs", "scripts") == ""
    for path in (
        "scripts/validate-plans.sh",
        "docs/superpowers/journals/plans/2026-09-25-p.md",
        "docs/superpowers/plans/2026-09-25-p/_meta.yaml",
    ):
        # Format, kept (robust per path rather than assuming HEAD is "the
        # one commit" this invocation made).
        assert (
            _git(repo, "log", "-1", "--format=%s", "--", path)
            == "chore(fr): plan 2026-09-25-p — create"
        ), path
    # The unrelated file the "executor" staged stays staged, never swept in
    # — an outcome, kept as-is (operator steer).
    assert _git(repo, "diff", "--cached", "--name-only") == "unrelated.md"


def test_plan_edit_tick_and_complete_each_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _feature_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    assert _create(repo, tmp_path).exit_code == 0
    plan = "docs/superpowers/plans/2026-09-25-p"

    # Directory-scoped, not a specific file: `tick` writes the owning phase
    # yaml, `--complete-phase` may touch a different one — either way `git
    # log -1 -- <plan dir>` finds the fr commit that actually touched it,
    # instead of assuming HEAD is "the one commit" (operator steer, p3-steer).

    res = CliRunner().invoke(app, ["plan", "edit", plan, "--tick", "P1.T1.S1"])
    assert res.exit_code == 0, res.output
    assert (
        _git(repo, "log", "-1", "--format=%s", "--", plan)
        == "chore(fr): plan 2026-09-25-p — tick P1.T1.S1"
    )
    assert _git(repo, "status", "--porcelain", "--", "docs") == ""
    # p3-steer (c): at most one commit-report line per invocation.
    commit_lines = [
        ln
        for ln in res.stderr.splitlines()
        if ln.startswith("fr: committed") or ln.startswith("fr: not committed")
    ]
    assert len(commit_lines) <= 1, res.stderr

    res = CliRunner().invoke(app, ["plan", "edit", plan, "--complete-phase", "1"])
    assert res.exit_code == 0, res.output
    assert (
        _git(repo, "log", "-1", "--format=%s", "--", plan)
        == "chore(fr): plan 2026-09-25-p — complete phase 1"
    )
    assert _git(repo, "status", "--porcelain", "--", "docs") == ""


# --- p3-m1: rework / rework-add commit like create / edit ---------------------


def test_plan_rework_and_rework_add_each_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _feature_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    spec = repo / "docs" / "superpowers" / "specs" / "2026-09-25-p-design.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        "# Spec\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n|---|---|---|---|\n"
    )
    _git(repo, "add", "--", "docs")
    _git(repo, "commit", "-qm", "spec")
    phases = tmp_path / "phases.yaml"
    phases.write_text(_PHASES)
    res = CliRunner().invoke(
        app,
        [
            "plan", "create", "--slug", "2026-09-25-p", "--target-repo", "o/r",
            "--phases-file", str(phases), "--spec", "docs/superpowers/specs/2026-09-25-p-design.md",
        ],
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    (repo / "unrelated.md").write_text("executor's own work\n")
    _git(repo, "add", "--", "unrelated.md")

    res = CliRunner().invoke(app, ["plan", "rework", "docs/superpowers/plans/2026-09-25-p"])

    assert res.exit_code == 0, res.output
    # Outcome, not cadence (operator steer, p3-steer): fr's record paths are
    # clean when the command returns, whatever number of commits it took.
    assert _git(repo, "status", "--porcelain", "--", "docs") == ""
    for path in (
        "docs/superpowers/plans/2026-09-25-p-rework-1/_meta.yaml",
        "docs/superpowers/specs/2026-09-25-p-design.md",
    ):
        # Format, kept (robust per path rather than assuming HEAD is "the
        # one commit").
        assert (
            _git(repo, "log", "-1", "--format=%s", "--", path)
            == "chore(fr): plan 2026-09-25-p-rework-1 — rework"
        ), path
    # The unrelated file the "executor" staged stays staged, never swept in
    # — an outcome, kept as-is (operator steer).
    assert _git(repo, "diff", "--cached", "--name-only") == "unrelated.md"

    res = CliRunner().invoke(
        app,
        [
            "plan", "rework-add", "docs/superpowers/plans/2026-09-25-p-rework-1",
            "--item", "i", "--source", "s", "--track", "development",
        ],
    )  # fmt: skip

    assert res.exit_code == 0, res.output
    assert (
        _git(
            repo,
            "log",
            "-1",
            "--format=%s",
            "--",
            "docs/superpowers/plans/2026-09-25-p-rework-1/_meta.yaml",
        )
        == "chore(fr): plan 2026-09-25-p-rework-1 — rework-add"
    )
    assert _git(repo, "status", "--porcelain", "--", "docs") == ""
    assert _git(repo, "diff", "--cached", "--name-only") == "unrelated.md"


# --- p3-m3: when git cannot say what was staged, commit nothing ---------------


def test_staged_among_commits_nothing_when_git_cannot_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.git
    from fr.commands import plan_cmd

    repo = _feature_repo(tmp_path)
    foreign = repo / "scripts" / "validate-plans.sh"
    foreign.parent.mkdir()
    foreign.write_text("#!/bin/sh\nexit 0\n")

    def refuse(*_a: object, **_k: object) -> object:
        raise fr.git.GitUnavailableError("git is not installed or not on PATH")

    monkeypatch.setattr(fr.git, "git_answer", refuse)

    assert plan_cmd._staged_among(repo, [foreign, repo / "README.md"]) is None
