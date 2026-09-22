"""Walking skeleton for `fr triage collect` (plan 2026-09-21-fr-triage, phase 1).

The forge is replaced at the Forge seam — the factory the command uses to build
its forge — by a fake that serves the captured `gh` fixtures. Nothing here
monkeypatches subprocess, and nothing touches a real forge.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from typer.testing import CliRunner

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "triage"


def _load(name: str) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return data


class FixtureForge:
    """A Forge serving the captured super-fr fixtures."""

    def __init__(self) -> None:
        self.issues = _load("super-fr-issues.json")
        self.prs = _load("super-fr-prs.json")

    def list_repos(self, *, owner: str, limit: int) -> list[dict[str, Any]]:
        return [{"name": "super-fr", "isArchived": False}]

    def list_issues(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        assert repo == "derio-net/super-fr"
        return self.issues

    def list_prs(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        assert repo == "derio-net/super-fr"
        return self.prs

    def list_open_prs(self, *, repo: str, limit: int) -> list[dict[str, Any]]:
        assert repo == "derio-net/super-fr"
        return [p for p in self.prs if p.get("state") == "OPEN"]

    def view_issue(self, *, repo: str, number: int) -> dict[str, Any]:
        raise AssertionError("the skeleton never views a single issue")


def test_collect_writes_facts_json_from_the_forge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.commands.triage_cmd as triage_cmd

    monkeypatch.setattr(triage_cmd, "make_forge", FixtureForge)

    result = CliRunner().invoke(
        app, ["triage", "collect", "--repo", "derio-net/super-fr", "--dir", str(tmp_path)]
    )

    assert result.exit_code == 0, result.output
    facts_path = tmp_path / "facts.json"
    assert facts_path.exists()
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    assert facts["schema"] == 2
    assert facts["scope"] == "derio-net--super-fr"
    assert facts["kind"] == "repo"
    collected = {(i["repo"], i["number"]) for i in facts["issues"]}
    for issue in _load("super-fr-issues.json"):
        assert ("derio-net/super-fr", issue["number"]) in collected
