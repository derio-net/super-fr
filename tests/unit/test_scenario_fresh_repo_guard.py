"""tests/scenarios/_common.sh `scenario_require_fresh_repo` (review p6-r5).

A placement scenario adds an `origin`, commits and pushes in its working directory. Run
from a real checkout it mutated that checkout (one committed onto `main` and tried to push
to GitHub). tests/integration/test_scenarios.py and `fr verification walk` both run a
scenario in a freshly `git init`ed fixture, with no commits and no remote, so that is the
one place the guard lets it run. These tests never let a scenario run: the guard refuses
before the first mutation, and the stub `fr` only satisfies `_common.sh`'s PATH check.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = REPO_ROOT / "tests" / "scenarios"
PLACEMENT = sorted(SCENARIOS.glob("placement-*.sh"))


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _env(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "stub-bin"
    bin_dir.mkdir(exist_ok=True)
    log = tmp_path / "fr-calls.log"
    stub = bin_dir / "fr"
    stub.write_text(f'#!/bin/bash\necho "$*" >> "{log}"\nexit 9\n')
    stub.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}


def _guard(cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    script = f'. "{SCENARIOS / "_common.sh"}"; scenario_require_fresh_repo; echo passed'
    return subprocess.run(["bash", "-c", script], cwd=cwd, env=env, capture_output=True, text=True)


def _with_history(tmp_path: Path) -> Path:
    repo = tmp_path / "checkout"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "history")
    return repo


def test_the_guard_refuses_a_repo_with_history(tmp_path: Path) -> None:
    repo = _with_history(tmp_path)
    done = _guard(repo, _env(tmp_path))
    assert done.returncode != 0 and "passed" not in done.stdout
    assert "fresh" in done.stderr


def test_the_guard_refuses_a_repo_with_a_remote(tmp_path: Path) -> None:
    repo = tmp_path / "remote"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "remote", "add", "origin", "https://example.com/org/repo.git")
    done = _guard(repo, _env(tmp_path))
    assert done.returncode != 0 and "passed" not in done.stdout


def test_the_guard_refuses_a_subdirectory_and_a_non_repo(tmp_path: Path) -> None:
    repo = tmp_path / "fresh"
    (repo / "sub").mkdir(parents=True)
    _git(repo, "init", "-q")
    assert _guard(repo / "sub", _env(tmp_path)).returncode != 0
    outside = tmp_path / "outside"
    outside.mkdir()
    env = {**_env(tmp_path), "GIT_CEILING_DIRECTORIES": str(tmp_path)}
    assert _guard(outside, env).returncode != 0


def test_the_guard_passes_the_harness_fixture(tmp_path: Path) -> None:
    """What test_scenarios.py's `_scenario` builds: `git init -q <fixture>`, nothing more."""
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    subprocess.run(["git", "init", "-q", str(fixture)], check=True)
    done = _guard(fixture, _env(tmp_path))
    assert done.returncode == 0, done.stderr
    assert "passed" in done.stdout


@pytest.mark.parametrize("script", PLACEMENT, ids=[p.stem for p in PLACEMENT])
def test_every_placement_scenario_refuses_a_checkout_with_history(
    tmp_path: Path, script: Path
) -> None:
    repo = _with_history(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    done = subprocess.run(
        [str(script)], cwd=repo, env=_env(tmp_path), capture_output=True, text=True
    )
    assert done.returncode != 0
    assert "fresh" in done.stderr, done.stderr
    assert _git(repo, "remote") == ""
    assert _git(repo, "rev-parse", "HEAD") == head
    assert not (tmp_path / "fr-calls.log").exists()
