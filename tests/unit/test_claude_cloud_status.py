"""Session status and notes, and the herdr-only remnants (cloud-triage R15, §F; Test
Plan 10).

A cloud session's state maps onto fr's closed `SessionStatus`; a blocked session's
`needs_action` reaches the board and Needs-you-now through the optional `SessionNotes`
protocol, and nothing changes for a runner without it (herdr). A batch's stage stays a
function of forge facts alone. `adopt --list` and the wave grouping stop assuming herdr.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import fr.cli  # noqa: F401 - the command modules load in the CLI's order
import pytest
import yaml
from fr.commands import triage_batch_cmd, triage_kanban_cmd
from fr.commands.triage_kanban_cmd import read_sessions, write_board
from fr.triage.driver import CLOUD, HOST
from fr.triage.kanban import NEEDS_YOU, build_board
from fr.triage.model import load_facts, load_judgements
from fr.triage.render import render
from fr.triage.views import needs_you
from fr_claude_cloud.runner import ClaudeCloudRunner
from fr_dispatch.protocols import SessionNotes
from fr_dispatch.testing import run_item

from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 - fixtures
    REPO,
    DriveCheckout,
    ScriptedMerge,
    World,
    _batch,
    _conflict_error,
    _conflicts,
    _drive,
    _lines,
    _one_conflicted,
    _state,
    checkout_fixture,
    train,
    world_fixture,
)
from tests.unit.test_triage_batch_drive_cmd import _dispatch_event as _host_dispatch
from tests.unit.test_triage_driver_pass import _pass, _world, clock  # noqa: F401
from tests.unit.test_triage_kanban_cmd import _Inspector

B1 = f"{REPO}/run/batch-b1"
CLOUD_DISPATCH = (
    "      - {kind: dispatch, at: 2026-10-01T10:00:00Z, runner: claude-cloud, "
    "handle: h, branch: feat/batch-b1}\n"
)


def _cloud(state: Path, statuses: Any = None) -> ClaudeCloudRunner:
    runner = ClaudeCloudRunner.from_env()
    runner.open_mailbox(state, statuses)
    return runner


def _session(where: Path, item: str = B1, **extra: Any) -> None:
    (where / "sessions.yaml").write_text(
        yaml.safe_dump({"sessions": [{"item": item, "session": "session_01", **extra}]})
    )


# ------------------------------------------------------------------ the mapping


@pytest.mark.parametrize(
    ("state", "status"),
    [
        ("working", "working"),
        ("blocked", "blocked"),
        ("review_ready", "idle"),
        ("completed", "idle"),
        ("failed", "blocked"),
        ("something-new", "unknown"),
    ],
)
def test_a_cloud_state_maps_onto_an_fr_session_status(
    tmp_path: Path, state: str, status: str
) -> None:
    item = run_item(run_id="batch-b1")
    runner = _cloud(tmp_path, {"sessions": [{"id": "s1", "tag": item.id, "state": state}]})
    assert runner.session_statuses([item]) == {item.id: status}


def test_an_item_with_no_session_is_absent(tmp_path: Path) -> None:
    item = run_item(run_id="batch-b1")
    assert _cloud(tmp_path).session_statuses([item]) == {item.id: "absent"}


def test_session_notes_return_only_blocked_sessions_needs_action(tmp_path: Path) -> None:
    blocked, working, failed = (run_item(run_id=f"batch-{b}") for b in ("b1", "b2", "b3"))
    runner = _cloud(
        tmp_path,
        {"sessions": [
            {"id": "s1", "tag": blocked.id, "state": "blocked", "needs_action": "approve push"},
            {"id": "s2", "tag": working.id, "state": "working", "needs_action": "stale text"},
            {"id": "s3", "tag": failed.id, "state": "failed", "needs_action": "quota"},
        ]},
    )  # fmt: skip
    assert isinstance(runner, SessionNotes)
    assert runner.session_notes([blocked, working, failed]) == {
        blocked.id: "approve push",
        failed.id: "quota",
    }


def test_herdr_is_no_session_notes_runner() -> None:
    from fr_herdr.runner import HerdrRunner

    assert not isinstance(HerdrRunner(), SessionNotes)


def test_the_state_the_agent_read_persists_for_a_later_read_without_statuses(
    tmp_path: Path,
) -> None:
    item = run_item(run_id="batch-b1")
    _session(tmp_path, item.id)
    _cloud(tmp_path, {item.id: {"state": "blocked", "needs_action": "approve push"}})

    later = _cloud(tmp_path)  # the board, or `drive record`: no statuses handed in

    assert later.session_statuses([item]) == {item.id: "blocked"}
    assert later.session_notes([item]) == {item.id: "approve push"}


# ------------------------------------------------- the board and Needs-you-now


class _Noted(_Inspector):
    def __init__(self, statuses: dict[str, str], notes: dict[str, str]) -> None:
        super().__init__(statuses)
        self.notes = notes

    def session_notes(self, items: Any) -> dict[str, str]:
        return {i.id: self.notes[i.id] for i in items if i.id in self.notes}


def _one_dispatched(tmp_path: Path) -> tuple[Any, Any]:
    world = World()
    world.issues[1] = "open"
    _state(tmp_path, world, _batch("b1", 1, events=_host_dispatch("b1")))
    return load_facts(tmp_path / "facts.json"), load_judgements(tmp_path / "judgements.yaml")


def _card(board: Any) -> Any:
    return next(c for col in board.columns for c in col.cards if c.batch.id == "b1")


def test_the_board_card_shows_a_blocked_sessions_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    facts, judgements = _one_dispatched(tmp_path)
    runner = _Noted({B1: "blocked"}, {B1: "approve the push to main"})
    monkeypatch.setattr(triage_kanban_cmd, "load_runner", lambda name: runner)

    reads = read_sessions(judgements, facts)

    assert reads.statuses == {B1: "blocked"}
    assert reads.session_notes == {B1: "approve the push to main"}
    card = _card(build_board(facts, judgements, reads.statuses, notes=reads.session_notes))
    assert card.hint == f"{NEEDS_YOU}: approve the push to main"
    out, _ = write_board(SCOPE_OF(facts), tmp_path, scope_args=[])
    assert "approve the push to main" in out.read_text()


def test_the_board_is_unchanged_for_a_runner_without_notes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    facts, judgements = _one_dispatched(tmp_path)
    monkeypatch.setattr(triage_kanban_cmd, "load_runner", lambda name: _Inspector({B1: "blocked"}))

    reads = read_sessions(judgements, facts)

    assert reads.session_notes == {}
    assert _card(build_board(facts, judgements, reads.statuses)).hint == NEEDS_YOU
    assert _card(build_board(facts, judgements, reads.statuses, notes={})).hint == NEEDS_YOU


def test_needs_you_now_lists_a_blocked_sessions_note_and_nothing_without_one(
    tmp_path: Path,
) -> None:
    facts, judgements = _one_dispatched(tmp_path)

    without = needs_you(facts, judgements)
    noted = needs_you(facts, judgements, session_notes={B1: "approve the push"})

    assert [n for n in without if n.kind == "session-blocked"] == []
    (need,) = [n for n in noted if n.kind == "session-blocked"]
    assert need.ref == "b1" and "approve the push" in need.text
    page = render(facts, judgements, session_notes={B1: "approve the push"})
    assert "approve the push" in page
    assert render(facts, judgements) == render(facts, judgements, session_notes={})


def SCOPE_OF(facts: Any) -> Any:  # noqa: N802 - a fixture-shaped helper
    from fr.triage.model import Scope

    return Scope(kind="repo", target=facts.scope)


# ------------------------------------------ a session's state never moves a stage


def test_a_sessions_state_never_changes_a_batchs_stage_or_the_plan(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    clock: list[Any],  # noqa: F811 - the imported fixture
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plans: list[list[Any]] = []
    stages: list[dict[str, str]] = []
    real = triage_batch_cmd.drive_pass

    def spy(snap: Any) -> Any:
        plan = real(snap)
        plans.append(list(plan.actions))
        stages.append(dict(snap.stages))
        return plan

    monkeypatch.setattr(triage_batch_cmd, "drive_pass", spy)
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: ClaudeCloudRunner.from_env())
    for state_name in ("working", "blocked", "completed", "failed"):
        state = tmp_path / state_name
        world.__init__()  # type: ignore[misc] - the same forge facts for every pass
        _world(world, state)
        statuses = tmp_path / f"{state_name}.json"
        statuses.write_text(
            json.dumps({f"{REPO}/run/batch-b3": {"state": state_name, "needs_action": "x"}})
        )
        result = _pass(state, tmp_path / f"{state_name}-out.json", "--statuses", str(statuses))
        assert result.exit_code == 0, result.output

    assert all(p == plans[0] for p in plans)
    assert all(s == stages[0] for s in stages)


# ---------------------------------- a conflict on a completed session is a message


def test_a_conflict_on_a_completed_session_is_handed_back_by_message(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    train: ScriptedMerge,  # noqa: F811 - the imported fixture
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = ClaudeCloudRunner.from_env()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: runner)
    _one_conflicted(world, tmp_path)
    _session(tmp_path, B1, state="completed")  # finished its turn: still messageable
    train.script[101] = _conflict_error()

    code, out = _drive(tmp_path, "--once", "--yes")

    (line,) = _lines(out, "merge")
    assert "handed-back (pending)" in line, out
    (event,) = _conflicts(tmp_path)
    assert event.delivered == "session" and event.handle == B1
    (msg,) = [r for r in runner.outbox() if r["kind"] == "message"]
    assert msg["session"] == "session_01" and "PR #101" in msg["text"]
    assert [r for r in runner.outbox() if r["kind"] == "dispatch"] == []  # no fresh session


# ----------------------------------------------------- the herdr-only remnants


def test_adopt_list_reads_the_drivers_runner_and_is_skipped_when_it_cannot_adopt(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    asked: list[str] = []

    def load(name: str) -> Any:
        asked.append(name)
        return ClaudeCloudRunner.from_env()

    monkeypatch.setattr(triage_batch_cmd, "load_runner", load)

    triage_batch_cmd._list_sessions(None, driver=CLOUD)  # no exit: a message, not a refusal

    assert asked == ["claude-cloud"]
    out = " ".join(capsys.readouterr().out.split())
    assert "claude-cloud cannot adopt sessions" in out and "skipped" in out


def test_adopt_list_on_the_host_still_reads_herdr(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []

    class _Adopter:
        def describe(self, tab: str) -> None:
            return None

        def list_sessions(self) -> list[Any]:
            return []

        def adopt(self, item: Any, tab: str) -> str:
            return tab

    def load(name: str) -> Any:
        asked.append(name)
        return _Adopter()

    monkeypatch.setattr(triage_batch_cmd, "load_runner", load)
    triage_batch_cmd._list_sessions(None, driver=HOST)
    assert asked == [triage_batch_cmd.ADOPT_LIST_RUNNER] == ["herdr"]


def test_a_runner_without_groups_ignores_the_wave_group(tmp_path: Path) -> None:
    grouped = run_item(run_id="batch-b1", group="fr-wave-1")
    plain = run_item(run_id="batch-b2")
    runner = _cloud(tmp_path)

    assert runner.preflight([grouped]) is None
    runner.dispatch(grouped)
    runner.dispatch(plain)

    requests = {r["item"]: r for r in runner.outbox()}
    assert set(requests[grouped.id]) == set(requests[plain.id])  # no group, no workspace
    assert "group" not in requests[grouped.id]


# -------------------------------------- p4-o2: never load a runner it does not carry


def test_the_cloud_driver_never_loads_a_runner_it_does_not_carry(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    clock: list[Any],  # noqa: F811 - the imported fixture
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A host-dispatched (herdr) batch, merged and owing its close-out, in a cloud scope:
    the close-out is left to the host's driver, and herdr is never even loaded, not for
    its preflight, its existing dispatches, its sessions or the board."""
    asked: list[str] = []

    def load(name: str) -> Any:
        asked.append(name)
        if name != "claude-cloud":
            raise AssertionError(f"the cloud driver loaded {name}")
        return ClaudeCloudRunner.from_env()

    monkeypatch.setattr(triage_batch_cmd, "load_runner", load)
    monkeypatch.setattr(triage_kanban_cmd, "load_runner", load)
    state = tmp_path / "state"
    world.config = {"defaults": {"launch": {"runner": "herdr", "harness": "claude", "model": "m"}}}
    world.issues[3] = "open"
    world.pr(103, "feat/batch-b3", [3])
    herdr = ("      - {kind: dispatch, at: 2026-10-01T10:00:00Z, runner: herdr, "
             "handle: h, branch: feat/batch-b3}\n")  # fmt: skip
    state.mkdir()
    _state(state, world, _batch("b3", 3, events=herdr, launch="{runner: herdr}"))

    first = _pass(state, tmp_path / "o1.json")
    world_merged = bool(world.merged)
    clock[0] = clock[0].replace(hour=clock[0].hour + 1)
    second = _pass(state, tmp_path / "o2.json")

    assert first.exit_code in (0, 3), first.output
    assert second.exit_code in (0, 3), second.output
    assert set(asked) <= {"claude-cloud"}, asked
    assert world_merged
    said = " ".join(second.output.split())
    assert "closeout b3: left to the driver of runner herdr" in said
