"""CI runs on merge groups (spec 2026-10-11-merge-train-safety §D "CI", R15): a repo whose
base requires a merge queue builds each group on a `gh-readonly-queue/...` branch, and a
required check that never runs on it leaves the group unmerged. `ci.yml` and
`acceptance-report.yml` both trigger on `merge_group`; `change-fragment` stays
pull-request-only (the PR already passed it, and `ci-ok` treats a skip as a pass)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def _load(name: str) -> dict[str, Any]:
    data = yaml.safe_load((WORKFLOWS / name).read_text("utf-8"))
    assert isinstance(data, dict)
    return data


def _on(workflow: dict[str, Any]) -> dict[str, Any]:
    # YAML 1.1 reads the bare key `on` as the boolean True.
    return workflow.get("on", workflow.get(True))


@pytest.mark.parametrize("name", ["ci.yml", "acceptance-report.yml"])
def test_the_workflow_triggers_on_merge_group(name: str) -> None:
    assert "merge_group" in _on(_load(name))


@pytest.mark.parametrize("name", ["ci.yml", "acceptance-report.yml"])
def test_the_pull_request_and_push_triggers_are_kept(name: str) -> None:
    on = _on(_load(name))
    assert "pull_request" in on and on["push"]["branches"] == ["main"]


def test_change_fragment_stays_pull_request_only() -> None:
    job = _load("ci.yml")["jobs"]["change-fragment"]
    assert job["if"] == "github.event_name == 'pull_request'"


def test_ci_ok_treats_a_skipped_change_fragment_as_a_pass() -> None:
    ci_ok = _load("ci.yml")["jobs"]["ci-ok"]
    assert "change-fragment" in ci_ok["needs"] and ci_ok["if"] == "always()"
    assert "skipped" in str(ci_ok["steps"])
