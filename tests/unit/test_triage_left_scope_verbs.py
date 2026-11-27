"""`batch focus` refuses and `batch cancel --orphaned` retires a left-scope batch
(2026-11-27-closeout-state R7, R8)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.commands import triage_batch_cmd
from fr.triage.model import Facts, Truncation, load_judgements
from typer.testing import CliRunner

REPO = "example-org/widgets"
DISPATCH = (
    "    events:\n      - {kind: dispatch, at: 2026-10-01T10:00:00Z, runner: fake, handle: h,"
    " branch: feat/batch-a}\n"
)


def _state(tmp_path: Path, repos: list[str], *, truncated: bool = False) -> Path:
    (tmp_path / "judgements.yaml").write_text(
        "schema: 3\ntiers: [{n: 1, title: Now}]\nissues:\n  'other#1': {tier: 1}\n"
        "batches:\n  - id: a\n    title: A\n    ids: ['other#1']\n" + DISPATCH,
        "utf-8",
    )
    facts = Facts(
        viewer="op",
        scope="example-org--widgets",
        kind="repo",
        collected_at="2026-10-02T12:00:00+00:00",
        repos=repos,
        issues=[],
        warnings=(
            [Truncation(source="repos", target="example-org", limit=100)] if truncated else []
        ),
    )
    (tmp_path / "facts.json").write_text(json.dumps(facts.to_json()), "utf-8")
    return tmp_path


def _run(tmp_path: Path, verb: str, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app, ["triage", "batch", verb, "a", *args, "--repo", REPO, "--dir", str(tmp_path)]
    )
    return result.exit_code, " ".join(result.output.split())


@pytest.fixture
def no_forge(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def boom(url: str) -> Any:
        calls.append(url)
        raise AssertionError("no forge client may be made")

    def no_clone(*a: Any, **kw: Any) -> Any:
        calls.append("checkout")
        raise AssertionError("no checkout may be opened")

    monkeypatch.setattr(triage_batch_cmd, "make_client", boom)
    for name in ("make_checkout", "_open_checkout", "_tracking_gate"):
        if hasattr(triage_batch_cmd, name):
            monkeypatch.setattr(triage_batch_cmd, name, no_clone)
    return calls


def _events(tmp_path: Path) -> list[str]:
    return [e.kind for e in load_judgements(tmp_path / "judgements.yaml").batches[0].events]


def test_focus_refuses_a_left_scope_batch_naming_the_cancel(tmp_path: Path) -> None:
    code, out = _run(_state(tmp_path, ["example-org/other-only"]), "focus")
    assert code == 2, out
    assert "left this scope" in out
    assert "fr triage batch cancel a --orphaned" in out


def test_focus_does_not_refuse_for_leaving_when_the_repo_list_was_truncated(
    tmp_path: Path,
) -> None:
    _, out = _run(_state(tmp_path, ["example-org/other-only"], truncated=True), "focus")
    assert "left this scope" not in out


def test_orphaned_is_refused_when_the_repo_list_was_truncated(
    tmp_path: Path, no_forge: list[str]
) -> None:
    state = _state(tmp_path, ["example-org/other-only"], truncated=True)
    code, out = _run(state, "cancel", "--orphaned")
    assert code == 2 and "not left-scope" in out
    assert _events(tmp_path) == ["dispatch"]


def test_cancel_without_the_flag_names_it(tmp_path: Path, no_forge: list[str]) -> None:
    code, out = _run(_state(tmp_path, ["example-org/other-only"]), "cancel")
    assert code == 2, out
    assert "--orphaned" in out and "left this scope" in out
    assert _events(tmp_path) == ["dispatch"]


def test_the_orphaned_plan_writes_nothing(tmp_path: Path, no_forge: list[str]) -> None:
    code, out = _run(_state(tmp_path, ["example-org/other-only"]), "cancel", "--orphaned")
    assert code == 0, out
    assert "nothing on the forge is withdrawn" in out
    assert "cancel batch a (left-scope)" in out
    assert _events(tmp_path) == ["dispatch"]
    assert no_forge == []  # neither a client nor a checkout was made


def test_orphaned_yes_appends_only_the_cancel_event(tmp_path: Path, no_forge: list[str]) -> None:
    state = _state(tmp_path, ["example-org/other-only"])
    code, out = _run(state, "cancel", "--orphaned", "--yes")
    assert code == 0, out
    assert _events(tmp_path) == ["dispatch", "cancel"]
    assert no_forge == []
    code, out = _run(state, "cancel", "--orphaned", "--yes")
    assert code == 2 and "not left-scope" in out  # the batch now derives cancelled
    raw = yaml.safe_load((tmp_path / "judgements.yaml").read_text("utf-8"))
    assert [e["kind"] for e in raw["batches"][0]["events"]] == ["dispatch", "cancel"]


def test_orphaned_on_a_batch_whose_repo_is_present_is_refused(
    tmp_path: Path, no_forge: list[str]
) -> None:
    code, out = _run(_state(tmp_path, ["example-org/other"]), "cancel", "--orphaned")
    assert code == 2, out
    assert "--orphaned" in out
