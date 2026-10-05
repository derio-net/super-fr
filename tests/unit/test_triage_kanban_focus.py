"""`fr triage batch focus` (spec 2026-10-05 §E; R8)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_kanban_cmd
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
HAND_CLOSEOUT = f"      - {{kind: closeout, at: {DISPATCHED}, runner: hand, handle: c}}\n"


class _Focuser:
    def __init__(self, result: bool = True, refusal: str | None = None) -> None:
        self.result, self.refusal = result, refusal
        self.preflighted: list[Any] = []
        self.focused: list[Any] = []

    def preflight(self, items: Any) -> str | None:
        self.preflighted = list(items)
        return self.refusal

    def focus(self, item: Any) -> bool:
        self.focused.append(item)
        return self.result


class _NoFocus:
    def preflight(self, items: Any) -> str | None:
        return None


def _focus(tmp_path: Path, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app,
        ["triage", "batch", "focus", *args, "--repo", REPO, "--dir", str(tmp_path)],
    )
    return result.exit_code, result.output


def _setup(tmp_path: Path, *events: str, **kw: Any) -> Path:
    world = World()
    world.issues[1] = "open"
    return _state(tmp_path, world, _batch("b1", 1, events="".join(events), **kw))


def _use(monkeypatch: pytest.MonkeyPatch, runner: Any) -> None:
    monkeypatch.setattr(triage_kanban_cmd, "load_runner", lambda name: runner)


def test_an_unknown_batch_is_refused(tmp_path: Path) -> None:
    _setup(tmp_path)
    code, out = _focus(tmp_path, "nope")
    assert code == 2 and "no batch 'nope'" in out


def test_a_batch_with_no_dispatch_event_is_refused(tmp_path: Path) -> None:
    _setup(tmp_path)
    code, out = _focus(tmp_path, "b1")
    assert code == 2 and "no dispatch event" in out


def test_closeout_with_no_closeout_event_is_refused(tmp_path: Path) -> None:
    _setup(tmp_path, _dispatch_event("b1"))
    code, out = _focus(tmp_path, "b1", "--closeout")
    assert code == 2 and "no close-out event" in out


def test_an_adopted_closeout_has_no_session(tmp_path: Path) -> None:
    _setup(tmp_path, _dispatch_event("b1"), HAND_CLOSEOUT)
    code, out = _focus(tmp_path, "b1", "--closeout")
    assert code == 2 and "an adopted close-out has no session" in out


def test_an_unloadable_runner_is_one_line_and_no_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, _dispatch_event("b1"))

    def boom(name: str) -> Any:
        raise RuntimeError("adapter exploded")

    monkeypatch.setattr(triage_kanban_cmd, "load_runner", boom)
    code, out = _focus(tmp_path, "b1")
    assert code == 2
    assert "adapter exploded" in out and "Traceback" not in out
    assert len([ln for ln in out.splitlines() if ln.strip()]) == 1


def test_a_runner_without_focus_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, _dispatch_event("b1"))
    _use(monkeypatch, _NoFocus())
    code, out = _focus(tmp_path, "b1")
    assert code == 2 and "cannot focus" in out


def test_a_failing_preflight_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, _dispatch_event("b1"))
    runner = _Focuser(refusal="not inside herdr")
    _use(monkeypatch, runner)
    code, out = _focus(tmp_path, "b1")
    assert code == 2 and "not inside herdr" in out and runner.focused == []


def test_no_live_session_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, _dispatch_event("b1"))
    _use(monkeypatch, _Focuser(result=False))
    code, out = _focus(tmp_path, "b1")
    assert code == 2 and "no live session" in out


def test_focus_succeeds_and_probes_the_batch_item_with_its_wave_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, _dispatch_event("b1"), wave=2)
    runner = _Focuser()
    _use(monkeypatch, runner)
    code, out = _focus(tmp_path, "b1")
    assert code == 0, out
    (item,) = runner.focused
    assert item.id == f"{REPO}/run/batch-b1" and item.unit == "run"
    assert item.payload["group"] == "drive-wave-2"
    assert runner.preflighted == [item]


def test_closeout_focus_probes_the_closeout_item(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, _dispatch_event("b1"), CLOSEOUT)
    runner = _Focuser()
    _use(monkeypatch, runner)
    code, out = _focus(tmp_path, "b1", "--closeout")
    assert code == 0, out
    assert runner.focused[0].id == f"{REPO}/run/closeout-b1"
