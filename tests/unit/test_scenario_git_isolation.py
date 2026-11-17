"""A scenario's git never reaches the repository its caller is in (gh#1468).

A git hook and `git rebase -x` both export `GIT_DIR` (a hook also `GIT_INDEX_FILE`)
naming the checkout they run in. A pytest started there passed it to every
scenario, so `git init <fixture>` re-initialised the LIVE repository instead of
creating one, and a fixture's `git commit --allow-empty` and `git checkout -b
feat/fixture` moved the run worktree's branch. Both entry points now drop every
variable `git rev-parse --local-env-vars` names: the pytest harness
(`tests/integration/test_scenarios.py`) and `tests/scenarios/_common.sh`, which
`fr verification walk`'s scenarios source too.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.integration import test_scenarios as harness

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMON = REPO_ROOT / "tests" / "scenarios" / "_common.sh"

# What the retire-vk run's leak did: the closed-recovery fixture's two git steps.
FIXTURE_STEPS = (
    "git -c user.name=scenario -c user.email=scenario@example.invalid "
    "commit -q --allow-empty -m fixture && git checkout -q -b feat/fixture"
)


def _git(cwd: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()


@pytest.fixture
def live(tmp_path: Path) -> dict[str, str]:
    """A run worktree, and the env a hook running in it hands its children."""
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    _git(main, "commit", "-q", "--allow-empty", "-m", "base")
    wt = tmp_path / "run-wt"
    _git(main, "worktree", "add", "-q", "-b", "feat/run", str(wt))
    gitdir = _git(wt, "rev-parse", "--absolute-git-dir")
    return {
        "wt": str(wt),
        "head": _git(wt, "rev-parse", "HEAD"),
        "GIT_DIR": gitdir,
        "GIT_INDEX_FILE": str(Path(gitdir) / "index"),
    }


def _assert_untouched(live: dict[str, str]) -> None:
    wt = Path(live["wt"])
    assert _git(wt, "symbolic-ref", "--short", "HEAD") == "feat/run"
    assert _git(wt, "rev-parse", "HEAD") == live["head"]
    assert "feat/fixture" not in _git(wt, "branch", "--list")


def _fresh(path: Path) -> Path:
    path.mkdir()
    _git(path, "init", "-q")
    return path


def test_common_sh_drops_the_callers_git_scope(tmp_path: Path, live: dict[str, str]) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "fr").write_text("#!/bin/sh\nexit 0\n")  # _common.sh needs an fr on PATH
    (bin_dir / "fr").chmod(0o755)
    fixture = _fresh(tmp_path / "fixture")
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "GIT_DIR": live["GIT_DIR"],
        "GIT_INDEX_FILE": live["GIT_INDEX_FILE"],
    }
    done = subprocess.run(
        ["bash", "-c", f'. "{COMMON}"; {FIXTURE_STEPS}'],
        cwd=fixture,
        env=env,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr
    _assert_untouched(live)
    assert _git(fixture, "symbolic-ref", "--short", "HEAD") == "feat/fixture"


def test_the_harness_runs_a_scenario_outside_the_callers_repo(
    tmp_path: Path, live: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    scenarios = tmp_path / "scenarios"
    scenarios.mkdir()
    probe = scenarios / "probe.sh"
    probe.write_text(f"#!/usr/bin/env bash\nset -e\n{FIXTURE_STEPS}\necho 'ok: probe'\n")
    probe.chmod(0o755)
    monkeypatch.setattr(harness, "SCENARIOS", scenarios)
    monkeypatch.setenv("GIT_DIR", live["GIT_DIR"])
    monkeypatch.setenv("GIT_INDEX_FILE", live["GIT_INDEX_FILE"])
    prefix = tmp_path / "prefix"
    (prefix / "bin").mkdir(parents=True)
    work = tmp_path / "work"
    work.mkdir()
    harness._scenario("probe", prefix, work)
    _assert_untouched(live)
    fixture = work / "fixture"
    assert _git(fixture, "symbolic-ref", "--short", "HEAD") == "feat/fixture"
