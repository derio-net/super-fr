"""Background work behind the Batches page's `waits for background` (spec
2026-11-27-board-session-state R3, §B).

The herdr CLI is faked at its seams; the screens are captures under `tests/fixtures/herdr/restart/`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import fr.cli  # noqa: F401  (the commands import each other; load them in the CLI order)
import pytest
from fr.commands.triage_kanban_cmd import read_sessions
from fr_dispatch.protocols import SessionActivity, SessionInspector
from fr_dispatch.testing import run_item
from fr_herdr import runner as herdr_runner
from fr_herdr.runner import HerdrRunner

from tests.unit.test_triage_batch_drive_cmd import REPO, _dispatch_event
from tests.unit.test_triage_kanban_cmd import _Inspector, _loaded, _setup, _use

SCREENS = Path(__file__).resolve().parent.parent / "fixtures" / "herdr" / "restart"


def _screen(name: str) -> str:
    return str(json.loads((SCREENS / name).read_text())["raw"])


# ------------------------------------------------------------------ the protocol


def test_session_activity_is_a_runtime_checkable_protocol_beside_the_others() -> None:
    class Says:
        def session_background(self, items: Any) -> frozenset[str]:
            return frozenset()

    assert isinstance(Says(), SessionActivity)
    assert not isinstance(object(), SessionActivity)
    assert isinstance(HerdrRunner(), SessionActivity)
    assert isinstance(HerdrRunner(), SessionInspector)


# ------------------------------------------------------------- the herdr runner


class _Herdr:
    def __init__(self, tabs: list[dict[str, Any]], agents: list[dict[str, Any]],
                 screens: dict[str, str]) -> None:  # fmt: skip
        self.tabs, self.agents, self.screens = tabs, agents, screens
        self.reads: list[str] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(herdr_runner, "_list_tabs", lambda: self.tabs)
        monkeypatch.setattr(herdr_runner, "_list_agents", lambda: self.agents)
        monkeypatch.setattr(herdr_runner, "_run_herdr", self)

    def __call__(self, args: list[str], **kwargs: Any) -> dict[str, Any]:
        assert args[:2] == ["pane", "read"], args
        assert "--source" in args and "visible" in args and "--ansi" in args
        self.reads.append(args[2])
        if self.screens[args[2]] == "RAISE":
            raise RuntimeError("pane read failed")
        return {"raw": self.screens[args[2]]}


def _tab(item_id: str, tab: str, status: str) -> dict[str, Any]:
    return {"tab_id": tab, "label": item_id, "agent_status": status, "workspace_id": "w1"}


def _agent(tab: str, pane: str, kind: str = "claude") -> dict[str, Any]:
    return {"agent": kind, "tab_id": tab, "pane_id": pane, "agent_status": "idle"}


def test_an_idle_claude_pane_with_a_shell_is_background_and_nothing_else_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    items = [run_item(run_id=r) for r in ("a", "b", "c", "d", "e")]
    ids = [i.id for i in items]
    herdr = _Herdr(
        tabs=[
            _tab(ids[0], "t0", "idle"),  # a shell runs: background
            _tab(ids[1], "t1", "working"),  # never read
            _tab(ids[2], "t2", "idle"),  # opencode: never read
            _tab(ids[3], "t3", "done"),  # only the `← 1 agent` line: not background
            # ids[4] has no tab at all
        ],
        agents=[
            _agent("t0", "p0"),
            _agent("t1", "p1"),
            _agent("t2", "p2", kind="opencode"),
            _agent("t3", "p3"),
        ],
        screens={"p0": _screen("screen-background.json"), "p3": _screen("screen-empty.json")},
    )
    herdr.install(monkeypatch)
    assert HerdrRunner().session_background(items) == frozenset({ids[0]})
    assert sorted(herdr.reads) == ["p0", "p3"]


def test_one_unreadable_pane_never_loses_another_items_background_mark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    items = [run_item(run_id=r) for r in ("a", "b", "c")]
    ids = [i.id for i in items]
    herdr = _Herdr(
        tabs=[_tab(ids[0], "t0", "idle"), _tab(ids[1], "t1", "idle"), _tab(ids[2], "t2", "idle")],
        agents=[
            _agent("t0", "p0"),
            _agent("t1", "p1"),
            {"agent": "claude", "tab_id": "t2", "agent_status": "idle"},  # no pane_id
        ],
        screens={"p0": "RAISE", "p1": _screen("screen-background.json")},
    )
    herdr.install(monkeypatch)
    assert HerdrRunner().session_background(items) == frozenset({ids[1]})


# ------------------------------------------------------------------ read_sessions


class _Activity(_Inspector):
    def __init__(self, background: set[str]) -> None:
        super().__init__()
        self.background = background

    def session_background(self, items: Any) -> frozenset[str]:
        return frozenset(self.background)


class _ActivityRaises(_Inspector):
    def session_background(self, items: Any) -> frozenset[str]:
        raise RuntimeError("pane read failed:\nboom")


def test_read_sessions_fills_background_from_a_runner_that_says_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, _dispatch_event("b1"))
    key = f"{REPO}/run/batch-b1"
    _use(monkeypatch, _Activity({key}))
    facts, judgements = _loaded(tmp_path)
    assert read_sessions(judgements, facts).background == frozenset({key})


def test_a_runner_without_the_protocol_reports_no_background(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, _dispatch_event("b1"))
    _use(monkeypatch, _Inspector())
    facts, judgements = _loaded(tmp_path)
    reads = read_sessions(judgements, facts)
    assert reads.background == frozenset() and reads.notes == []


def test_a_failed_background_read_is_one_note_and_statuses_are_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, _dispatch_event("b1"))
    key = f"{REPO}/run/batch-b1"
    runner = _ActivityRaises({key: "idle"})
    _use(monkeypatch, runner)
    facts, judgements = _loaded(tmp_path)
    reads = read_sessions(judgements, facts)
    assert reads.statuses == {key: "idle"} and reads.background == frozenset()
    assert reads.notes == ["runner `fake` could not read background work: pane read failed: boom"]
