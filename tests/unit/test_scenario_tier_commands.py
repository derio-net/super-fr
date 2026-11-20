"""The scenario tier is deselected locally and run everywhere the suite is evidence
(spec 2026-11-19-local-suite-cost R5, §3.D).

`pyproject.toml`'s addopts carries `-m "not scenario"`, so a plain local `pytest`
skips the slow install and shell-scenario tests. Every command line that is the
suite's evidence must still run them: CI's `collect` and sharded `test` jobs, the
release's collect and shards (they replace addopts), and the release's one-process
staged suite (it keeps addopts, so it passes `-m ""`). `split-check` alone cannot
show this, because collect and the shards would shrink together: this file pins
each command line, and that the options they use really collect both scenario
files.
"""

from __future__ import annotations

import importlib.util
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
CI = REPO / ".github" / "workflows" / "ci.yml"
SCRIPT = REPO / "scripts" / "release.py"
SCENARIOS = "tests/integration/test_scenarios.py"
INSTALL_SH = "tests/integration/test_install_sh.py"
TRIPWIRE = "test_every_scenario_script_has_a_test_here"


def _release():  # type: ignore[no-untyped-def]
    name = "release_script_scenario_tier"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _runs_every_tier(argv: list[str]) -> bool:
    """True when `argv` replaces addopts with options naming no `-m`, or passes
    `-m ""` itself."""
    for i, tok in enumerate(argv):
        if tok == "-m" and i + 1 < len(argv) and argv[i + 1] == "":
            return True
    replaced = False
    for i, tok in enumerate(argv):
        value = None
        if tok == "-o" and i + 1 < len(argv):
            value = argv[i + 1]
        elif tok.startswith("-o") and len(tok) > 2:
            value = tok[2:]
        if value is not None and value.startswith("addopts="):
            if "-m" in shlex.split(value.removeprefix("addopts=")):
                return False
            replaced = True
    if any(tok == "-m" or tok.startswith("-m=") for tok in argv):
        return False
    return replaced


def _ci_pytest_lines(job: str) -> list[list[str]]:
    jobs = yaml.safe_load(CI.read_text())["jobs"]
    lines = [
        shlex.split(step["run"])
        for step in jobs[job]["steps"]
        if "pytest" in str(step.get("run", ""))
    ]
    assert lines, f"ci.yml's {job} job runs no pytest"
    return lines


@pytest.mark.parametrize("job", ["collect", "test"])
def test_ci_collect_and_test_jobs_run_the_scenario_tier(job: str) -> None:
    for argv in _ci_pytest_lines(job):
        assert _runs_every_tier(argv), (job, argv)


def test_the_release_collect_and_shards_run_the_scenario_tier(tmp_path: Path) -> None:
    release = _release()
    assert _runs_every_tier(release._collect_pytest_args(tmp_path))
    assert _runs_every_tier(
        release._shard_pytest_args(tmp_path, group=1, splits=6, out=tmp_path / "d.json")
    )


def test_the_release_staged_suite_runs_the_scenario_tier(tmp_path: Path) -> None:
    release = _release()
    calls: list[list[str]] = []

    def run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        if "pytest" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "1 passed\n", "")
        return subprocess.CompletedProcess(cmd, 0, "5.0.0\n", "")

    assert release._run_staged_tests(tmp_path, "5.0.0", run=run) is None
    pytest_call = next(c for c in calls if "pytest" in c)
    assert _runs_every_tier(pytest_call), pytest_call


def test_the_predicate_rejects_a_line_that_keeps_the_default_deselection() -> None:
    assert not _runs_every_tier(["pytest", "-q"])
    assert not _runs_every_tier(["pytest", "-o", "addopts=--strict-markers -m 'not x'"])
    assert not _runs_every_tier(["pytest", "-o", "addopts=--strict-markers", "-m", "smoke"])
    assert _runs_every_tier(["pytest", "-o", "addopts=--strict-markers"])
    assert _runs_every_tier(["pytest", "-q", "-m", ""])


def _collect(*args: str) -> list[str]:
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert done.returncode in (0, 5), done.stdout + done.stderr
    return [line for line in done.stdout.splitlines() if "::" in line]


def test_the_ci_options_collect_both_scenario_files() -> None:
    nodes = _collect("-o", "addopts=--strict-markers", SCENARIOS, INSTALL_SH)
    assert any(n.startswith(SCENARIOS + "::") and TRIPWIRE not in n for n in nodes)
    assert any(n.startswith(INSTALL_SH + "::") for n in nodes)


def test_the_default_local_run_keeps_only_the_tripwire_of_the_scenario_file() -> None:
    nodes = _collect("--no-cov", SCENARIOS, INSTALL_SH)
    assert nodes == [f"{SCENARIOS}::{TRIPWIRE}"]
