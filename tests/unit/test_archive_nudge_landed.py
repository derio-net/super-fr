"""The "plan complete — run fr archive" nudges need landed evidence (#544).

Spec `2026-09-23-archive-merge-evidence-design.md` §3.C, Test Plan §5 item 7:
the `fr status <plan>` nudge, its JSON `archive_ready` field and `fr apply`'s
nudge share `archive_gate`, so they stay silent for a plan that is complete
only on the branch and fire once it has landed on `origin/main`.

Every repo is a real temp git repo whose origin is a FILE PATH, and
`fr.archive._fetch` is monkeypatched, so nothing touches a network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import apply_cmd, status_cmd
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.test_merge_evidence import (
    PLANS_REL,
    _add_remote,
    _commit,
    _init,
    _publish,
    _write_plan,
    stub_fetch,
)

NAME = "2026-06-01-done"
NUDGE = "plan complete — run `fr archive"


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    return stub_fetch(monkeypatch)


def _repo(tmp_path: Path, *, landed: bool, names: tuple[str, ...] = (NAME,)) -> Path:
    """Locally complete plan(s), published to origin/main only when ``landed``."""
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _publish(repo)
    for name in names:
        _write_plan(repo, name, [("agentic", True), ("manual", True)])
    _commit(repo, "complete plans")
    if landed:
        _publish(repo)
    return repo


def _invoke(monkeypatch: pytest.MonkeyPatch, repo: Path, argv: list[str]):
    gh = FakeGhClient()
    monkeypatch.setattr(status_cmd, "_make_gh_client", lambda: gh)
    monkeypatch.setattr(apply_cmd, "_make_gh_client", lambda: gh)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("VK_REPO_ROOT", str(repo))
    return CliRunner().invoke(app, argv)


def _archive_ready(output: str) -> bool:
    return json.loads(output)["plans"][0]["archive_ready"]


@pytest.mark.parametrize("landed", [False, True])
def test_status_nudge_fires_only_once_the_plan_has_landed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, landed: bool
) -> None:
    repo = _repo(tmp_path, landed=landed)
    result = _invoke(monkeypatch, repo, ["status", str(PLANS_REL / NAME)])
    assert result.exit_code == 0, result.output
    assert (NUDGE in result.output) is landed, result.output


@pytest.mark.parametrize("landed", [False, True])
def test_status_json_archive_ready_follows_landed_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, landed: bool
) -> None:
    repo = _repo(tmp_path, landed=landed)
    result = _invoke(monkeypatch, repo, ["status", str(PLANS_REL / NAME), "--format", "json"])
    assert result.exit_code == 0, result.output
    assert _archive_ready(result.output) is landed


@pytest.mark.parametrize("landed", [False, True])
def test_apply_nudge_fires_only_once_the_plan_has_landed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, landed: bool
) -> None:
    repo = _repo(tmp_path, landed=landed)
    result = _invoke(monkeypatch, repo, ["apply", str(PLANS_REL / NAME)])
    assert result.exit_code == 0, result.output
    assert (NUDGE in result.output) is landed, result.output


def test_status_single_plan_fetches_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _hermetic: list[str]
) -> None:
    repo = _repo(tmp_path, landed=True)
    result = _invoke(monkeypatch, repo, ["status", str(PLANS_REL / NAME), "--format", "json"])
    assert result.exit_code == 0, result.output
    assert _hermetic == ["origin"]


def test_apply_all_computes_merge_evidence_once_per_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _hermetic: list[str]
) -> None:
    repo = _repo(tmp_path, landed=True, names=("2026-06-01-a", "2026-06-02-b"))
    result = _invoke(monkeypatch, repo, ["apply", "--all"])
    assert result.exit_code == 0, result.output
    assert result.output.count(NUDGE) == 2, result.output
    assert _hermetic == ["origin"]
