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
        self.workspaces: dict[str, Any] = {}
        self.listing: dict[str, Any] = {}

    def __call__(self, args: list[str]) -> dict[str, Any]:
        self.calls.append(list(args))
        if args[:2] == ["tab", "create"]:
            return _fixture("tab-create.json")
        if args[:2] == ["tab", "list"]:
            if self.listing:
                return self.listing
            return _fixture("tab-list.json")
        if args[:2] == ["workspace", "list"]:
            return self.workspaces or _fixture("workspace-list.json")
        if args[:2] == ["workspace", "create"]:
            return _fixture("workspace-create.json")
        if args[:2] == ["tab", "rename"]:
            return _fixture("tab-rename.json")
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


# ------------------------------------------------------------ live fixtures


def test_the_live_captured_fixtures_have_herdrs_result_types() -> None:
    assert _fixture("workspace-list.json")["result"]["type"] == "workspace_list"
    assert _fixture("tab-list-all.json")["result"]["type"] == "tab_list"
    assert _fixture("workspace-create.json")["result"]["type"] == "workspace_created"
    tabs = _fixture("tab-list-all.json")["result"]["tabs"]
    assert len({t["workspace_id"] for t in tabs}) > 1


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


@pytest.mark.parametrize("failing", ["start", "prompt"])
def test_a_failure_after_tab_create_closes_the_tab_and_reraises(
    herdr: _Herdr, monkeypatch: pytest.MonkeyPatch, failing: str
) -> None:
    """Review r2p-f9: a labelled tab left behind would read as a live dispatch
    to `existing_dispatches` forever, so the runner closes what it opened."""

    def flaky(args: list[str]) -> dict[str, Any]:
        if args[:2] == ["agent", failing]:
            herdr.calls.append(list(args))
            raise herdr_runner.HerdrError(f"herdr agent {failing} failed: boom")
        return herdr(args)

    monkeypatch.setattr(herdr_runner, "_run_herdr", flaky)
    with pytest.raises(herdr_runner.HerdrError, match=f"agent {failing} failed"):
        HerdrRunner.from_env().dispatch(_item())
    assert herdr.calls[-1] == ["tab", "close", "w2:t1H"]


def test_a_failed_tab_close_does_not_mask_the_original_error(
    herdr: _Herdr, monkeypatch: pytest.MonkeyPatch
) -> None:
    def flaky(args: list[str]) -> dict[str, Any]:
        herdr.calls.append(list(args))
        if args[:2] == ["tab", "create"]:
            return _fixture("tab-create.json")
        if args[:2] == ["tab", "close"]:
            raise herdr_runner.HerdrError("herdr tab close failed: gone")
        raise herdr_runner.HerdrError("herdr agent start failed: boom")

    monkeypatch.setattr(herdr_runner, "_run_herdr", flaky)
    with pytest.raises(herdr_runner.HerdrError, match="agent start failed"):
        HerdrRunner.from_env().dispatch(_item())
    assert ["tab", "close", "w2:t1H"] in herdr.calls


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
    assert herdr.calls == [["tab", "list"]]


def test_existing_dispatches_finds_a_tab_in_any_workspace(herdr: _Herdr) -> None:
    tabs = _fixture("tab-list-all.json")["result"]["tabs"]
    elsewhere = next(t for t in tabs if t["workspace_id"] != "w2")
    item = _item()
    relabelled = {"result": {"type": "tab_list", "tabs": [{**elsewhere, "label": item.id}]}}
    herdr.listing = relabelled
    assert HerdrRunner.from_env().existing_dispatches([item]) == {item.id}


# --------------------------------------------------------------------- groups


def _grouped(**kw: Any) -> Any:
    return _item(group="drive-wave-1", **kw)


def _ws(label: str, wid: str) -> dict[str, Any]:
    return {
        "result": {"type": "workspace_list", "workspaces": [{"label": label, "workspace_id": wid}]}
    }


def test_a_group_naming_an_existing_workspace_opens_a_tab_in_it(herdr: _Herdr) -> None:
    herdr.workspaces = _ws("drive-wave-1", "w9")
    HerdrRunner.from_env().dispatch(_grouped(model="m", brief="b"))
    text = herdr.text()
    assert "tab create --workspace w9 --cwd /work/alpha" in text
    assert "workspace create" not in text


def test_a_group_with_no_workspace_creates_one_and_uses_its_root_pane(herdr: _Herdr) -> None:
    item = _grouped(model="m", brief="b")
    handle = HerdrRunner.from_env().dispatch(item)
    assert [
        "workspace", "create", "--label", "drive-wave-1", "--cwd", "/work/alpha", "--no-focus",
    ] in herdr.calls  # fmt: skip
    assert ["tab", "rename", "w2H:t1", item.id] in herdr.calls
    assert not any(c[:2] == ["tab", "create"] for c in herdr.calls)
    start = next(c for c in herdr.calls if c[:2] == ["agent", "start"])
    assert start[start.index("--pane") + 1] == "w2H:p1"
    assert handle == "w2H:p1"


@pytest.mark.parametrize("failing", [["agent", "start"], ["tab", "rename"]])
def test_a_failure_after_workspace_create_closes_the_workspace(
    herdr: _Herdr, monkeypatch: pytest.MonkeyPatch, failing: list[str]
) -> None:
    def flaky(args: list[str]) -> dict[str, Any]:
        if args[:2] == failing:
            herdr.calls.append(list(args))
            raise herdr_runner.HerdrError("boom")
        return herdr(args)

    monkeypatch.setattr(herdr_runner, "_run_herdr", flaky)
    with pytest.raises(herdr_runner.HerdrError, match="boom"):
        HerdrRunner.from_env().dispatch(_grouped(model="m", brief="b"))
    assert herdr.calls[-1] == ["workspace", "close", "w2H"]


def test_without_a_group_the_runners_own_workspace_is_used(herdr: _Herdr) -> None:
    HerdrRunner.from_env().dispatch(_item(model="m", brief="b"))
    assert herdr.calls[0][:4] == ["tab", "create", "--workspace", "w2"]
    assert not any(c[0] == "workspace" for c in herdr.calls)


def test_preflight_needs_no_workspace_id_when_every_item_has_a_group(
    herdr: _Herdr, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HERDR_WORKSPACE_ID")
    runner = HerdrRunner.from_env()
    assert runner.preflight([_grouped()]) is None
    message = runner.preflight([_grouped(), _item()])
    assert message is not None and "HERDR_WORKSPACE_ID" in message


# ------------------------------------------------------------------ contract


def test_the_runner_passes_the_run_unit_contract(herdr: _Herdr) -> None:
    check_constructible(HerdrRunner)
    check_run_unit_contract(HerdrRunner.from_env(), _item(), sent=herdr.text)


# ---------------------------------------------------------------------- close


def _tabs(*tabs: tuple[str, str, str, str]) -> dict[str, Any]:
    """A tab list of `(tab_id, workspace_id, label, agent_status)`."""
    return {
        "result": {
            "type": "tab_list",
            "tabs": [
                {"tab_id": t, "workspace_id": w, "label": lbl, "agent_status": st}
                for t, w, lbl, st in tabs
            ],
        }
    }


def _closes(herdr: _Herdr) -> list[list[str]]:
    return [c for c in herdr.calls if c[1:2] == ["close"]]


def test_close_is_absent_when_no_tab_carries_the_item_id(herdr: _Herdr) -> None:
    herdr.listing = _tabs(("w2:t1", "w2", "other", "idle"))
    assert HerdrRunner.from_env().close(_item()) == "absent"
    assert _closes(herdr) == []


@pytest.mark.parametrize("status", ["working", "blocked"])
def test_close_is_busy_for_a_working_or_blocked_tab_and_closes_nothing(
    herdr: _Herdr, status: str
) -> None:
    item = _item()
    herdr.listing = _tabs(("w9:t1", "w9", item.id, "idle"), ("w9:t2", "w9", item.id, status))
    assert HerdrRunner.from_env().close(item) == "busy"
    assert _closes(herdr) == []


@pytest.mark.parametrize("status", ["idle", "done", "unknown"])
def test_close_closes_a_settled_tab_by_id(herdr: _Herdr, status: str) -> None:
    item = _item()
    herdr.listing = _tabs(("w2:t7", "w2", item.id, status), ("w2:t8", "w2", "other", "idle"))
    assert HerdrRunner.from_env().close(item) == "closed"
    assert _closes(herdr) == [["tab", "close", "w2:t7"]]


def test_close_closes_the_group_workspace_of_a_lone_tab(herdr: _Herdr) -> None:
    item = _grouped()
    herdr.listing = _tabs(("w9:t1", "w9", item.id, "idle"))
    herdr.workspaces = _ws("drive-wave-1", "w9")
    assert HerdrRunner.from_env().close(item) == "closed"
    assert _closes(herdr) == [["workspace", "close", "w9"]]


def test_close_never_closes_the_runners_own_workspace(herdr: _Herdr) -> None:
    item = _grouped()
    herdr.listing = _tabs(("w2:t1", "w2", item.id, "idle"))
    herdr.workspaces = _ws("drive-wave-1", "w2")
    assert HerdrRunner.from_env().close(item) == "closed"
    assert _closes(herdr) == [["tab", "close", "w2:t1"]]


def test_close_leaves_a_lone_tabs_workspace_of_another_label_open(herdr: _Herdr) -> None:
    item = _grouped()
    herdr.listing = _tabs(("w9:t1", "w9", item.id, "idle"))
    herdr.workspaces = _ws("somebody-elses", "w9")
    assert HerdrRunner.from_env().close(item) == "closed"
    assert _closes(herdr) == [["tab", "close", "w9:t1"]]


def test_close_keeps_the_workspace_when_it_holds_other_tabs(herdr: _Herdr) -> None:
    item = _grouped()
    herdr.listing = _tabs(("w9:t1", "w9", item.id, "idle"), ("w9:t2", "w9", "sibling", "working"))
    herdr.workspaces = _ws("drive-wave-1", "w9")
    assert HerdrRunner.from_env().close(item) == "closed"
    assert _closes(herdr) == [["tab", "close", "w9:t1"]]


def test_close_without_a_group_never_lists_workspaces(herdr: _Herdr) -> None:
    item = _item()
    herdr.listing = _tabs(("w9:t1", "w9", item.id, "idle"))
    assert HerdrRunner.from_env().close(item) == "closed"
    assert not any(c[:2] == ["workspace", "list"] for c in herdr.calls)


def test_herdr_meets_the_close_contract(herdr: _Herdr) -> None:
    from fr_dispatch.testing import check_close_contract

    herdr.listing = _tabs(("w2:t1", "w2", "other", "idle"))
    check_close_contract(HerdrRunner.from_env(), _item())
