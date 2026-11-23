"""This repo's own CI runs on the wave merge queue's slot branches (spec
2026-11-19-wave-merge-queue R7, R21): `ci.yml` and `acceptance-report.yml` trigger on pushes
to `fr-queue/**`, and `--allow-migratable` is used only on pull requests and on those
pushes, never on `main`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
QUEUE_BRANCHES = "fr-queue/**"


def _load(name: str) -> dict[str, Any]:
    doc = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    return doc


def _triggers(doc: dict[str, Any]) -> dict[str, Any]:
    return doc.get("on") or doc.get(True)  # YAML 1.1 reads a bare `on` as True


@pytest.mark.parametrize("name", ["ci.yml", "acceptance-report.yml"])
def test_the_workflow_runs_on_pushes_to_the_queues_slot_branches(name: str) -> None:
    branches = _triggers(_load(name))["push"]["branches"]
    assert QUEUE_BRANCHES in branches and "main" in branches


@pytest.mark.parametrize("name", ["ci.yml", "acceptance-report.yml"])
def test_the_push_trigger_is_never_unscoped(name: str) -> None:
    """An unscoped push overlaps pull_request and ran every PR push twice (#941)."""
    assert set(_triggers(_load(name))["push"]["branches"]) == {"main", QUEUE_BRANCHES}


def test_allow_migratable_is_used_only_where_a_stale_artifact_is_expected() -> None:
    uses: list[tuple[str, str, str]] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job, body in (doc.get("jobs") or {}).items():
            for step in body.get("steps") or []:
                if "--allow-migratable" in str(step.get("run") or ""):
                    uses.append((path.name, job, str(step.get("if") or "")))
    assert [(w, j) for w, j, _ in uses] == [("ci.yml", "validate-artifacts")]
    condition = uses[0][2]
    assert "pull_request" in condition and "refs/heads/fr-queue/" in condition
    assert "main" not in condition


def test_the_default_branch_keeps_the_strict_check() -> None:
    steps = _load("ci.yml")["jobs"]["validate-artifacts"]["steps"]
    strict = [s for s in steps if str(s.get("run") or "").strip() == "fr validate artifacts"]
    assert len(strict) == 1
    condition = str(strict[0]["if"])
    assert (
        "!= 'pull_request'" in condition
        and "!startsWith(github.ref, 'refs/heads/fr-queue/')" in condition
    )
