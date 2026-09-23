"""`.github/workflows/pinned-clis.yml` runs least-privilege and bounded (p5r-f1)."""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "pinned-clis.yml"


def test_the_workflow_token_is_read_only() -> None:
    assert yaml.safe_load(WORKFLOW.read_text())["permissions"] == {"contents": "read"}


def test_every_job_has_a_timeout() -> None:
    jobs = yaml.safe_load(WORKFLOW.read_text())["jobs"]
    assert jobs and all(job.get("timeout-minutes") == 10 for job in jobs.values())
