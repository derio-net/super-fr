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
    env.pop("VK_REPO_ROOT", None)
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
    _fake_fr(tmp_path / "bin", "echo 'placement: quiet is not yet available' >&2\nexit 2\n")
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
        "if [ -n \"${VK_REPO_ROOT:-}\" ]; then echo 'VK_REPO_ROOT leaked' >&2; exit 5; fi\n",
    )
    res = _run(repo, tmp_path / "bin")
    assert res.returncode == 0, res.stderr
    assert os.path.isdir(other / "plans")
