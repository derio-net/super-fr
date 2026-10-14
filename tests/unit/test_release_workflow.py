"""`.github/workflows/release.yml` (spec 2026-09-26-version-bump-churn §3.C).

It replaces `auto-tag.yml`: runs on every push to `main` and on a manual
dispatch with an optional `version`, one run at a time, never cancelled, and
drives `scripts/release.py`.
"""

from __future__ import annotations

import re
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


def test_permissions_are_contents_and_issues_write_and_pull_requests_read() -> None:
    """`pull-requests: read` is for `fr release status` (exit-gates R21), which reads the
    merged PRs' gate labels with the workflow token, never the app's."""
    assert _workflow()["permissions"] == {
        "contents": "write",
        "issues": "write",
        "pull-requests": "read",
    }


def test_runs_daily_so_a_final_follows_the_last_gate_pass() -> None:
    """Exit-gates R20: a gate passes with no push to main, so a daily run cuts the final."""
    (entry,) = _on()["schedule"]
    assert re.fullmatch(r"\d+ \d+ \* \* \*", entry["cron"])


def test_release_status_reads_the_forge_with_the_workflow_token() -> None:
    run = next(s for s in _steps() if "scripts/release.py" in str(s.get("run", "")))
    assert run["env"]["FR_RELEASE_STATUS_TOKEN"] == "${{ github.token }}"


def test_checks_out_full_history_and_runs_release_py_with_a_token() -> None:
    steps = _steps()
    checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout["with"]["fetch-depth"] == 0
    assert any(str(s.get("uses", "")).startswith("astral-sh/setup-uv") for s in steps)
    run = next(s for s in steps if "scripts/release.py" in str(s.get("run", "")))
    assert "GH_TOKEN" in run["env"]
    # The dispatch input reaches the script through env, never spliced into the shell.
    assert "inputs.version" not in run["run"]


def test_header_states_both_token_modes_and_the_bypass_actor() -> None:
    header = " ".join(WORKFLOW.read_text().split("\non:", 1)[0].replace("#", " ").split())
    assert "GITHUB_TOKEN" in header
    assert "no CI" in header  # fallback mode: a GITHUB_TOKEN push triggers nothing
    assert "bypass actor" in header
    assert "FR_AUTOMATION_APP_ID" in header
    assert "no-op" in header  # app mode: CI runs and release.yml re-runs as a no-op


def test_app_token_step_is_conditional_and_pinned_to_a_sha() -> None:
    step = next(s for s in _steps() if s.get("id") == "app-token")
    assert step["if"] == "vars.FR_AUTOMATION_APP_ID != ''"
    uses = step["uses"]
    assert uses.startswith("actions/create-github-app-token@")
    assert re.fullmatch(r"[0-9a-f]{40}", uses.split("@", 1)[1])
    assert step["with"]["app-id"] == "${{ vars.FR_AUTOMATION_APP_ID }}"
    assert step["with"]["private-key"] == "${{ secrets.FR_AUTOMATION_APP_KEY }}"


def test_app_token_is_scoped_to_this_repo_with_contents_and_issues_write_only() -> None:
    w = next(s for s in _steps() if s.get("id") == "app-token")["with"]
    assert w["permission-contents"] == "write"
    assert w["permission-issues"] == "write"
    assert w["owner"] == "${{ github.repository_owner }}"
    assert w["repositories"] == "${{ github.event.repository.name }}"
    assert {k for k in w if k.startswith("permission-")} == {
        "permission-contents",
        "permission-issues",
    }


def test_checkout_persists_no_credential() -> None:
    checkout = next(s for s in _steps() if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout["with"]["persist-credentials"] is False


def test_checkout_and_release_step_take_the_app_token_or_the_default() -> None:
    expr = "${{ steps.app-token.outputs.token || github.token }}"
    steps = _steps()
    checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout["with"]["token"] == expr
    run = next(s for s in steps if "scripts/release.py" in str(s.get("run", "")))
    assert run["env"]["GH_TOKEN"] == expr


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
