"""The claude-cloud runner's mailbox (cloud-triage R14, §F; Test Plan 9).

fr cannot reach a cloud session itself, so every session action is a request with a
stable id `<item id>:<kind>:<n>`, pending in the scope's `requests.yaml` until the
driver's agent records its result; recorded sessions live in `sessions.yaml`. Both files
travel in the state ref (phase 3), so a driver restored on a fresh workspace still holds
them.
"""

from __future__ import annotations

import json
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Any

import fr.cli  # noqa: F401 - the command modules load in the CLI's order
import pytest
import yaml
from fr.commands import triage_batch_cmd
from fr.triage.driver import Mailbox
from fr.triage.model import load_judgements
from fr_claude_cloud.mailbox import REQUEST_TABLE
from fr_claude_cloud.runner import ClaudeCloudRunner
from fr_dispatch.protocols import SessionCloser, SessionInspector, SessionMessenger
from fr_dispatch.testing import check_run_unit_contract, run_item

from tests.unit.test_triage_batch_dispatch import FakeRunner
from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 - fixtures
    REPO,
    DriveCheckout,
    World,
    checkout_fixture,
    world_fixture,
)
from tests.unit.test_triage_driver_pass import _pass, _record, _world, clock  # noqa: F401

ITEM = run_item(run_id="batch-b1")
OTHER = run_item(run_id="batch-b2")


def _opened(state: Path, statuses: Any = None) -> ClaudeCloudRunner:
    runner = ClaudeCloudRunner.from_env()
    runner.open_mailbox(state, statuses)
    return runner


def _requests(state: Path) -> list[dict[str, Any]]:
    return list((yaml.safe_load((state / "requests.yaml").read_text()) or {})["requests"])


def _sessions(state: Path) -> list[dict[str, Any]]:
    path = state / "sessions.yaml"
    if not path.is_file():
        return []
    return list((yaml.safe_load(path.read_text()) or {}).get("sessions") or [])


def _pending(runner: ClaudeCloudRunner, kind: str) -> list[dict[str, Any]]:
    return [r for r in runner.outbox() if r["kind"] == kind]


# ------------------------------------------------------------------- the seam


def test_the_runner_is_the_drivers_mailbox_and_its_session_protocols(tmp_path: Path) -> None:
    runner = _opened(tmp_path)
    assert isinstance(runner, Mailbox)
    assert isinstance(runner, SessionCloser)
    assert isinstance(runner, SessionInspector)
    assert isinstance(runner, SessionMessenger)


def test_the_run_unit_contract_holds_on_an_opened_mailbox(tmp_path: Path) -> None:
    runner = _opened(tmp_path)
    check_run_unit_contract(
        runner, run_item(), sent=lambda: (tmp_path / "requests.yaml").read_text()
    )


# ------------------------------------------------------------------ dispatch


def test_dispatch_writes_a_pending_request_and_returns_its_pending_handle(
    tmp_path: Path,
) -> None:
    runner = _opened(tmp_path)

    handle = runner.dispatch(ITEM)

    rid = f"{ITEM.id}:dispatch:1"
    assert handle == f"pending:{rid}"
    (request,) = _requests(tmp_path)
    assert request["id"] == rid
    assert request["kind"] == "dispatch"
    assert request["item"] == ITEM.id
    assert request["tag"] == ITEM.id  # the batch's item id: how a lost result is found
    assert request["repo"] == ITEM.repo
    assert request["branch"] == ITEM.payload["branch"]
    assert request["model"] == ITEM.payload["model"]
    assert request["prompt"] == ITEM.payload["brief"]


def test_a_pending_dispatch_is_held_and_never_requested_twice(tmp_path: Path) -> None:
    runner = _opened(tmp_path)
    first = runner.dispatch(ITEM)

    assert runner.existing_dispatches([ITEM, OTHER]) == {ITEM.id}
    again = _opened(tmp_path)  # the next pass
    assert again.existing_dispatches([ITEM]) == {ITEM.id}
    assert again.dispatch(ITEM) == first
    assert len(_pending(again, "dispatch")) == 1


def test_a_pending_request_is_re_emitted_on_every_pass_until_recorded(tmp_path: Path) -> None:
    _opened(tmp_path).dispatch(ITEM)
    rid = f"{ITEM.id}:dispatch:1"

    for _ in range(3):  # three passes, no result recorded
        assert [r["id"] for r in _pending(_opened(tmp_path), "dispatch")] == [rid]

    runner = _opened(tmp_path)
    assert runner.record_results([{"id": rid, "session": "session_01"}]) == [rid]

    after = _opened(tmp_path)
    assert _pending(after, "dispatch") == []
    assert _sessions(tmp_path) == [
        {"item": ITEM.id, "session": "session_01", "repo": ITEM.repo,
         "branch": ITEM.payload["branch"]}
    ]  # fmt: skip
    assert after.existing_dispatches([ITEM]) == {ITEM.id}


def test_a_failed_create_keeps_the_dispatch_pending(tmp_path: Path) -> None:
    _opened(tmp_path).dispatch(ITEM)
    rid = f"{ITEM.id}:dispatch:1"

    assert _opened(tmp_path).record_results([{"id": rid, "error": "quota"}]) == [rid]

    assert [r["id"] for r in _pending(_opened(tmp_path), "dispatch")] == [rid]
    assert _sessions(tmp_path) == []


def test_a_result_no_pending_request_names_is_not_applied(tmp_path: Path) -> None:
    _opened(tmp_path).dispatch(ITEM)

    applied = _opened(tmp_path).record_results(
        [{"id": "nobody:dispatch:9", "session": "s"}, {"session": "no id"}]
    )

    assert applied == []
    assert _sessions(tmp_path) == []


def test_a_malformed_result_list_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="result"):
        _opened(tmp_path).record_results(["not an object"])  # type: ignore[list-item]


def test_a_lost_dispatch_result_is_found_by_its_tag_and_recorded_not_created_again(
    tmp_path: Path,
) -> None:
    _opened(tmp_path).dispatch(ITEM)  # the agent created the session; its result was lost
    listed = {"sessions": [{"id": "session_77", "tag": ITEM.id, "state": "working"}]}

    replay = _opened(tmp_path, listed)

    assert _pending(replay, "dispatch") == []  # nothing to create a second time
    assert [s["session"] for s in _sessions(tmp_path)] == ["session_77"]
    assert replay.existing_dispatches([ITEM]) == {ITEM.id}
    assert replay.session_statuses([ITEM]) == {ITEM.id: "working"}


def test_existing_dispatches_reads_recorded_and_listed_sessions(tmp_path: Path) -> None:
    (tmp_path / "sessions.yaml").write_text(
        yaml.safe_dump({"sessions": [{"item": ITEM.id, "session": "session_01"}]})
    )
    listed = {"sessions": [{"id": "session_02", "tag": OTHER.id, "state": "completed"}]}
    third = run_item(run_id="batch-b3")

    runner = _opened(tmp_path, listed)

    assert runner.existing_dispatches([ITEM, OTHER, third]) == {ITEM.id, OTHER.id}


def test_a_driver_restored_on_a_fresh_workspace_keeps_its_requests_and_sessions(
    tmp_path: Path,
) -> None:
    first = tmp_path / "a"
    runner = _opened(first)
    runner.dispatch(ITEM)
    runner.dispatch(OTHER)
    runner.record_results([{"id": f"{ITEM.id}:dispatch:1", "session": "session_01"}])
    fresh = tmp_path / "b"  # what a fetch of the ref restores: the files, nothing else
    fresh.mkdir()
    for name in ("requests.yaml", "sessions.yaml"):
        shutil.copy(first / name, fresh / name)

    restored = _opened(fresh)

    assert [r["id"] for r in _pending(restored, "dispatch")] == [f"{OTHER.id}:dispatch:1"]
    assert restored.existing_dispatches([ITEM, OTHER]) == {ITEM.id, OTHER.id}


# ------------------------------------------------------------- close, message


def _with_session(state: Path, item: Any = ITEM, session: str = "session_01") -> None:
    runner = _opened(state)
    runner.dispatch(item)
    runner.record_results([{"id": f"{item.id}:dispatch:1", "session": session}])


def test_close_is_absent_for_nothing_busy_while_pending_and_closed_once_recorded(
    tmp_path: Path,
) -> None:
    runner = _opened(tmp_path)
    assert runner.close(ITEM) == "absent"
    runner.dispatch(ITEM)
    assert runner.close(ITEM) == "busy"  # its session does not exist yet
    runner.record_results([{"id": f"{ITEM.id}:dispatch:1", "session": "session_01"}])

    runner = _opened(tmp_path)
    assert runner.close(ITEM) == "busy"  # the archive is a request now
    assert runner.close(ITEM) == "busy"  # and stays one, not two
    (close,) = _pending(runner, "close")
    assert close["id"] == f"{ITEM.id}:close:1"
    assert close["session"] == "session_01"

    runner = _opened(tmp_path)
    runner.record_results([{"id": close["id"], "outcome": "closed"}])
    assert _sessions(tmp_path) == []
    assert _opened(tmp_path).close(ITEM) == "absent"


def test_a_busy_close_result_asks_again_with_the_next_number(tmp_path: Path) -> None:
    _with_session(tmp_path)
    runner = _opened(tmp_path)
    runner.close(ITEM)
    runner.record_results([{"id": f"{ITEM.id}:close:1", "outcome": "busy"}])

    again = _opened(tmp_path)
    assert again.close(ITEM) == "busy"
    assert [r["id"] for r in _pending(again, "close")] == [f"{ITEM.id}:close:2"]


def test_a_message_carries_its_request_id_and_a_refused_one_is_retried(tmp_path: Path) -> None:
    _with_session(tmp_path)
    runner = _opened(tmp_path)

    runner.message(ITEM, "rebase onto main")
    runner.message(ITEM, "rebase onto main")  # a re-sent hand-back is the same request

    (msg,) = _pending(runner, "message")
    assert msg["id"] == f"{ITEM.id}:message:1"
    assert msg["session"] == "session_01"
    assert msg["id"] in msg["text"] and "rebase onto main" in msg["text"]

    _opened(tmp_path).record_results([{"id": msg["id"], "outcome": "refused"}])
    (retry,) = _pending(_opened(tmp_path), "message")
    assert retry["id"] == f"{ITEM.id}:message:2"
    assert "rebase onto main" in retry["text"]

    _opened(tmp_path).record_results([{"id": retry["id"], "outcome": "sent"}])
    assert _pending(_opened(tmp_path), "message") == []


def test_a_message_to_no_session_is_a_failed_send(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no session"):
        _opened(tmp_path).message(ITEM, "hello")


def test_a_rehome_replaces_the_session_once_recorded(tmp_path: Path) -> None:
    _with_session(tmp_path)
    runner = _opened(tmp_path)

    runner.rehome(ITEM, "resume brief")

    (req,) = _pending(runner, "rehome")
    assert req["id"] == f"{ITEM.id}:rehome:1"
    assert req["session"] == "session_01" and req["prompt"] == "resume brief"
    assert req["tag"] == ITEM.id
    runner.record_results([{"id": req["id"], "session": "session_02"}])
    assert [s["session"] for s in _sessions(tmp_path)] == ["session_02"]


# ------------------------------------------------------------ the request table


def test_the_request_table_names_the_five_kinds() -> None:
    assert set(REQUEST_TABLE) == {"dispatch", "message", "close", "rehome", "status"}
    for row in REQUEST_TABLE.values():
        assert row.execute and row.record


def test_every_outbox_entry_carries_what_to_execute_and_what_to_record(tmp_path: Path) -> None:
    _with_session(tmp_path)
    runner = _opened(tmp_path)
    runner.dispatch(OTHER)
    runner.message(ITEM, "hi")
    runner.close(ITEM)
    runner.rehome(ITEM, "resume")

    out = _opened(tmp_path).outbox()

    assert {r["kind"] for r in out} == set(REQUEST_TABLE)
    for request in out:
        row = REQUEST_TABLE[request["kind"]]
        assert request["execute"] == row.execute
        assert request["record"] == row.record
    assert "list_sessions" in REQUEST_TABLE["dispatch"].execute
    assert "create_session" in REQUEST_TABLE["dispatch"].execute
    assert "archive_session" in REQUEST_TABLE["close"].execute
    assert "get_session" in REQUEST_TABLE["status"].execute


def test_a_status_request_is_asked_of_every_recorded_session_and_records_its_state(
    tmp_path: Path,
) -> None:
    _with_session(tmp_path)
    (status,) = _pending(_opened(tmp_path), "status")
    assert status["id"] == f"{ITEM.id}:status:1"
    assert status["session"] == "session_01"

    _opened(tmp_path).record_results(
        [{"id": status["id"], "state": "blocked", "needs_action": "approve the push"}]
    )

    again = _opened(tmp_path)
    assert again.session_statuses([ITEM]) == {ITEM.id: "blocked"}
    assert again.session_notes([ITEM]) == {ITEM.id: "approve the push"}


# ------------------------------------------------- the pass, with the real runner


@pytest.fixture
def cloud(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """`claude-cloud` is the real runner; any other name a fake that records asks."""
    loaded: dict[str, Any] = {}

    def load(name: str) -> Any:
        if name not in loaded:
            loaded[name] = ClaudeCloudRunner.from_env() if name == "claude-cloud" else FakeRunner()
        return loaded[name]

    monkeypatch.setattr(triage_batch_cmd, "load_runner", load)
    return loaded


def test_the_pass_emits_the_real_runners_outbox_and_replays_it_until_recorded(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    cloud: dict[str, Any],
    clock: list[Any],  # noqa: F811 - the imported fixture
) -> None:
    state = tmp_path / "state"
    _world(world, state)
    outbox = tmp_path / "outbox.json"

    first = _pass(state, outbox)

    assert first.exit_code == 0, first.output
    b1, b2 = (f"{REPO}/run/batch-{b}" for b in ("b1", "b2"))
    requests = json.loads(outbox.read_text())["requests"]
    assert [(r["id"], r["kind"]) for r in requests] == [
        (f"{b1}:dispatch:1", "dispatch"),
        (f"{b2}:dispatch:1", "dispatch"),
    ]
    events = {b.id: b.events[-1] for b in load_judgements(state / "judgements.yaml").batches}
    assert events["b1"].handle == f"pending:{b1}:dispatch:1"  # in flight, pending
    assert set(cloud) == {"claude-cloud"}  # no other runner was loaded

    clock[0] += timedelta(minutes=10)  # the next wake: no result recorded
    cloud.clear()
    second = _pass(state, outbox)

    assert second.exit_code in (0, 3), second.output
    again = json.loads(outbox.read_text())["requests"]
    batch_ids = [r["id"] for r in again if r["item"] in (b1, b2)]
    assert batch_ids == [r["id"] for r in requests]  # re-emitted, not new
    batches = load_judgements(state / "judgements.yaml").batches
    assert sum(e.kind == "dispatch" for b in batches for e in b.events) == 3  # b3's + two

    results = tmp_path / "results.json"
    results.write_text(
        json.dumps([{"id": r["id"], "session": f"session_{i}"} for i, r in enumerate(again)])
    )
    recorded = _record(state, outbox, results)
    assert recorded.exit_code == 0, recorded.output

    clock[0] += timedelta(minutes=10)
    cloud.clear()
    third = _pass(state, outbox)
    assert third.exit_code in (0, 3), third.output
    third_out = json.loads(outbox.read_text())["requests"]
    mine = [r["kind"] for r in third_out if r["item"] in (b1, b2)]
    assert mine == ["status", "status"]  # recorded: no dispatch, each state asked for


def test_record_refuses_a_malformed_result_by_name_and_records_nothing(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    cloud: dict[str, Any],
    clock: list[Any],  # noqa: F811 - the imported fixture
) -> None:
    state = tmp_path / "state"
    _world(world, state)
    outbox = tmp_path / "outbox.json"
    assert _pass(state, outbox).exit_code == 0
    _with_session(state, run_item(repo=REPO, run_id="batch-b1"))
    runner = _opened(state)
    runner.close(run_item(repo=REPO, run_id="batch-b1"))
    close = _pending(runner, "close")[0]
    results = tmp_path / "results.json"
    results.write_text(json.dumps([{"id": close["id"], "outcome": "archived"}]))

    result = _record(state, outbox, results)

    assert result.exit_code == 2, result.output
    assert "outcome is one of" in result.output
