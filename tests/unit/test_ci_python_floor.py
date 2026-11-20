"""CI tests one Python, the floor it declares (#1589); the whole base is on 3.14.

gh#940: no workflow pinned an interpreter, so `uv sync` took whatever the
runner had (3.12) and the declared `requires-python` floor (3.11) was never
exercised. The pin is `UV_PYTHON` in the workflow env, not a committed
`.python-version`, so it does not also pin an operator's local runs.

gh#1589: the second leg (3.11 and 3.14) doubled the PR test cost for a
version-specific break that no longer exists once the floor is 3.14. CI has one
leg, inheriting the workflow's `UV_PYTHON`, and every shard feeds coverage.

gh#941: `on: [push, pull_request]` ran every check twice on a PR push. A
workflow that gates PRs triggers on `push` to `main` only.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"


def _floor() -> str:
    spec = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]["requires-python"]
    m = re.fullmatch(r">=\s*(\d+\.\d+)", spec.strip())
    assert m, f"requires-python {spec!r} is not a plain >=X.Y floor"
    return m.group(1)


def _workflow(name: str) -> dict[str, Any]:
    doc = yaml.safe_load((WORKFLOWS / name).read_text())
    # PyYAML parses the bare key `on` as the boolean True.
    if True in doc:
        doc["on"] = doc.pop(True)
    return doc


def test_ci_pins_the_requires_python_floor() -> None:
    assert _workflow("ci.yml").get("env", {}).get("UV_PYTHON") == _floor()


def test_release_suite_runs_on_the_requires_python_floor() -> None:
    # scripts/release.py runs the whole suite on the staged tree before it
    # pushes; that run must see the same interpreter as CI.
    assert _workflow("release.yml").get("env", {}).get("UV_PYTHON") == _floor()


@pytest.mark.parametrize(
    ("workflow", "suite_jobs"), [("ci.yml", {"test", "collect"}), ("release.yml", {"test"})]
)
def test_one_python_the_floor(workflow: str, suite_jobs: set[str]) -> None:
    # R3/R6: no job picks another interpreter, so every job inherits the
    # workflow's floor (#1589). setup-uv's `with: python-version` is the
    # override this repo's own setup action offers, so it is refused too.
    jobs = _workflow(workflow)["jobs"]
    assert suite_jobs <= set(jobs)
    for name, job in jobs.items():
        assert "python" not in (job.get("strategy") or {}).get("matrix", {}), name
        assert "UV_PYTHON" not in (job.get("env") or {}), name
        for step in job.get("steps", []):
            assert "setup-python" not in str(step.get("uses", "")), name
            assert "UV_PYTHON" not in (step.get("env") or {}), name
            assert "python-version" not in (step.get("with") or {}), name


def test_every_shard_feeds_coverage() -> None:
    job = _workflow("ci.yml")["jobs"]["test"]
    upload = next(
        s
        for s in job["steps"]
        if "upload-artifact" in str(s.get("uses", ""))
        and str(s.get("with", {}).get("name", "")).startswith("coverage-shard-")
    )
    assert "if" not in upload
    pytest_step = next(s for s in job["steps"] if "uv run pytest" in str(s.get("run", "")))
    assert "--cov --cov-report=" in pytest_step["run"]
    assert "cov_args" not in yaml.safe_dump(job)


def test_the_floor_is_3_14_everywhere() -> None:
    assert _floor() == "3.14"
    root = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert root["tool"]["ruff"]["target-version"] == "py314"
    assert root["tool"]["mypy"]["python_version"] == "3.14"
    members = sorted((REPO / "packages").glob("*/pyproject.toml"))
    assert members
    for path in members:
        spec = tomllib.loads(path.read_text())["project"]["requires-python"]
        assert spec == f">={_floor()}", path


def test_pr_gating_workflows_run_once_per_pr_push() -> None:
    for name in ("ci.yml", "acceptance-report.yml"):
        on = _workflow(name)["on"]
        assert isinstance(on, dict), f"{name}: `on:` must be a mapping, got {on!r}"
        assert "pull_request" in on, name
        assert (on.get("push") or {}).get("branches") == ["main"], (
            f"{name}: push must be scoped to main, or every PR push runs it twice"
        )
