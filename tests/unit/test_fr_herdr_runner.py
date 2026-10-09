"""`HerdrRunner` — the run-unit runner over the herdr CLI (spec 2026-09-25-triage-batches
§3.C, Test Plan 6).

The herdr CLI is faked at `fr_herdr.runner._run_herdr`, the runner's one
subprocess seam; its answers are the fixtures under `tests/fixtures/herdr/`
(see the README there for which are live captures). No herdr session is driven.
"""

from __future__ import annotations

import json
import re
import subprocess
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
        self.agents: dict[str, Any] = {}

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
        if args[:2] == ["agent", "list"]:
            return self.agents or _fixture("agent-list.json")
        if args[:2] == ["agent", "rename"]:
            return _fixture("agent-rename.json")
        return {}

    def text(self) -> str:
        return "\n".join(" ".join(c) for c in self.calls)


@pytest.fixture
def herdr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _Herdr:
    fake = _Herdr()
    monkeypatch.setattr(herdr_runner, "_run_herdr", fake)
    monkeypatch.setattr(herdr_runner.shutil, "which", lambda name: "/usr/local/bin/herdr")
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setenv("HERDR_WORKSPACE_ID", "w2")
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "server.sock"))
    monkeypatch.setenv("FR_HERDR_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(herdr_runner, "stable_checkout", lambda path: path)
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
    # driver-sessions R9: the refusal says where to run the driver from
    assert "fr triage batch drive" in message and "dispatch" in message
    assert "herdr pane" in message


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


def test_opencode_refuses_an_unqualified_model_before_opening_a_tab(herdr: _Herdr) -> None:
    with pytest.raises(herdr_runner.HerdrError, match="provider/model"):
        HerdrRunner.from_env().dispatch(_item(harness="opencode", model="unqualified"))
    assert herdr.calls == []


def test_original_opencode_batch_message_persists_conflict_identity(herdr: _Herdr) -> None:
    from fr_herdr import managed

    item = _item(harness="opencode", model="openai/gpt-6.1-sol")
    pane = HerdrRunner.from_env().dispatch(item)
    # Synthetic listing joins the captured create identity to this test item.
    herdr.listing = {"result": {"tabs": [{"tab_id": "w2:t1H", "label": item.id}]}}
    herdr.agents = {"result": {"agents": [{"tab_id": "w2:t1H", "pane_id": pane}]}}
    brief = "Merge conflict on batch lifecycle: PR #1, at head abc, conflicts with main. six steps"
    HerdrRunner.from_env().message(item, brief)
    d = managed.load(pane)
    assert d.item == item.id and d.role == "batch"
    assert d.conflict_head == "abc" and d.conflict_brief == brief


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


@pytest.mark.parametrize(
    "harness,model", [("claude", "claude-opus-5-5"), ("opencode", "openai/gpt-6.1-sol")]
)
def test_dispatch_creates_the_tab_starts_the_agent_then_prompts_it(
    herdr: _Herdr, harness: str, model: str
) -> None:
    item = _item(harness=harness, model=model, brief="/fr-goal Separate lifecycles")

    handle = HerdrRunner.from_env().dispatch(item)

    create, start, prompt = herdr.calls
    assert create == [
        "tab", "create", "--workspace", "w2", "--cwd", "/work/alpha",
        "--label", item.id, "--no-focus",
    ]  # fmt: skip
    name = agent_name(item.id)
    assert start == [
        "agent", "start", name, "--kind", harness, "--pane", "w2:p1K",
        "--", "--model", model,
    ]  # fmt: skip
    assert prompt == [
        "agent", "prompt", name, "/fr-goal Separate lifecycles",
        "--wait", "--until", "working", "--until", "blocked", "--timeout", "30000",
    ]  # fmt: skip
    assert handle == "w2:p1K"


# ------------------------------------- gh#931 / gh#956: a ready pane, a submitted brief


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    naps: list[float] = []
    monkeypatch.setattr(herdr_runner, "_sleep", naps.append)
    return naps


def _refusal(name: str) -> herdr_runner.HerdrError:
    """The `HerdrError` `_run_herdr` raises for a herdr error envelope fixture."""
    envelope = _fixture(name)
    return herdr_runner.HerdrError(
        f"herdr {envelope['id']} failed: {json.dumps(envelope)}", code=envelope["error"]["code"]
    )


def _refusing(herdr: _Herdr, refusals: dict[str, list[herdr_runner.HerdrError]]) -> Any:
    """`herdr` with the first calls of each verb (`"agent start"`) raising its errors."""
    left = {verb: list(errors) for verb, errors in refusals.items()}

    def fake(args: list[str]) -> dict[str, Any]:
        errors = left.get(" ".join(args[:2]))
        if errors:
            herdr.calls.append(list(args))
            raise errors.pop(0)
        return herdr(args)

    return fake


def test_run_herdr_carries_herdrs_error_code(monkeypatch: pytest.MonkeyPatch) -> None:
    stderr = (FIXTURES / "agent-start-pane-busy.json").read_text(encoding="utf-8")

    def run(argv: list[str], **kw: Any) -> Any:
        raise subprocess.CalledProcessError(1, argv, output="", stderr=stderr)

    monkeypatch.setattr(herdr_runner.subprocess, "run", run)
    with pytest.raises(herdr_runner.HerdrError, match="not an available shell") as caught:
        herdr_runner._run_herdr(["agent", "start", "x"])
    assert caught.value.code == "agent_pane_busy"


def test_a_failure_without_an_envelope_has_no_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def run(argv: list[str], **kw: Any) -> Any:
        raise subprocess.CalledProcessError(2, argv, output="", stderr="usage: herdr ...")

    monkeypatch.setattr(herdr_runner.subprocess, "run", run)
    with pytest.raises(herdr_runner.HerdrError) as caught:
        herdr_runner._run_herdr(["agent", "start", "x"])
    assert caught.value.code is None


def test_a_hung_herdr_observation_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    def hung(argv, **kwargs):
        assert kwargs.get("timeout") == 60
        raise subprocess.TimeoutExpired(argv, 60)

    monkeypatch.setattr(herdr_runner.subprocess, "run", hung)
    with pytest.raises(herdr_runner.HerdrError, match="timed out"):
        herdr_runner._run_herdr(["pane", "process-info", "--pane", "synthetic"])


def test_a_pane_whose_shell_is_not_up_yet_is_retried(
    herdr: _Herdr, monkeypatch: pytest.MonkeyPatch, sleeps: list[float]
) -> None:
    """gh#931: `agent start` right after `tab create` can find the shell still starting."""
    busy = _refusal("agent-start-pane-busy.json")
    monkeypatch.setattr(herdr_runner, "_run_herdr", _refusing(herdr, {"agent start": [busy, busy]}))
    assert HerdrRunner.from_env().dispatch(_item()) == "w2:p1K"
    verbs = [c[:2] for c in herdr.calls]
    assert verbs == [["tab", "create"], *[["agent", "start"]] * 3, ["agent", "prompt"]]
    assert len(sleeps) == 2


def test_a_pane_still_busy_at_the_bound_fails_and_closes_the_tab(
    herdr: _Herdr, monkeypatch: pytest.MonkeyPatch, sleeps: list[float]
) -> None:
    busy = [_refusal("agent-start-pane-busy.json")] * 100
    monkeypatch.setattr(herdr_runner, "_run_herdr", _refusing(herdr, {"agent start": busy}))
    with pytest.raises(herdr_runner.HerdrError, match="not an available shell"):
        HerdrRunner.from_env().dispatch(_item())
    starts = [c for c in herdr.calls if c[:2] == ["agent", "start"]]
    assert len(starts) == herdr_runner.PANE_BUSY_TRIES
    assert sum(sleeps) <= 60  # bounded: a pane that never comes up fails the dispatch
    assert herdr.calls[-1] == ["tab", "close", "w2:t1H"]
    assert ["agent", "prompt"] not in [c[:2] for c in herdr.calls]


def test_another_start_refusal_is_not_retried(
    herdr: _Herdr, monkeypatch: pytest.MonkeyPatch, sleeps: list[float]
) -> None:
    """`agent_not_ready` is a dialog the operator must answer (herdr --skill), not a race."""
    blocked = herdr_runner.HerdrError("herdr agent start failed: blocked", code="agent_not_ready")
    monkeypatch.setattr(herdr_runner, "_run_herdr", _refusing(herdr, {"agent start": [blocked]}))
    with pytest.raises(herdr_runner.HerdrError, match="blocked"):
        HerdrRunner.from_env().dispatch(_item())
    assert sleeps == []
    assert herdr.calls[-1] == ["tab", "close", "w2:t1H"]


def test_a_stalled_brief_is_submitted_with_enter_and_confirmed(
    herdr: _Herdr, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gh#956: the brief sat in the input box, unsubmitted. herdr says not to send it
    again (it may be there already); one Enter submits what is there."""
    stalled = _refusal("agent-prompt-stalled.json")
    monkeypatch.setattr(herdr_runner, "_run_herdr", _refusing(herdr, {"agent prompt": [stalled]}))
    item = _item()
    assert HerdrRunner.from_env().dispatch(item) == "w2:p1K"
    name = agent_name(item.id)
    prompt, enter, wait = herdr.calls[-3:]
    assert prompt[:3] == ["agent", "prompt", name]
    assert enter == ["agent", "send-keys", name, "enter"]
    assert wait == [
        "agent", "wait", name, "--until", "working", "--until", "blocked", "--timeout", "10000",
    ]  # fmt: skip
    assert sum(1 for c in herdr.calls if c[:2] == ["agent", "prompt"]) == 1  # never re-sent


def test_a_brief_still_unsubmitted_after_enter_fails_loudly_and_closes_the_tab(
    herdr: _Herdr, monkeypatch: pytest.MonkeyPatch
) -> None:
    stalled = _refusal("agent-prompt-stalled.json")
    timeout = herdr_runner.HerdrError("herdr agent wait failed: timed out", code="timeout")
    monkeypatch.setattr(
        herdr_runner,
        "_run_herdr",
        _refusing(herdr, {"agent prompt": [stalled], "agent wait": [timeout]}),
    )
    with pytest.raises(herdr_runner.HerdrError, match="not submitted"):
        HerdrRunner.from_env().dispatch(_item())
    assert herdr.calls[-1] == ["tab", "close", "w2:t1H"]


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


def test_the_live_captured_focus_fixtures_have_herdrs_result_types() -> None:
    assert _fixture("workspace-focus.json")["result"]["type"] == "workspace_info"
    assert _fixture("tab-focus.json")["result"]["type"] == "tab_info"


# ------------------------------------------------- session status and focus


def _tabs_of(*rows: tuple[str, str, str, str]) -> dict[str, Any]:
    """A tab-list envelope from (label, status, tab_id, workspace_id) rows."""
    base = _fixture("tab-list-all.json")["result"]["tabs"][0]
    tabs = [
        {**base, "label": label, "agent_status": status, "tab_id": tab, "workspace_id": ws}
        for label, status, tab, ws in rows
    ]
    return {"result": {"type": "tab_list", "tabs": tabs}}


def test_a_blocked_tab_outranks_an_idle_one(herdr: _Herdr) -> None:
    item = _item()
    herdr.listing = _tabs_of((item.id, "idle", "w9:t1", "w9"), (item.id, "blocked", "w9:t2", "w9"))
    assert HerdrRunner.from_env().session_statuses([item]) == {item.id: "blocked"}


def test_a_working_tab_outranks_an_idle_one(herdr: _Herdr) -> None:
    item = _item()
    herdr.listing = _tabs_of((item.id, "working", "w9:t1", "w9"), (item.id, "idle", "w9:t2", "w9"))
    assert HerdrRunner.from_env().session_statuses([item]) == {item.id: "working"}


@pytest.mark.parametrize(
    ("first", "second", "wins"),
    [
        ("working", "blocked", "blocked"),
        ("idle", "working", "working"),
        ("done", "idle", "idle"),
        ("unknown", "done", "done"),
    ],
)
def test_the_precedence_is_blocked_working_idle_done_unknown(
    herdr: _Herdr, first: str, second: str, wins: str
) -> None:
    """R9's whole order, each adjacent pair in both tab orders."""
    item = _item()
    for a, b in ((first, second), (second, first)):
        herdr.listing = _tabs_of((item.id, a, "w9:t1", "w9"), (item.id, b, "w9:t2", "w9"))
        assert HerdrRunner.from_env().session_statuses([item]) == {item.id: wins}


def test_an_item_with_no_tab_is_absent(herdr: _Herdr) -> None:
    item = _item()
    herdr.listing = _tabs_of(("other", "idle", "w9:t1", "w9"))
    assert HerdrRunner.from_env().session_statuses([item]) == {item.id: "absent"}


def test_an_unrecognised_agent_status_is_unknown(herdr: _Herdr) -> None:
    item = _item()
    herdr.listing = _tabs_of((item.id, "weird", "w9:t1", "w9"))
    assert HerdrRunner.from_env().session_statuses([item]) == {item.id: "unknown"}


def test_session_statuses_lists_tabs_once_for_several_items(herdr: _Herdr) -> None:
    a = run_item("example-org/alpha", "batch-a")
    b = run_item("example-org/alpha", "batch-b")
    herdr.listing = _tabs_of((a.id, "done", "w9:t1", "w9"))
    got = HerdrRunner.from_env().session_statuses([a, b])
    assert got == {a.id: "done", b.id: "absent"}
    assert herdr.calls == [["tab", "list"]]


def test_focus_selects_the_workspace_then_the_tab(herdr: _Herdr) -> None:
    item = _item()
    herdr.listing = _tabs_of((item.id, "idle", "w9:t4", "w9"))
    assert HerdrRunner.from_env().focus(item) is True
    assert herdr.calls == [
        ["tab", "list"],
        ["workspace", "focus", "w9"],
        ["tab", "focus", "w9:t4"],
    ]


def test_focus_with_no_matching_tab_is_false_and_focuses_nothing(herdr: _Herdr) -> None:
    item = _item()
    herdr.listing = _tabs_of(("other", "idle", "w9:t1", "w9"))
    assert HerdrRunner.from_env().focus(item) is False
    assert herdr.calls == [["tab", "list"]]


# ------------------------------------------------- session messaging (R23)


def test_message_prompts_the_items_agent_with_the_text(herdr: _Herdr) -> None:
    """Spec 2026-10-06-verification-strategies §G: `herdr agent prompt <name> <text>`."""
    from fr_dispatch.protocols import SessionMessenger

    item = _item()
    runner = HerdrRunner.from_env()
    assert isinstance(runner, SessionMessenger)
    assert runner.message(item, "resolve the conflict") is None
    assert herdr.calls == [["agent", "prompt", agent_name(item.id), "resolve the conflict"]]


# ------------------------------------------------- idle-session restart (driver-sessions §B)


def test_restart_idle_is_a_session_restarter_and_summarises_the_engine_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R6: `restart_idle(exclude=...)` runs the engine with `yes=True` and maps its lines to
    a `RestartSummary(ok, skipped, failed)` of (pane, reason) pairs."""
    from fr_dispatch.protocols import RestartSummary, SessionRestarter
    from fr_herdr import restart as restart_mod

    seen: list[dict[str, object]] = []

    def _engine(*, yes: bool, exclude: object = ()) -> restart_mod.RestartReport:
        seen.append({"yes": yes, "exclude": tuple(exclude)})  # type: ignore[call-overload]
        return restart_mod.RestartReport(
            lines=[
                restart_mod.PaneLine("p1", "t", "ok", ""),
                restart_mod.PaneLine("p2", "t", "ok", ""),
                restart_mod.PaneLine("p3", "t", "skip", "working"),
                restart_mod.PaneLine("p4", "t", "fail", "did not exit"),
            ],
            dry_run=False,
        )

    monkeypatch.setattr(restart_mod, "restart_idle", _engine)
    runner = HerdrRunner.from_env()
    assert isinstance(runner, SessionRestarter)
    summary = runner.restart_idle(exclude=("pX",))
    assert summary == RestartSummary(ok=2, skipped=1, failed=(("p4", "did not exit"),))
    assert seen == [{"yes": True, "exclude": ("pX",)}]


# ------------------------------------------------- session adoption (spec 2026-10-06 §E)
#
# The fixtures are one live capture (tests/fixtures/herdr/README.md): `wT:t1` is a
# scratch tab whose `claude` was started by hand, not by `herdr agent start`.

SCRATCH_TAB = "wT:t1"


@pytest.fixture
def adoptable(herdr: _Herdr) -> _Herdr:
    herdr.listing = _fixture("tab-list-adopt.json")
    herdr.workspaces = _fixture("workspace-list-adopt.json")
    herdr.agents = _fixture("agent-list.json")
    return herdr


def test_the_live_captured_adopt_fixtures_have_herdrs_result_types() -> None:
    assert _fixture("agent-list.json")["result"]["type"] == "agent_list"
    assert _fixture("agent-rename.json")["result"]["type"] == "agent_info"
    assert _fixture("agent-rename.json")["result"]["agent"]["name"] == "b-adopt-scratch-0000"
    assert _fixture("tab-rename-adopt.json")["result"]["type"] == "tab_info"
    hand_started = [
        a for a in _fixture("agent-list.json")["result"]["agents"] if a["tab_id"] == SCRATCH_TAB
    ]
    assert len(hand_started) == 1 and "name" not in hand_started[0]


def test_describe_reports_label_workspace_agent_and_status(adoptable: _Herdr) -> None:
    from fr_dispatch.protocols import AdoptTarget

    got = HerdrRunner.from_env().describe(SCRATCH_TAB)
    assert got == AdoptTarget(
        tab=SCRATCH_TAB,
        label="1 · adopt › claude › model haiku",
        group="fr-adopt-scratch",
        agent="wT:p1",
        status="blocked",
    )


def test_describe_an_unknown_tab_is_none(adoptable: _Herdr) -> None:
    assert HerdrRunner.from_env().describe("wZ:t9") is None


def test_describe_a_tab_with_no_agent_has_agent_none(adoptable: _Herdr) -> None:
    got = HerdrRunner.from_env().describe("w7:t9")  # the `|` tab: a bare shell
    assert got is not None and got.agent is None


def test_describe_a_tab_with_several_agents_has_agent_none(adoptable: _Herdr) -> None:
    agents = _fixture("agent-list.json")
    scratch = next(a for a in agents["result"]["agents"] if a["tab_id"] == SCRATCH_TAB)
    agents["result"]["agents"].append({**scratch, "pane_id": "wT:p2"})
    adoptable.agents = agents
    got = HerdrRunner.from_env().describe(SCRATCH_TAB)
    assert got is not None and got.agent is None


def test_describe_prefers_an_agents_name_over_its_pane(adoptable: _Herdr) -> None:
    adoptable.agents = _fixture("agent-list-adopted.json")
    got = HerdrRunner.from_env().describe(SCRATCH_TAB)
    assert got is not None and got.agent == "b-adopt-scratch-0000"


def test_list_sessions_returns_one_target_per_tab_with_its_raw_label(adoptable: _Herdr) -> None:
    got = HerdrRunner.from_env().list_sessions()
    tabs = _fixture("tab-list-adopt.json")["result"]["tabs"]
    assert [t.tab for t in got] == [t["tab_id"] for t in tabs]
    by_tab = {t.tab: t for t in got}
    assert by_tab["w7:t5"].label == "frank#551 fr-goal finish"
    assert by_tab["w7:t5"].group == "frank"
    assert by_tab["w7:t5"].agent == "w7:p5"
    assert by_tab["w9:tA"].status == "working"


def test_list_sessions_reads_each_list_once(adoptable: _Herdr) -> None:
    HerdrRunner.from_env().list_sessions()
    assert sorted(c[:2] for c in adoptable.calls) == [
        ["agent", "list"],
        ["tab", "list"],
        ["workspace", "list"],
    ]


def test_adopt_renames_the_tab_then_the_agent_and_returns_the_tab(adoptable: _Herdr) -> None:
    item = _item()
    handle = HerdrRunner.from_env().adopt(item, SCRATCH_TAB)
    assert handle == SCRATCH_TAB
    writes = [c for c in adoptable.calls if c[1] == "rename"]
    assert writes == [
        ["tab", "rename", SCRATCH_TAB, item.id],
        ["agent", "rename", "wT:p1", agent_name(item.id)],
    ]


def test_adopt_is_a_no_op_when_already_adopted(adoptable: _Herdr) -> None:
    item = _item()
    tabs = _fixture("tab-list-adopt.json")
    for t in tabs["result"]["tabs"]:
        if t["tab_id"] == SCRATCH_TAB:
            t["label"] = item.id
    agents = _fixture("agent-list.json")
    for a in agents["result"]["agents"]:
        if a["tab_id"] == SCRATCH_TAB:
            a["name"] = agent_name(item.id)
    adoptable.listing, adoptable.agents = tabs, agents
    assert HerdrRunner.from_env().adopt(item, SCRATCH_TAB) == SCRATCH_TAB
    assert [c for c in adoptable.calls if c[1] == "rename"] == []


def test_adopt_an_unknown_tab_raises_and_renames_nothing(adoptable: _Herdr) -> None:
    with pytest.raises(herdr_runner.HerdrError, match="wZ:t9"):
        HerdrRunner.from_env().adopt(_item(), "wZ:t9")
    assert [c for c in adoptable.calls if c[1] == "rename"] == []


def test_adopt_a_tab_without_one_agent_raises_and_renames_nothing(adoptable: _Herdr) -> None:
    with pytest.raises(herdr_runner.HerdrError, match="agent"):
        HerdrRunner.from_env().adopt(_item(), "w7:t9")
    assert [c for c in adoptable.calls if c[1] == "rename"] == []


def test_herdr_meets_the_adopt_contract(adoptable: _Herdr) -> None:
    from fr_dispatch.testing import check_adopt_contract

    check_adopt_contract(HerdrRunner.from_env())
