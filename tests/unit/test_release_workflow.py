"""`.github/workflows/release.yml` (spec 2026-09-26-version-bump-churn §3.C).

It replaces `auto-tag.yml`: runs on every push to `main` and on a manual
dispatch with an optional `version`, one run at a time, never cancelled, and
drives `scripts/release.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "release.yml"


def _workflow() -> dict[Any, Any]:
    data = yaml.safe_load(WORKFLOW.read_text())
    assert isinstance(data, dict)
    return data


def _on() -> dict[str, Any]:
    data = _workflow()
    # PyYAML reads the bare key `on` as boolean True.
    on = data.get("on", data.get(True))
    assert isinstance(on, dict)
    return on


def _steps() -> list[dict[str, Any]]:
    return [step for job in _workflow()["jobs"].values() for step in job["steps"]]


def test_triggers_on_push_to_main_with_no_path_filter() -> None:
    push = _on()["push"]
    assert push["branches"] == ["main"]
    assert "paths" not in push  # every merge may carry a fragment


def test_manual_dispatch_takes_an_optional_version() -> None:
    inputs = _on()["workflow_dispatch"]["inputs"]
    assert inputs["version"]["required"] is False


def test_runs_one_at_a_time_and_is_never_cancelled() -> None:
    assert _workflow()["concurrency"] == {"group": "release", "cancel-in-progress": False}


def test_permissions_are_contents_and_issues_write() -> None:
    assert _workflow()["permissions"] == {"contents": "write", "issues": "write"}


def test_checks_out_full_history_and_runs_release_py_with_a_token() -> None:
    steps = _steps()
    checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout["with"]["fetch-depth"] == 0
    assert any(str(s.get("uses", "")).startswith("astral-sh/setup-uv") for s in steps)
    run = next(s for s in steps if "scripts/release.py" in str(s.get("run", "")))
    assert "GH_TOKEN" in run["env"]
    # The dispatch input reaches the script through env, never spliced into the shell.
    assert "inputs.version" not in run["run"]


def test_header_states_the_no_ci_property_and_the_bypass_actor() -> None:
    header = WORKFLOW.read_text().split("\non:", 1)[0]
    assert "GITHUB_TOKEN" in header
    assert "bypass actor" in header


def test_header_no_longer_claims_the_staged_diff_check_is_enough() -> None:
    """#854: the diff check proves which lines changed, not how the code behaves
    at the new number — 5.0.0 shipped refusing its own plans under that claim."""
    header = WORKFLOW.read_text().split("\non:", 1)[0]
    assert "safe only because release.py verifies the staged diff" not in " ".join(header.split())
    assert "tests the staged tree" in " ".join(header.replace("#", " ").split())


def test_the_release_job_has_a_budget_for_the_full_suite() -> None:
    budget = yaml.safe_load((REPO / ".github" / "ci-budget.yaml").read_text())
    assert budget["workflows"]["release.yml"]["budget_seconds"] >= 900


def test_auto_tag_workflow_is_gone() -> None:
    assert not (REPO / ".github" / "workflows" / "auto-tag.yml").exists()
