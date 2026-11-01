"""Pins the CI test layout of spec 2026-11-01-ci-speed §3.B/§3.C (R4-R7, R12).

`plan` picks ONE durations file per run, every shard of both legs splits by it,
`collect` + `split-check` prove the shards ran exactly the collected set, and a
push to main saves the 3.14 leg's measured durations for the next run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
CI = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text())
JOBS: dict[str, Any] = CI["jobs"]


def _needs(job: str) -> list[str]:
    n = JOBS[job].get("needs", [])
    return [n] if isinstance(n, str) else list(n)


def _steps_text(job: str) -> str:
    return "\n".join(f"{s.get('uses', '')} {s.get('run', '')}" for s in JOBS[job]["steps"])


def _pytest_step(job: str) -> dict[str, Any]:
    steps = [s for s in JOBS[job]["steps"] if "uv run pytest" in str(s.get("run", ""))]
    assert len(steps) == 1, steps
    return steps[0]


def test_plan_job_restores_the_cache_falls_back_and_uploads_one_artifact() -> None:
    plan = JOBS["plan"]
    assert plan["timeout-minutes"] == 5
    uses = [s for s in plan["steps"] if "actions/cache/restore" in str(s.get("uses", ""))]
    assert len(uses) == 1
    assert "test-durations-" in yaml.safe_dump(uses[0]["with"])
    assert ".test_durations" in _steps_text("plan")
    upload = next(s for s in plan["steps"] if "upload-artifact" in str(s.get("uses", "")))
    assert upload["with"]["name"] == "durations-plan"


def test_test_job_splits_six_ways_by_the_plans_file() -> None:
    test = JOBS["test"]
    assert "plan" in _needs("test")
    assert test["timeout-minutes"] == 20
    assert test["strategy"]["matrix"]["shard"] == [1, 2, 3, 4, 5, 6]
    assert test["strategy"]["matrix"]["python"] == ["3.11", "3.14"]
    run = _pytest_step("test")["run"]
    for flag in (
        "--splits 6",
        "--splitting-algorithm least_duration",
        "--store-durations",
        "--clean-durations",
        "--durations-path shard-durations.json",
    ):
        assert flag in run, flag
    steps = test["steps"]
    cp = next(
        i
        for i, s in enumerate(steps)
        if "shard-durations.json" in str(s.get("run", ""))
        and "cp " in s["run"]
        and "durations-plan.json" in s["run"]
    )
    assert cp < steps.index(_pytest_step("test"))


def test_collect_job_collects_per_leg_with_the_shards_addopts_and_no_split() -> None:
    collect = JOBS["collect"]
    assert collect["timeout-minutes"] == 10
    assert collect["strategy"]["matrix"]["python"] == ["3.11", "3.14"]
    run = _pytest_step("collect")["run"]
    assert "--collect-only -q" in run
    assert '-o addopts="--strict-markers"' in run
    assert "--splits" not in run and "--cov" not in run


def test_split_check_gates_and_saves_the_cache_only_on_main_pushes() -> None:
    sc = JOBS["split-check"]
    assert set(_needs("split-check")) == {"test", "collect"}
    assert sc["timeout-minutes"] == 5
    assert "split_check.py check" in _steps_text("split-check")
    save = next(s for s in sc["steps"] if "actions/cache/save" in str(s.get("uses", "")))
    assert save["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    assert save["with"]["key"] == "test-durations-${{ github.run_id }}"
    merge = next(s for s in sc["steps"] if "split_check.py merge" in str(s.get("run", "")))
    assert "py3.14" in merge["run"]
    # One file, three places: merge writes it, save stores it, plan restores it.
    restore = next(
        s for s in JOBS["plan"]["steps"] if "actions/cache/restore" in str(s.get("uses", ""))
    )
    out = merge["run"].split("-o", 1)[1].split()[0]
    assert out == save["with"]["path"] == restore["with"]["path"]


def test_split_check_covers_every_test_leg() -> None:
    test_legs = JOBS["test"]["strategy"]["matrix"]["python"]
    assert JOBS["collect"]["strategy"]["matrix"]["python"] == test_legs
    text = _steps_text("split-check")
    assert "for dir in collected/collected-py*" in text
    assert "3.11 3.14" not in text


def test_ci_ok_needs_the_new_jobs() -> None:
    assert {"plan", "collect", "split-check"} <= set(_needs("ci-ok"))
