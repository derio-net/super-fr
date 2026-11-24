"""`ci.yml`'s lanes, concurrency and landed skip (spec 2026-11-24-ci-economy R1, R2, R5-R7,
R15-R17). The decisions live in `scripts/ci_lane.py` (`test_ci_lane.py`); this pins the
workflow that calls it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

CI = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
WORKFLOW: dict[str, Any] = yaml.safe_load(CI.read_text("utf-8"))
JOBS: dict[str, Any] = WORKFLOW["jobs"]
SHARD_JOBS = ("plan", "collect", "test", "split-check", "coverage")
FULL = "needs.classify.outputs.lane == 'full'"
LIGHT = "needs.classify.outputs.lane == 'light'"
NOT_LANDED = "needs.classify.outputs.lane != 'landed'"


def _needs(job: str) -> list[str]:
    needs = JOBS[job].get("needs", [])
    return [needs] if isinstance(needs, str) else list(needs)


def _run_text(job: str) -> str:
    return "\n".join(str(s.get("run", "")) for s in JOBS[job]["steps"])


def _checkout(job: str) -> dict[str, Any]:
    return next(s for s in JOBS[job]["steps"] if "actions/checkout" in str(s.get("uses", "")))


# R1
def test_pull_request_runs_share_a_group_and_cancel_only_there() -> None:
    assert WORKFLOW["concurrency"] == {
        "group": (
            "${{ github.event_name == 'pull_request' && format('ci-pr-{0}', github.ref)"
            " || format('ci-{0}-{1}', github.event_name, github.run_id) }}"
        ),
        "cancel-in-progress": "${{ github.event_name == 'pull_request' }}",
    }


# R2, R17
def test_ci_ok_always_runs_and_asks_the_verdict() -> None:
    ci_ok = JOBS["ci-ok"]
    assert ci_ok["if"] == "always()"
    assert set(_needs("ci-ok")) == set(JOBS) - {"ci-ok"}
    assert {"classify", "scoped-tests"} <= set(_needs("ci-ok"))
    step = next(s for s in ci_ok["steps"] if "ci_lane.py verdict" in str(s.get("run", "")))
    assert step["env"]["LANE"] == "${{ needs.classify.outputs.lane }}"
    assert step["env"]["NEEDS"] == "${{ toJSON(needs) }}"
    assert step["env"]["TRUSTED_RUN"] == "${{ needs.classify.outputs.trusted_run }}"


# R5, R15
def test_classify_reads_full_history_with_read_only_permissions() -> None:
    classify = JOBS["classify"]
    assert _checkout("classify")["with"]["fetch-depth"] == 0
    assert classify["permissions"] == {"contents": "read", "actions": "read"}
    assert classify["outputs"]["lane"] == "${{ steps.lane.outputs.lane }}"
    assert classify["outputs"]["trusted_run"] == "${{ steps.lane.outputs.trusted_run }}"
    assert "needs" not in classify and "if" not in classify


def test_classify_chooses_the_subcommand_by_event() -> None:
    step = next(s for s in JOBS["classify"]["steps"] if s.get("id") == "lane")
    run = step["run"]
    assert step["env"]["EVENT"] == "${{ github.event_name }}"
    assert step["env"]["REF"] == "${{ github.ref }}"
    assert step["env"]["GH_TOKEN"] == "${{ github.token }}"
    push_main = run.index('"$EVENT" = push') < run.index("ci_lane.py landed")
    assert push_main and "refs/heads/main" in run
    assert 'ci_lane.py landed --sha "$GITHUB_SHA" --run "$GITHUB_RUN_ID"' in run
    assert '"$EVENT" = pull_request' in run
    assert 'ci_lane.py classify --base "$BASE_REF"' in run
    assert step["env"]["BASE_REF"] == "${{ github.base_ref }}"
    # Any other event (a merge group, an fr-queue/** push) is full.
    assert 'echo "lane=full" >> "$GITHUB_OUTPUT"' in run


# R15, R16
@pytest.mark.parametrize("job", SHARD_JOBS)
def test_the_shard_jobs_run_only_in_the_full_lane(job: str) -> None:
    assert "classify" in _needs(job)
    assert FULL in JOBS[job]["if"]


def test_the_shard_jobs_keep_their_own_needs() -> None:
    assert set(_needs("test")) == {"classify", "plan"}
    assert set(_needs("split-check")) == {"classify", "test", "collect"}
    assert set(_needs("coverage")) == {"classify", "test"}


def test_scoped_tests_runs_the_fr_scope_tier_in_the_light_lane() -> None:
    job = JOBS["scoped-tests"]
    assert _needs("scoped-tests") == ["classify"]
    assert job["if"] == LIGHT
    assert _checkout("scoped-tests")["with"]["fetch-depth"] == 0
    step = next(s for s in job["steps"] if "--fr-scope" in str(s.get("run", "")))
    assert 'pytest --fr-scope "origin/$BASE_REF"' in step["run"]
    assert step["env"]["BASE_REF"] == "${{ github.base_ref }}"


# R5, R17
@pytest.mark.parametrize(
    "job",
    sorted(set(JOBS) - {"classify", "ci-ok", "scoped-tests", "validate-artifacts", *SHARD_JOBS}),
)
def test_every_other_job_needs_classify_and_skips_in_the_landed_lane(job: str) -> None:
    assert "classify" in _needs(job)
    assert NOT_LANDED in JOBS[job]["if"]


def test_validate_artifacts_runs_in_every_lane() -> None:
    job = JOBS["validate-artifacts"]
    assert _needs("validate-artifacts") == ["classify"]
    assert "if" not in job
    strict = [s for s in job["steps"] if s.get("run") == "fr validate artifacts"]
    assert len(strict) == 1
    # Review p2-r1: the strict step must run on a push to main (the landed lane's guarantee,
    # R5) and the lenient one only on a pull request or a queue push.
    assert strict[0]["if"] == (
        "github.event_name != 'pull_request' && !startsWith(github.ref, 'refs/heads/fr-queue/')"
    )
    lenient = [
        s for s in job["steps"] if s.get("run") == "fr validate artifacts --allow-migratable"
    ]
    assert len(lenient) == 1
    assert lenient[0]["if"] == (
        "github.event_name == 'pull_request' || startsWith(github.ref, 'refs/heads/fr-queue/')"
    )


def test_classify_runs_on_the_runners_own_python() -> None:
    """Review p2-r3: every job waits on `classify`, so it installs nothing; the stdlib-only
    script runs on the runner's python3."""
    steps = JOBS["classify"]["steps"]
    assert not any("setup-uv" in str(s.get("uses", "")) for s in steps)
    script = next(s["run"] for s in steps if s.get("id") == "lane")
    assert "python3 scripts/ci_lane.py landed" in script
    assert "python3 scripts/ci_lane.py classify" in script
    assert "uv run" not in script


def test_change_fragment_keeps_its_own_condition() -> None:
    assert JOBS["change-fragment"]["if"] == (f"github.event_name == 'pull_request' && {NOT_LANDED}")


# R7
def test_split_check_saves_the_plan_on_main_as_before() -> None:
    saves = [s for s in JOBS["split-check"]["steps"] if "if" in s]
    assert [s["if"] for s in saves] == [
        "github.event_name == 'push' && github.ref == 'refs/heads/main'",
        "github.event_name == 'push' && github.ref == 'refs/heads/main'",
    ]
    assert saves[1]["with"]["key"] == "test-durations-${{ github.run_id }}"
    caches = [
        s
        for job in JOBS.values()
        for s in job["steps"]
        if "actions/cache/save" in str(s.get("uses", ""))
    ]
    assert caches == [saves[1]]
