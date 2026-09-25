"""`HerdrRunner` — the run-unit runner over the herdr CLI (spec 2026-09-25-triage-batches
§3.C, Test Plan 6).

The herdr CLI is faked at `fr_herdr.runner._run_herdr`, the runner's one
subprocess seam; its answers are the fixtures under `tests/fixtures/herdr/`
(see the README there for which are live captures). No herdr session is driven.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from fr_dispatch.testing import check_constructible, check_run_unit_contract, run_item
from fr_herdr import runner as herdr_runner
from fr_herdr.runner import HerdrRunner, agent_name

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "herdr"
AGENT_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


def _fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return data


class _Herdr:
    """Records every herdr argv; answers tab create/list from the fixtures."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> dict[str, Any]:
        self.calls.append(list(args))
        if args[:2] == ["tab", "create"]:
            return _fixture("tab-create.json")
        if args[:2] == ["tab", "list"]:
            return _fixture("tab-list.json")
        return {}

    def text(self) -> str:
        return "\n".join(" ".join(c) for c in self.calls)


@pytest.fixture
def herdr(monkeypatch: pytest.MonkeyPatch) -> _Herdr:
    fake = _Herdr()
    monkeypatch.setattr(herdr_runner, "_run_herdr", fake)
    monkeypatch.setattr(herdr_runner.shutil, "which", lambda name: "/usr/local/bin/herdr")
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setenv("HERDR_WORKSPACE_ID", "w2")
    return fake


def _item(**kw: Any) -> Any:
    return run_item("example-org/alpha", "batch-lifecycle", checkout="/work/alpha", **kw)


# -------------------------------------------------------------- construction


def test_from_env_reads_the_workspace_id(herdr: _Herdr) -> None:
    runner = HerdrRunner.from_env()
    assert runner.workspace_id == "w2"
    assert (runner.name, runner.slot_budget(), runner.refresh()) == ("herdr", 1, None)
    assert runner.capabilities == frozenset({"git", "tests", "scm", "devcontainer"})


# ------------------------------------------------------------------ preflight


def test_preflight_passes_inside_a_herdr_session(herdr: _Herdr) -> None:
    assert HerdrRunner.from_env().preflight([_item()]) is None


def test_preflight_refuses_outside_a_herdr_session(
    herdr: _Herdr, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HERDR_ENV")
    message = HerdrRunner.from_env().preflight([_item()])
    assert message is not None and "HERDR_ENV" in message


def test_preflight_refuses_without_herdr_on_path(
    herdr: _Herdr, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(herdr_runner.shutil, "which", lambda name: None)
    message = HerdrRunner.from_env().preflight([_item()])
    assert message is not None and "PATH" in message


def test_preflight_refuses_without_a_workspace_id(
    herdr: _Herdr, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HERDR_WORKSPACE_ID")
    message = HerdrRunner.from_env().preflight([_item()])
    assert message is not None and "HERDR_WORKSPACE_ID" in message


# ------------------------------------------------------------------ routing


def test_can_dispatch_takes_a_run_item_for_a_known_harness(herdr: _Herdr) -> None:
    runner = HerdrRunner.from_env()
    assert runner.can_dispatch(_item())
    assert not runner.can_dispatch(_item(harness="nonesuch"))


def test_can_dispatch_refuses_a_phase_item(herdr: _Herdr) -> None:
    from fr_dispatch.work_item import WorkItem

    phase = WorkItem(
        id="example-org/alpha/spec/plan/phase/1",
        unit="phase",
        workflow="fr-goal",
        repo="example-org/alpha",
        parent="example-org/alpha/spec/plan",
        inputs=(),
        payload={"harness": "claude"},
    )
    assert not HerdrRunner.from_env().can_dispatch(phase)


# ------------------------------------------------------------------ dispatch


def test_dispatch_creates_the_tab_starts_the_agent_then_prompts_it(herdr: _Herdr) -> None:
    item = _item(model="claude-opus-5-5", brief="/fr-goal Separate lifecycles")

    handle = HerdrRunner.from_env().dispatch(item)

    create, start, prompt = herdr.calls
    assert create == [
        "tab", "create", "--workspace", "w2", "--cwd", "/work/alpha",
        "--label", item.id, "--no-focus",
    ]  # fmt: skip
    name = agent_name(item.id)
    assert start == [
        "agent", "start", name, "--kind", "claude", "--pane", "w2:p1K",
        "--", "--model", "claude-opus-5-5",
    ]  # fmt: skip
    assert prompt == ["agent", "prompt", name, "/fr-goal Separate lifecycles"]
    assert handle == "w2:p1K"


def test_a_failed_tab_create_starts_nothing(herdr: _Herdr, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(args: list[str]) -> dict[str, Any]:
        herdr.calls.append(list(args))
        raise herdr_runner.HerdrError("herdr tab create failed: no such workspace")

    monkeypatch.setattr(herdr_runner, "_run_herdr", broken)
    with pytest.raises(herdr_runner.HerdrError, match="no such workspace"):
        HerdrRunner.from_env().dispatch(_item())
    assert len(herdr.calls) == 1


# ------------------------------------------------------------------ identity


def test_the_agent_name_fits_herdrs_pattern_for_a_40_character_batch_id() -> None:
    item_id = "example-org/alpha/run/batch-" + "a" * 40
    name = agent_name(item_id)
    assert AGENT_NAME.match(name), name
    assert name.startswith("b-" + "a" * 20 + "-")


def test_the_same_batch_id_in_two_repos_gets_different_labels_and_names() -> None:
    one = run_item("example-org/alpha", "batch-lifecycle")
    two = run_item("example-org/beta", "batch-lifecycle")
    assert one.id != two.id  # the tab label is the item id
    assert agent_name(one.id) != agent_name(two.id)


def test_existing_dispatches_matches_live_tabs_by_label(herdr: _Herdr) -> None:
    live = run_item("example-org/alpha", "batch-lifecycle")
    idle = run_item("example-org/alpha", "batch-docs")

    held = HerdrRunner.from_env().existing_dispatches([live, idle])

    assert held == {live.id}
    assert herdr.calls == [["tab", "list", "--workspace", "w2"]]


# ------------------------------------------------------------------ contract


def test_the_runner_passes_the_run_unit_contract(herdr: _Herdr) -> None:
    check_constructible(HerdrRunner)
    check_run_unit_contract(HerdrRunner.from_env(), _item(), sent=herdr.text)
