"""Pins the CI `test` job's shard layout and partition (spec 2026-09-26
ci-time-budget §3.A, Test Plan §7.1/§7.8).

(a) `.github/workflows/ci.yml` shape: the `test` job is a 4-way matrix with
`fail-fast: false`, its pytest step clears `addopts` and re-adds
`--strict-markers --cov`, and a `coverage` job (`needs: test`) combines the
shards and gates at 75.

(b) Partition: pytest-split's `least_duration` grouping must place every
test in exactly one of the 4 groups. This calls pytest-split's own algorithm
in process over the real node ids in `.test_durations`, plus ids absent from
it (a new test gets the average duration), so the check exercises the real
algorithm and costs milliseconds. Earlier versions of this test ran five
full-suite `--collect-only` subprocesses, which took 30-90s inside a change
whose whole point is CI time.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from pytest_split.algorithms import LeastDurationAlgorithm

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_YAML = REPO_ROOT / ".github" / "workflows" / "ci.yml"

DURATIONS = REPO_ROOT / ".test_durations"


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

    pytest_steps = [step for step in test_job["steps"] if "run" in step and "pytest" in step["run"]]
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
        step for step in test_job["steps"] if step.get("uses", "").startswith("actions/checkout")
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


class _Item:
    """The one attribute pytest-split's algorithm reads from a pytest Item."""

    def __init__(self, nodeid: str) -> None:
        self.nodeid = nodeid


def test_shard_partition_is_disjoint_and_complete() -> None:
    durations: dict[str, float] = json.loads(DURATIONS.read_text())
    assert len(durations) > 1000, "the committed .test_durations looks truncated"
    node_ids = [*durations, *(f"tests/unit/test_new_{i}.py::test_x" for i in range(7))]
    items = [_Item(n) for n in node_ids]

    groups_raw = LeastDurationAlgorithm()(4, items, durations)
    groups = [{it.nodeid for it in g.selected} for g in groups_raw]

    assert len(groups) == 4
    assert all(groups), "an empty shard means the matrix is wider than the suite"
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            overlap = groups[i] & groups[j]
            assert not overlap, f"group {i + 1} and group {j + 1} overlap: {sorted(overlap)[:5]}"
    union = set().union(*groups)
    assert union == set(node_ids), f"missing from shards: {sorted(set(node_ids) - union)[:5]}"
