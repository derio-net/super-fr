"""`fr triage board` and the board's session statuses (spec 2026-10-05 §E; R1, R7, R10).

The runner is a fake; nothing here reaches herdr, a forge or a browser.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_kanban_cmd
from fr.commands.triage_kanban_cmd import scope_args, session_statuses, write_board
from fr.triage.drive_lock import LOCK_GRACE
from fr.triage.errors import ForgeError
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
    assert "(1 batch)" in out.replace("\n", "")


def test_board_with_no_batches_still_writes_a_page_that_says_so(tmp_path: Path) -> None:
    world = World()
    world.issues[1] = "open"
    _state(tmp_path, world)
    code, out = _board(tmp_path)
    assert code == 0, out
    assert "No batches" in (tmp_path / "board.html").read_text(encoding="utf-8")


def _column(page: str, key: str) -> str:
    """The markup of one rendered column section."""
    start = page.index(f'<section class="col" data-column="{key}">')
    return page[start : page.index("</section>", start)]


def test_a_relative_dir_is_copied_as_an_absolute_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A copied command is pasted in another pane: a relative --dir would resolve there."""
    monkeypatch.chdir(tmp_path)
    assert scope_args(REPO, None, Path("state")) == [
        "--repo",
        REPO,
        "--dir",
        str((tmp_path / "state").resolve()),
    ]


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
    assert "no-such-runner" in page
    assert '<span class="pill status-unknown">' in _column(page, "running")


def test_the_copied_command_carries_dir_only_when_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, _dispatch_event("b1"))
    _use(monkeypatch, _Inspector({f"{REPO}/run/batch-b1": "idle"}))
    _board(tmp_path)  # this test passes --dir
    page = (tmp_path / "board.html").read_text(encoding="utf-8")
    assert re.search(r'data-command="fr triage batch focus b1 --repo [^"]*--dir ', page)
    facts, judgements = _loaded(tmp_path)
    path, _ = write_board(SCOPE, tmp_path, scope_args=["--repo", REPO], refresh=30)
    assert " --dir" not in path.read_text(encoding="utf-8").split("data-command=")[1].split(">")[0]


def test_write_board_is_atomic_and_reloads_judgements_from_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    _use(monkeypatch, _Inspector())
    path, cards = write_board(SCOPE, tmp_path, scope_args=["--repo", REPO], refresh=0)
    assert path == tmp_path / "board.html" and cards == 1
    assert 'id="card-b1"' in _column(path.read_text(encoding="utf-8"), "proposed")
    _setup(tmp_path, _dispatch_event("b1"))  # judgements change on disk
    write_board(SCOPE, tmp_path, scope_args=["--repo", REPO], refresh=0)
    page = path.read_text(encoding="utf-8")
    assert 'id="card-b1"' in _column(page, "running")
    assert 'id="card-b1"' not in _column(page, "proposed")
    assert [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp" or ".tmp" in p.name] == []


def test_write_board_judges_idleness_by_the_wall_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """driver-sessions R8: the dispatch in the fixture is days old by the real clock, and the
    runner reports the session idle with no PR, so the card is flagged and says why."""
    _setup(tmp_path, _dispatch_event("b1"))
    _use(monkeypatch, _Inspector({f"{REPO}/run/batch-b1": "idle"}))
    path, _ = write_board(SCOPE, tmp_path, scope_args=["--repo", REPO], refresh=0)
    card = _column(path.read_text(encoding="utf-8"), "running")
    assert re.search(
        r"idle, dispatched \d+ min ago, no PR as of \d{4}-\d\d-\d\d \d\d:\d\d UTC", card
    )
    assert 'class="card needs-you"' in card


# ---------------------------------------------------------------- --watch (R12)


class _Watch:
    """The loop's seams: collect, write and sleep recorded in order; a stop after *stop* sleeps."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop: int = 3) -> None:
        self.calls: list[str] = []
        self.sleeps: list[float] = []
        self.tmp_path, self.stop = tmp_path, stop
        self.on_sleep: Any = None
        monkeypatch.setattr(
            triage_kanban_cmd, "recollect", lambda s, t: self.calls.append("collect")
        )
        real = triage_kanban_cmd.write_board

        def _write(*a: Any, **kw: Any) -> Any:
            self.calls.append("write")
            return real(*a, **kw)

        monkeypatch.setattr(triage_kanban_cmd, "write_board", _write)
        monkeypatch.setattr(triage_kanban_cmd, "_sleep", self._sleep)
        _use(monkeypatch, _Inspector())

    def _sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        if self.on_sleep:
            self.on_sleep(len(self.sleeps))
        if len(self.sleeps) >= self.stop:
            raise KeyboardInterrupt


def _lock(tmp_path: Path, pid: int) -> None:
    (tmp_path / "drive.lock").write_text(json.dumps({"pid": pid, "started": "x"}))


def test_watch_collects_then_writes_every_interval_until_interrupted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    w = _Watch(tmp_path, monkeypatch)
    code, out = _board(tmp_path, "--watch")
    assert code == 0, out
    assert w.calls == ["collect", "write"] * 3
    assert w.sleeps == [60, 60, 60]  # the default interval
    assert (tmp_path / "board.html").exists()


def test_watch_takes_the_interval_and_refuses_less_than_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    w = _Watch(tmp_path, monkeypatch, stop=1)
    assert _board(tmp_path, "--watch", "--interval", "7")[0] == 0
    assert w.sleeps == [7]
    assert _board(tmp_path, "--watch", "--interval", "0")[0] == 2


def test_watch_refuses_while_a_live_drive_holds_the_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    w = _Watch(tmp_path, monkeypatch)
    _lock(tmp_path, os.getpid())
    code, out = _board(tmp_path, "--watch")
    assert code == 2 and "drive" in out and str(os.getpid()) in out
    assert w.calls == [] and w.sleeps == []


def test_watch_ignores_a_stale_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path)
    w = _Watch(tmp_path, monkeypatch, stop=1)
    _lock(tmp_path, 999_999_999)
    code, out = _board(tmp_path, "--watch")
    assert code == 0, out
    assert w.calls == ["collect", "write"]


def test_an_iteration_that_finds_the_lock_held_skips_and_says_so_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    w = _Watch(tmp_path, monkeypatch, stop=4)
    w.on_sleep = lambda n: _lock(tmp_path, os.getpid()) if n == 1 else None
    code, out = _board(tmp_path, "--watch")
    assert code == 0, out
    assert w.calls == ["collect", "write"]  # the drive owns the board from the second iteration
    assert out.count("skipping") == 1


def test_a_collect_that_fails_warns_once_and_the_loop_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    w = _Watch(tmp_path, monkeypatch, stop=3)

    def _boom(scope: Any, target: Path) -> None:
        raise ForgeError("forge said no")

    monkeypatch.setattr(triage_kanban_cmd, "recollect", _boom)
    code, out = _board(tmp_path, "--watch")
    assert code == 0, out
    assert out.count("forge said no") == 1 and w.calls == ["write"] * 3


def test_watch_refuses_a_young_unreadable_lock_like_the_drive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lock not yet whole is a driver starting up for LOCK_GRACE (review p3-r1)."""
    _setup(tmp_path)
    w = _Watch(tmp_path, monkeypatch)
    (tmp_path / "drive.lock").write_text("")
    code, out = _board(tmp_path, "--watch")
    assert code == 2 and "starting up" in out and w.calls == []


def test_watch_ignores_an_old_unreadable_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    w = _Watch(tmp_path, monkeypatch, stop=1)
    lock = tmp_path / "drive.lock"
    lock.write_text("")
    old = time.time() - LOCK_GRACE - 5
    os.utime(lock, (old, old))
    assert _board(tmp_path, "--watch")[0] == 0 and w.calls == ["collect", "write"]


def test_any_collect_failure_warns_once_and_the_loop_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    w = _Watch(tmp_path, monkeypatch, stop=3)

    def _boom(scope: Any, target: Path) -> None:
        raise OSError("disk\nfull")

    monkeypatch.setattr(triage_kanban_cmd, "recollect", _boom)
    code, out = _board(tmp_path, "--watch")
    assert code == 0, out
    assert out.count("disk full") == 1 and w.calls == ["write"] * 3


def test_a_render_that_fails_or_refuses_never_ends_the_watch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    w = _Watch(tmp_path, monkeypatch, stop=3)
    seen: list[int] = []

    def _write(*a: Any, **kw: Any) -> Any:
        seen.append(1)
        if len(seen) == 1:
            raise OSError("read-only")
        triage_kanban_cmd._fail("no facts.json")

    monkeypatch.setattr(triage_kanban_cmd, "write_board", _write)
    code, out = _board(tmp_path, "--watch")
    assert code == 0, out
    assert len(seen) == 3 and w.calls == ["collect"] * 3
    assert out.count("read-only") == 1 and out.count("no facts.json") == 1


def test_watch_resumes_when_the_drive_lock_goes_and_re_arms_the_skip_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    w = _Watch(tmp_path, monkeypatch, stop=6)
    lock = tmp_path / "drive.lock"

    def _flip(n: int) -> None:
        if n in (1, 4):
            _lock(tmp_path, os.getpid())
        if n in (2, 5):
            lock.unlink()

    w.on_sleep = _flip
    code, out = _board(tmp_path, "--watch")
    assert code == 0, out
    assert (
        w.calls == ["collect", "write"] * 4
    )  # iterations 1, 3, 4 and 6; 2 and 5 find the lock held
    assert out.count("skipping") == 2


def test_a_count_of_batches_is_spelled_batches(tmp_path: Path) -> None:
    from fr.triage.render import plural

    assert plural(2, "batch") == "2 batches" and plural(1, "batch") == "1 batch"
    assert plural(2, "repo") == "2 repos"
