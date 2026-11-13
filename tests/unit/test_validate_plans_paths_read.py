"""validate-plans.sh's read of `fr settings paths --shell` (review p2-r1): fall back to the
repo literals only for an absent or too-old `fr`; a refusal from `fr` is the script's own."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate-plans.sh"


def _fake_fr(bindir: Path, body: str) -> None:
    bindir.mkdir(exist_ok=True)
    fr = bindir / "fr"
    fr.write_text("#!/bin/sh\n" + body)
    fr.chmod(fr.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs/superpowers/plans").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def _run(repo: Path, bindir: Path | None) -> subprocess.CompletedProcess[str]:
    path = f"{bindir}:" if bindir else ""
    # /usr/bin:/bin keeps git/sed; a real `fr` is never on it.
    env = {"PATH": path + "/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin", "HOME": str(repo)}
    env.pop("FR_REPO_ROOT", None)
    return subprocess.run(
        ["bash", str(SCRIPT)], cwd=repo, env=env, capture_output=True, text=True, check=False
    )


def test_fr_absent_falls_back_to_the_literals(repo: Path) -> None:
    res = _run(repo, None)
    assert res.returncode == 0, res.stderr


def test_an_old_fr_without_the_subcommand_falls_back(repo: Path, tmp_path: Path) -> None:
    _fake_fr(tmp_path / "bin", "echo \"Error: No such command 'paths'.\" >&2\nexit 2\n")
    res = _run(repo, tmp_path / "bin")
    assert res.returncode == 0, res.stderr


def test_a_refusing_fr_fails_the_script_with_its_message(repo: Path, tmp_path: Path) -> None:
    _fake_fr(
        tmp_path / "bin",
        "echo 'fr settings paths: refused: placement: quiet is not yet available' >&2\nexit 2\n",
    )
    res = _run(repo, tmp_path / "bin")
    assert res.returncode != 0
    assert "placement: quiet is not yet available" in res.stderr


def test_a_working_fr_supplies_the_directories(repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "elsewhere"
    (other / "plans").mkdir(parents=True)
    (other / "plans" / "2026-01-01-x").mkdir()
    _fake_fr(
        tmp_path / "bin",
        f"echo \"FR_PLANS_DIR='{other}/plans'\"\n"
        f"echo \"FR_PLAN_CONFIG_FILE='{other}/none.yaml'\"\n"
        "if [ -n \"${FR_REPO_ROOT:-}\" ]; then echo 'FR_REPO_ROOT leaked' >&2; exit 5; fi\n",
    )
    res = _run(repo, tmp_path / "bin")
    assert res.returncode == 0, res.stderr
    assert os.path.isdir(other / "plans")


# --- review pr1431-r7: only an explicit placement refusal is fatal ------------------


def _repo_with_a_plan(root: Path) -> Path:
    """A repo-placement checkout holding one plan with no header, so the validator must
    actually read the literal plans dir to fail: `exit 1` proves it validated."""
    plan = root / "docs/superpowers/plans/2026-01-01-x.md"
    plan.write_text("# x\n")
    return plan


@pytest.mark.parametrize(
    "body",
    [
        "echo 'Traceback (most recent call last): garbage' >&2\necho 'FR_PLANS_DIR=$(touch /x)'\n"
        "exit 1\n",
        "echo 'fr: refusing — two fr binaries serve this session (super-fr#746).' >&2\nexit 2\n",
        "echo 'Usage: fr settings paths [OPTIONS]' >&2\necho \"No such option: --no-create\" >&2\n"
        "exit 2\n",
    ],
    ids=["broken", "identity-refusing", "unknown-option"],
)
def test_an_fr_that_gives_no_answer_still_validates_the_literals(
    repo: Path, tmp_path: Path, body: str
) -> None:
    _repo_with_a_plan(repo)
    _fake_fr(tmp_path / "bin", body)
    res = _run(repo, tmp_path / "bin")
    assert res.returncode == 1, (res.returncode, res.stdout, res.stderr)
    assert "2026-01-01-x" in res.stdout + res.stderr


def test_a_missing_fr_still_validates_the_literals(repo: Path) -> None:
    _repo_with_a_plan(repo)
    res = _run(repo, None)
    assert res.returncode == 1, (res.stdout, res.stderr)


def test_fr_is_asked_with_no_create(repo: Path, tmp_path: Path) -> None:
    log = tmp_path / "argv.log"
    _fake_fr(tmp_path / "bin", f'echo "$*" >> "{log}"\n')
    assert _run(repo, tmp_path / "bin").returncode == 0
    assert log.read_text().strip() == "settings paths --shell --no-create"


def test_a_relative_path_fr_is_never_run(repo: Path, tmp_path: Path) -> None:
    """Resolved like the hooks: only absolute PATH entries (or an absolute pin) count."""
    ran = tmp_path / "ran"
    (repo / "bin").mkdir()
    planted = repo / "bin" / "fr"
    planted.write_text(f'#!/bin/sh\ntouch "{ran}"\n')
    planted.chmod(0o755)
    env = {"PATH": "bin:/usr/bin:/bin", "HOME": str(repo)}
    res = subprocess.run(
        ["bash", str(SCRIPT)], cwd=repo, env=env, capture_output=True, text=True, check=False
    )
    assert res.returncode == 0, res.stderr
    assert not ran.exists()


def test_an_absolute_fr_harness_pin_is_used(repo: Path, tmp_path: Path) -> None:
    log = tmp_path / "pin.log"
    _fake_fr(tmp_path / "pin", f'echo pinned >> "{log}"\n')
    env = {"PATH": "/usr/bin:/bin", "HOME": str(repo), "FR_HARNESS_FR": str(tmp_path / "pin/fr")}
    res = subprocess.run(
        ["bash", str(SCRIPT)], cwd=repo, env=env, capture_output=True, text=True, check=False
    )
    assert res.returncode == 0, res.stderr
    assert log.read_text().strip() == "pinned"


def test_a_real_placement_refusal_is_recognised(repo: Path, tmp_path: Path) -> None:
    """The real `fr`'s refusal starts with the stable prefix the validator keys on."""
    from fr.commands.settings_cmd import PATHS_REFUSAL_PREFIX

    _fake_fr(
        tmp_path / "bin",
        f"echo '{PATHS_REFUSAL_PREFIX}placement stealth: no' >&2\nexit 2\n",
    )
    res = _run(repo, tmp_path / "bin")
    assert res.returncode == 2
    assert "placement stealth: no" in res.stderr
    assert PATHS_REFUSAL_PREFIX.startswith("fr settings paths: refused")


def test_under_quiet_the_validator_creates_no_fr_branch_or_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real fr, asked with --no-create: no local `fr` branch, no `fr` worktree."""
    import sys

    from tests.unit.settings_repo import git, make_repo
    from tests.unit.test_placement_quiet import QUIET, push_fr_branch

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    root = make_repo(tmp_path)
    push_fr_branch(root, QUIET)
    git(root, "checkout", "-q", "-b", "feat/q")
    fr_bin = Path(sys.executable).parent / "fr"
    assert fr_bin.is_file()
    env = {
        "PATH": f"{fr_bin.parent}:/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin",
        "HOME": str(home),
        "FR_SKIP_IDENTITY": "1",
        "FR_SKIP_MIGRATION": "1",
    }
    res = subprocess.run(
        ["bash", str(SCRIPT)], cwd=root, env=env, capture_output=True, text=True, check=False
    )
    assert res.returncode == 0, (res.stdout, res.stderr)
    branches = git(root, "branch", "--list", "fr").strip()
    assert branches == ""
    assert not (home / ".cache" / "fr" / "worktrees").exists()
    assert len(git(root, "worktree", "list", "--porcelain").split("worktree ")) == 2
