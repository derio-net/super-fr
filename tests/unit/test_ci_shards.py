"""Pins the CI `test` job's shard layout and partition (spec 2026-09-26
ci-time-budget §3.A, Test Plan §7.1/§7.8).

(a) `.github/workflows/ci.yml` shape: the `test` job is a 4-way matrix with
`fail-fast: false`, its pytest step clears `addopts` and re-adds
`--strict-markers --cov`, and a `coverage` job (`needs: test`) combines the
shards and gates at 75.

(b) Partition: pytest-split's `--splits 4 --group k` must cover every
collected test exactly once, with no gaps and no overlaps. Run as
subprocesses so a real `pytest --collect-only` decides this, not a guess
about pytest-split's algorithm.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_YAML = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# Set on the subprocesses this test itself spawns, so that if a full-suite
# invocation's own subprocess call somehow re-entered this test file, it
# would skip part (b) instead of recursing.
_INNER_ENV_VAR = "PYTEST_SPLIT_INNER"


def _load_ci_workflow() -> dict:
    return yaml.safe_load(CI_YAML.read_text())


def test_test_job_matrix_shape() -> None:
    workflow = _load_ci_workflow()
    test_job = workflow["jobs"]["test"]

    strategy = test_job["strategy"]
    assert strategy["matrix"]["shard"] == [1, 2, 3, 4]
    assert strategy["fail-fast"] is False


def test_test_job_pytest_step_pins_addopts_and_splitting() -> None:
    workflow = _load_ci_workflow()
    test_job = workflow["jobs"]["test"]

    pytest_steps = [
        step for step in test_job["steps"] if "run" in step and "pytest" in step["run"]
    ]
    assert len(pytest_steps) == 1, f"expected exactly one pytest step, got {pytest_steps}"
    run = pytest_steps[0]["run"]

    assert '-o addopts="--strict-markers --cov"' in run
    assert "--cov-report=" in run
    assert "--splits 4" in run
    assert "--group ${{ matrix.shard }}" in run
    assert "--splitting-algorithm least_duration" in run


def test_test_job_checkout_has_full_fetch_depth() -> None:
    workflow = _load_ci_workflow()
    test_job = workflow["jobs"]["test"]

    checkout_steps = [
        step
        for step in test_job["steps"]
        if step.get("uses", "").startswith("actions/checkout")
    ]
    assert len(checkout_steps) == 1
    assert checkout_steps[0]["with"]["fetch-depth"] == 0


def test_coverage_job_combines_and_gates() -> None:
    workflow = _load_ci_workflow()
    jobs = workflow["jobs"]
    assert "coverage" in jobs, "a `coverage` job must exist (needs: test)"

    coverage_job = jobs["coverage"]
    needs = coverage_job["needs"]
    if isinstance(needs, str):
        needs = [needs]
    assert "test" in needs

    run_steps = " ".join(step.get("run", "") for step in coverage_job["steps"])
    assert "coverage combine" in run_steps
    assert "coverage report --fail-under=75" in run_steps


# ── (b) partition: every collected test exactly once across 4 groups ──


def _collect_node_ids(extra_args: list[str]) -> set[str]:
    """Run `pytest --collect-only -q` as a subprocess and return the set of
    collected node ids (lines containing `::`, excluding the trailing
    summary line)."""
    env = dict(os.environ)
    env[_INNER_ENV_VAR] = "1"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            *extra_args,
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    node_ids = {line.strip() for line in result.stdout.splitlines() if "::" in line}
    assert node_ids, (
        f"no node ids collected (exit={result.returncode}); "
        f"stdout={result.stdout[-2000:]} stderr={result.stderr[-2000:]}"
    )
    return node_ids


def test_shard_partition_is_disjoint_and_complete() -> None:
    if os.environ.get(_INNER_ENV_VAR) == "1":
        import pytest

        pytest.skip(
            f"{_INNER_ENV_VAR}=1: this is already a subprocess spawned by this "
            "test's own partition check — skip to avoid recursing"
        )

    unsplit = _collect_node_ids([])

    groups: list[set[str]] = []
    for k in (1, 2, 3, 4):
        groups.append(
            _collect_node_ids(
                ["--splits", "4", "--group", str(k), "--splitting-algorithm", "least_duration"]
            )
        )

    # pairwise disjoint
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            overlap = groups[i] & groups[j]
            assert not overlap, f"group {i + 1} and group {j + 1} overlap: {overlap}"

    union = set().union(*groups)
    assert union == unsplit, (
        f"missing from shards: {unsplit - union}; extra in shards: {union - unsplit}"
    )
