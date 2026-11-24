"""Every flow meets the docs-currency gate (spec 2026-11-11-docs-currency R10, R11)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.own_artifacts

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = REPO_ROOT / "plugins" / "super-fr" / "skills"


@pytest.mark.parametrize("skill", ["fr-goal", "fr-debugging"])
def test_the_delivering_skills_name_fr_docs_check(skill: str) -> None:
    """R10: both skills that end in a PR tell the agent to run the check."""
    assert "fr docs check" in (SKILLS / skill / "SKILL.md").read_text()


def _ci() -> dict:
    import yaml

    return yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text())


def test_ci_runs_fr_docs_check_on_every_pull_request_inside_ci_ok() -> None:
    """R11: the gate no flow can skip. A pull request diffs against its base;
    a push to main and a merge group run it with no base (R6: structure only
    on the default branch, the default branch as base on a merge group)."""
    jobs = _ci()["jobs"]
    job = jobs["docs-check"]
    # Every event, not only pull_request. The one skip is the landed lane (ci-economy R5):
    # a push to main whose sha already passed this whole workflow on an fr-queue/** push.
    assert job["if"] == "needs.classify.outputs.lane != 'landed'"
    steps = job["steps"]
    checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout@"))
    assert checkout["with"]["fetch-depth"] == 0
    runs = {s.get("if"): s["run"] for s in steps if "run" in s}
    # The base reaches the script through env, never interpolated into it (gh#1289).
    pr_step = next(s for s in steps if s.get("if") == "github.event_name == 'pull_request'")
    assert pr_step["env"] == {"BASE_REF": "${{ github.base_ref }}"}
    assert runs["github.event_name == 'pull_request'"] == (
        'uv run fr docs check --base "origin/$BASE_REF"'
    )
    assert runs["github.event_name != 'pull_request'"] == "uv run fr docs check"
    assert "docs-check" in jobs["ci-ok"]["needs"]


def test_docs_check_uses_change_fragments_pins() -> None:
    jobs = _ci()["jobs"]

    def uses(name: str) -> list[str]:
        return [s["uses"] for s in jobs[name]["steps"] if "uses" in s]

    assert uses("docs-check") == uses("change-fragment")
