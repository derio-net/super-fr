"""`fr pickup --branch <b>` — spec 2026-09-28-closeout-always §D.

A third `fr pickup` mode, mutually exclusive with `<plan-dir> --phase N` and
`--run <id>`: given a branch name (no run cursor required), it prints the
same close-out brief `--run` prints for a finished run, minus the run-only
extras (PR/spec/plan lines, the Test Plan line, out-of-scope findings).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fr.cli import app
from typer.testing import CliRunner

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"

runner = CliRunner()

GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


def _invoke(repo: Path, argv: list[str]):
    env = {**os.environ, "VK_REPO_ROOT": str(repo)}
    return runner.invoke(app, argv, env=env)


def _repo_with_branch(tmp_path: Path, branch: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run([*GIT, "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / "README.md").write_text("x\n")
    subprocess.run([*GIT, "-C", str(repo), "add", "-A"], check=True)
    subprocess.run([*GIT, "-C", str(repo), "commit", "-q", "-m", "init"], check=True)
    subprocess.run([*GIT, "-C", str(repo), "branch", branch], check=True)
    return repo


def test_pickup_branch_prints_the_brief_with_no_run_cursor(tmp_path: Path) -> None:
    repo = _repo_with_branch(tmp_path, "feat/x")

    result = _invoke(repo, ["pickup", "--branch", "feat/x"])

    assert result.exit_code == 0, result.output
    out = result.output
    assert "branch: feat/x" in out
    assert str(repo.resolve()) in out
    i_verify = out.index("fr isolation verify-merge --branch feat/x")
    i_stop = out.index("STOP", i_verify)
    i_status = out.index("fr status", i_stop)
    i_up = out.index("fr isolation up --branch chore/closeout-feat-x", i_status)
    i_archive = out.index("fr archive --branch feat/x", i_up)
    i_commit = out.index(
        "git add -A && git commit -m 'chore: close out feat/x' "
        "&& git push -u origin chore/closeout-feat-x",
        i_archive,
    )
    i_down = out.index("fr isolation down --branch feat/x", i_commit)
    assert i_verify < i_stop < i_status < i_up < i_archive < i_commit < i_down
    # Branch mode never prints run-only content.
    assert "PR:" not in out
    assert "spec:" not in out
    assert "Test Plan" not in out


def test_pickup_branch_refuses_an_unresolvable_branch(tmp_path: Path) -> None:
    repo = _repo_with_branch(tmp_path, "feat/x")

    result = _invoke(repo, ["pickup", "--branch", "does-not-exist"])

    assert result.exit_code == 2
    output = " ".join((result.output or "").split()) + " ".join((result.stderr or "").split())
    assert "does-not-exist" in output


def test_pickup_branch_refuses_combination_with_plan_dir(tmp_path: Path) -> None:
    repo = _repo_with_branch(tmp_path, "feat/x")

    result = _invoke(repo, ["pickup", str(FIXTURE), "--branch", "feat/x"])

    assert result.exit_code == 2


def test_pickup_branch_refuses_combination_with_phase(tmp_path: Path) -> None:
    repo = _repo_with_branch(tmp_path, "feat/x")

    result = _invoke(repo, ["pickup", "--branch", "feat/x", "--phase", "1"])

    assert result.exit_code == 2


def test_pickup_branch_refuses_combination_with_run(tmp_path: Path) -> None:
    repo = _repo_with_branch(tmp_path, "feat/x")

    result = _invoke(repo, ["pickup", "--branch", "feat/x", "--run", "r1"])

    assert result.exit_code == 2


def test_pickup_phase_mode_still_works_with_no_branch_flag(tmp_path: Path) -> None:
    result = _invoke(tmp_path, ["pickup", str(FIXTURE), "--phase", "1"])

    assert result.exit_code == 0, result.output
    assert "Phase 1/1" in result.output
