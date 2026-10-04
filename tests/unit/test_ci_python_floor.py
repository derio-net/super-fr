"""CI tests the Python floor it declares, plus the newest Python, once per push.

gh#940: no workflow pinned an interpreter, so `uv sync` took whatever the
runner had (3.12) and the declared `requires-python` floor (3.11) was never
exercised. The pin is `UV_PYTHON` in the workflow env, not a committed
`.python-version`, so it does not also pin an operator's local runs.

gh#941: `on: [push, pull_request]` ran every check twice on a PR push. A
workflow that gates PRs triggers on `push` to `main` only.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

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


def _version(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split("."))


def test_ci_pins_the_requires_python_floor() -> None:
    assert _workflow("ci.yml").get("env", {}).get("UV_PYTHON") == _floor()


def test_release_suite_runs_on_the_requires_python_floor() -> None:
    # scripts/release.py runs the whole suite on the staged tree before it
    # pushes; that run must see the same interpreter as CI.
    assert _workflow("release.yml").get("env", {}).get("UV_PYTHON") == _floor()


def test_ci_tests_the_floor_and_a_newer_python() -> None:
    job = _workflow("ci.yml")["jobs"]["test"]
    pythons = [str(p) for p in job["strategy"]["matrix"]["python"]]
    assert _floor() in pythons
    assert any(_version(p) > _version(_floor()) for p in pythons), pythons
    # The matrix value only matters if it reaches uv.
    assert job.get("env", {}).get("UV_PYTHON") == "${{ matrix.python }}"


def test_only_the_floor_leg_feeds_coverage() -> None:
    # Two legs uploading coverage-shard-N would collide on the artifact name.
    job = _workflow("ci.yml")["jobs"]["test"]
    upload = next(s for s in job["steps"] if "upload-artifact" in str(s.get("uses", "")))
    assert upload.get("if") == f"matrix.python == '{_floor()}'"


def test_pr_gating_workflows_run_once_per_pr_push() -> None:
    for name in ("ci.yml", "acceptance-report.yml"):
        on = _workflow(name)["on"]
        assert isinstance(on, dict), f"{name}: `on:` must be a mapping, got {on!r}"
        assert "pull_request" in on, name
        assert (on.get("push") or {}).get("branches") == ["main"], (
            f"{name}: push must be scoped to main, or every PR push runs it twice"
        )
