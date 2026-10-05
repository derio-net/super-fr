"""`fr triage board` and the board's session statuses (spec 2026-10-05 §E; R1, R7, R10).

The runner is a fake; nothing here reaches herdr, a forge or a browser.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_kanban_cmd
from fr.commands.triage_kanban_cmd import scope_args, session_statuses, write_board
from fr.triage.model import Scope, load_facts, load_judgements
from typer.testing import CliRunner

from tests.unit.test_triage_batch_drive_cmd import (
    DISPATCHED,
    REPO,
    World,
    _batch,
    _dispatch_event,
    _state,
)

CLOSEOUT = f"      - {{kind: closeout, at: {DISPATCHED}, runner: fake, handle: c}}\n"
HAND = f"      - {{kind: closeout, at: {DISPATCHED}, runner: hand, handle: c}}\n"
SCOPE = Scope(kind="repo", target=REPO)


class _Inspector:
    def __init__(self, statuses: dict[str, str] | None = None, refusal: str | None = None) -> None:
        self.statuses = statuses or {}
        self.refusal = refusal
        self.asked: list[Any] = []

    def preflight(self, items: Any) -> str | None:
        return self.refusal

    def session_statuses(self, items: Any) -> dict[str, str]:
        self.asked = list(items)
        return {i.id: self.statuses.get(i.id, "absent") for i in items}


class _NoInspect:
    def preflight(self, items: Any) -> str | None:
        return None


class _Raises(_Inspector):
    def session_statuses(self, items: Any) -> dict[str, str]:
        raise RuntimeError("herdr tab list failed:\nboom")


def _setup(tmp_path: Path, *events: str, **kw: Any) -> Path:
    world = World()
    world.issues[1] = "open"
    return _state(tmp_path, world, _batch("b1", 1, events="".join(events), **kw))


def _use(monkeypatch: pytest.MonkeyPatch, runner: Any) -> None:
    monkeypatch.setattr(triage_kanban_cmd, "load_runner", lambda name: runner)


def _loaded(tmp_path: Path) -> tuple[Any, Any]:
    return load_facts(tmp_path / "facts.json"), load_judgements(tmp_path / "judgements.yaml")


def _board(tmp_path: Path, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app, ["triage", "board", "--repo", REPO, "--dir", str(tmp_path), *args]
    )
    return result.exit_code, result.output


# ----------------------------------------------------------------- scope args


def test_scope_args_name_the_repo_or_org_and_dir_only_when_given() -> None:
    assert scope_args("o/r", None, None) == ["--repo", "o/r"]
    assert scope_args(None, "acme", None) == ["--org", "acme"]
    assert scope_args("o/r", None, Path("/x y")) == ["--repo", "o/r", "--dir", "/x y"]


# ------------------------------------------------------------- session_statuses


def test_a_runners_statuses_reach_the_result_by_item_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, _dispatch_event("b1"))
    runner = _Inspector({f"{REPO}/run/batch-b1": "blocked"})
    _use(monkeypatch, runner)
    statuses, notes = session_statuses(*reversed(_loaded(tmp_path)))
    assert statuses == {f"{REPO}/run/batch-b1": "blocked"} and notes == []


def test_probe_items_carry_the_wave_group(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, _dispatch_event("b1"), wave=2)
    runner = _Inspector()
    _use(monkeypatch, runner)
    facts, judgements = _loaded(tmp_path)
    session_statuses(judgements, facts, prefix="mine")
    (item,) = runner.asked
    assert item.payload["group"] == "mine-wave-2" and item.unit == "run"


def test_a_hand_closeout_is_never_probed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, _dispatch_event("b1"), HAND)
    runner = _Inspector()
    _use(monkeypatch, runner)
    facts, judgements = _loaded(tmp_path)
    session_statuses(judgements, facts)
    assert [i.id for i in runner.asked] == [f"{REPO}/run/batch-b1"]


def test_a_runner_closeout_is_probed_with_its_own_item(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, _dispatch_event("b1"), CLOSEOUT)
    runner = _Inspector()
    _use(monkeypatch, runner)
    facts, judgements = _loaded(tmp_path)
    session_statuses(judgements, facts)
    assert [i.id for i in runner.asked] == [f"{REPO}/run/batch-b1", f"{REPO}/run/closeout-b1"]


def test_a_batch_never_dispatched_is_not_probed_and_loads_no_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)

    def never(name: str) -> Any:
        raise AssertionError("no runner should load")

    monkeypatch.setattr(triage_kanban_cmd, "load_runner", never)
    facts, judgements = _loaded(tmp_path)
    assert session_statuses(judgements, facts) == ({}, [])


@pytest.mark.parametrize(
    ("runner", "needle"),
    [
        (_Inspector(refusal="not inside herdr"), "not inside herdr"),
        (_NoInspect(), "cannot report"),
        (_Raises(), "boom"),
    ],
)
def test_a_failing_runner_is_unknown_with_one_note_and_nothing_printed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runner: Any,
    needle: str,
) -> None:
    _setup(tmp_path, _dispatch_event("b1"), CLOSEOUT)
    _use(monkeypatch, runner)
    facts, judgements = _loaded(tmp_path)
    statuses, notes = session_statuses(judgements, facts)
    assert statuses == {}
    assert len(notes) == 1 and needle in notes[0] and "`fake`" in notes[0]
    assert "\n" not in notes[0]
    captured = capsys.readouterr()
    assert "error:" not in captured.out + captured.err


def test_an_unloadable_runner_is_one_note_and_no_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _setup(tmp_path, _dispatch_event("b1").replace("runner: fake", "runner: no-such-runner"))
    facts, judgements = _loaded(tmp_path)
    statuses, notes = session_statuses(judgements, facts)
    assert statuses == {}
    assert len(notes) == 1 and "no-such-runner" in notes[0] and "could not be loaded" in notes[0]
    captured = capsys.readouterr()
    assert "error:" not in captured.out + captured.err


def test_an_unknown_status_value_reads_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, _dispatch_event("b1"))
    _use(monkeypatch, _Inspector({f"{REPO}/run/batch-b1": "sleeping"}))
    facts, judgements = _loaded(tmp_path)
    statuses, _ = session_statuses(judgements, facts)
    assert statuses == {f"{REPO}/run/batch-b1": "unknown"}


def test_a_missing_fr_dispatch_is_a_note_not_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, _dispatch_event("b1"))
    monkeypatch.setattr(triage_kanban_cmd.importlib.util, "find_spec", lambda name: None)
    facts, judgements = _loaded(tmp_path)
    statuses, notes = session_statuses(judgements, facts)
    assert statuses == {} and len(notes) == 1 and "fr-dispatch" in notes[0]


# ------------------------------------------------------------------ the command


def test_board_writes_board_html_and_prints_its_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, _dispatch_event("b1"))
    _use(monkeypatch, _Inspector({f"{REPO}/run/batch-b1": "working"}))
    code, out = _board(tmp_path)
    assert code == 0, out
    page = (tmp_path / "board.html").read_text(encoding="utf-8")
    assert str(tmp_path / "board.html") in out.replace("\n", "")
    assert 'id="card-b1"' in page and "working" in page


def test_board_with_no_batches_still_writes_a_page_that_says_so(tmp_path: Path) -> None:
    world = World()
    world.issues[1] = "open"
    _state(tmp_path, world)
    code, out = _board(tmp_path)
    assert code == 0, out
    assert "No batches" in (tmp_path / "board.html").read_text(encoding="utf-8")


def test_refresh_zero_turns_the_reload_off_and_default_is_thirty(tmp_path: Path) -> None:
    _setup(tmp_path)
    _board(tmp_path, "--refresh", "0")
    assert 'data-refresh="0"' in (tmp_path / "board.html").read_text(encoding="utf-8")
    _board(tmp_path)
    assert 'data-refresh="30"' in (tmp_path / "board.html").read_text(encoding="utf-8")


def test_a_negative_refresh_is_refused(tmp_path: Path) -> None:
    _setup(tmp_path)
    code, _ = _board(tmp_path, "--refresh", "-1")
    assert code == 2


def test_an_unloadable_runner_never_fails_the_board_and_shows_a_page_note(tmp_path: Path) -> None:
    _setup(tmp_path, _dispatch_event("b1").replace("runner: fake", "runner: no-such-runner"))
    code, out = _board(tmp_path)
    assert code == 0 and "error:" not in out
    page = (tmp_path / "board.html").read_text(encoding="utf-8")
    assert "no-such-runner" in page and "unknown" in page


def test_the_copied_command_carries_dir_only_when_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, _dispatch_event("b1"))
    _use(monkeypatch, _Inspector({f"{REPO}/run/batch-b1": "idle"}))
    _board(tmp_path)  # this test passes --dir
    page = (tmp_path / "board.html").read_text(encoding="utf-8")
    assert re.search(r'data-command="fr triage batch focus b1 --repo [^"]*--dir ', page)
    facts, judgements = _loaded(tmp_path)
    path = write_board(SCOPE, tmp_path, scope_args=["--repo", REPO], refresh=30)
    assert " --dir" not in path.read_text(encoding="utf-8").split("data-command=")[1].split(">")[0]


def test_write_board_is_atomic_and_reloads_judgements_from_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    _use(monkeypatch, _Inspector())
    path = write_board(SCOPE, tmp_path, scope_args=["--repo", REPO], refresh=0)
    assert path == tmp_path / "board.html" and "proposed" in path.read_text(encoding="utf-8")
    _setup(tmp_path, _dispatch_event("b1"))  # judgements change on disk
    write_board(SCOPE, tmp_path, scope_args=["--repo", REPO], refresh=0)
    assert 'data-column="running"' in path.read_text(encoding="utf-8")
    assert [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp" or ".tmp" in p.name] == []
