"""CI workflow hygiene (gh#1288, gh#1289).

gh#1289: an expression interpolated straight into a ``run:`` script is pasted into the
shell source before bash parses it, so a value that carries shell syntax runs as code.
The ``github.*`` contexts a pull request can influence go through an ``env:`` variable
instead, which the shell reads as data.

gh#1288: a job with no ``timeout-minutes`` runs for GitHub's default of six hours when it
hangs, holding a runner and the ``ci-ok`` result the whole time. Every ``ci.yml`` job
states its own bound.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"

# The github.* contexts whose value a pull request's author can shape (a branch name,
# a title, a body, a commit message). `github.base_ref` names an existing branch of
# this repo, so it is low risk, but it is the case gh#1289 found and it costs nothing
# to route through env like the rest.
_PR_SHAPED = re.compile(r"\$\{\{\s*github\.(base_ref|head_ref|event\.)")


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text("utf-8"))
    assert isinstance(data, dict)
    return data


def _steps(workflow: dict[str, Any]):
    for job_id, job in (workflow.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            yield job_id, step


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_no_pr_shaped_expression_is_interpolated_into_a_run_script(path: Path) -> None:
    offenders = [
        f"{job_id}: {step.get('name') or step['run'].splitlines()[0]}"
        for job_id, step in _steps(_load(path))
        if isinstance(step.get("run"), str) and _PR_SHAPED.search(step["run"])
    ]
    assert not offenders, (
        f"{path.name}: move these expressions into the step's env: and read the "
        f"variable in the script: {offenders}"
    )


def test_every_ci_job_has_a_timeout() -> None:
    jobs = _load(WORKFLOWS / "ci.yml")["jobs"]
    missing = [job_id for job_id, job in jobs.items() if "timeout-minutes" not in job]
    assert not missing, f"ci.yml jobs with no timeout-minutes: {missing}"
