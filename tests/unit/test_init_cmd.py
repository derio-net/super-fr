"""`fr init validator-wrapper` — the harness-neutral wrapper installer.

Replaces the Claude-only `bash ~/.claude/plugins/marketplaces/.../
install-validator-wrapper.sh` remedy (2026-09-25 fr-goal-closeout-defects
spec §3.B): every guard that tells an operator to repair a missing wrapper
now names one `fr` command that works on every harness.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from fr import plan_validator_wrapper
from fr.cli import app
from fr.plan_validator_wrapper import is_super_fr_validator_wrapper
from typer.testing import CliRunner

runner = CliRunner()


def _git_repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    (r / "README.md").write_text("hi\n")
    subprocess.run(["git", "-C", str(r), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(r), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        check=True,
    )
    return r


def _staged_files(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--name-only"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return out.splitlines()


def test_repair_command_names_the_neutral_installer() -> None:
    assert plan_validator_wrapper.REPAIR_COMMAND == "fr init validator-wrapper"


def test_writes_stages_and_marks_executable(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)

    res = runner.invoke(app, ["init", "validator-wrapper", "--repo", str(repo)])

    assert res.exit_code == 0, res.output
    target = repo / "scripts" / "validate-plans.sh"
    assert target.is_file()
    assert target.stat().st_mode & 0o111
    assert is_super_fr_validator_wrapper(target)
    assert "scripts/validate-plans.sh" in _staged_files(repo)


def test_foreign_file_left_untouched_exits_2(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    target = repo / "scripts" / "validate-plans.sh"
    target.parent.mkdir(parents=True)
    foreign = "#!/usr/bin/env bash\n# our own house validator\nexit 0\n"
    target.write_text(foreign)
    target.chmod(0o755)

    res = runner.invoke(app, ["init", "validator-wrapper", "--repo", str(repo)])

    assert res.exit_code == 2
    assert "scripts/validate-plans.sh" in res.output
    assert target.read_text() == foreign
    assert _staged_files(repo) == []


def test_second_run_is_a_noop(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    first = runner.invoke(app, ["init", "validator-wrapper", "--repo", str(repo)])
    assert first.exit_code == 0, first.output
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "wrapper",
        ],
        check=True,
    )

    res = runner.invoke(app, ["init", "validator-wrapper", "--repo", str(repo)])

    assert res.exit_code == 0, res.output
