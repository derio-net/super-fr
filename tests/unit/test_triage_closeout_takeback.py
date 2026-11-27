"""A failed close-out take-back reports both errors (spec closeout-state R1-R3, gh#1601)."""

from fr.triage import drive_errors


def test_the_fail_message_attribute_is_unchanged() -> None:
    assert drive_errors.FAIL_MESSAGE == "fr_message"


def test_fail_text_reads_each_kind_of_exception() -> None:
    import typer
    from fr.triage.drive_errors import fail_exit, fail_text

    assert fail_text(fail_exit("boom")) == "boom"
    assert fail_text(ValueError("x")) == "x"
    bare = fail_text(typer.Exit(code=2))
    assert bare and "2" in bare


# ------------------------------------------------------- the two take-backs (R1-R3)

from dataclasses import replace  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from fr.commands import triage_batch_cmd  # noqa: E402
from fr.triage import batch as batch_mod  # noqa: E402
from fr.triage.drive_errors import fail_exit  # noqa: E402
from fr.triage.errors import TriageError  # noqa: E402
from fr.triage.model import load_judgements  # noqa: E402
from fr.triage.privacy import VisibilityUnreadable  # noqa: E402

from tests.unit.test_triage_batch_closeout_cmd import _landed as _world_landed  # noqa: E402
from tests.unit.test_triage_batch_dispatch import FakeRunner  # noqa: E402
from tests.unit.test_triage_batch_drive_cmd import (  # noqa: E402
    DriveCheckout,
    World,
    _drive,
    _lines,
    _sandbox,  # noqa: F401 - the drive tests' autouse sandbox
    checkout_fixture,  # noqa: F401 - registered as `checkout`
    runner_fixture,  # noqa: F401 - registered as `runner`
    world_fixture,  # noqa: F401 - registered as `world`
)


def _fail_takeback(monkeypatch: pytest.MonkeyPatch, make: object = TriageError) -> None:
    """Every `save_closeouts` after the marker's own write raises `make("store moved")`."""
    real = triage_batch_cmd.save_closeouts
    seen: list[int] = []

    def wrapped(path: Path, closeouts: list, *, read: list) -> object:
        seen.append(1)
        if len(seen) > 1:
            raise make("store moved")  # type: ignore[operator]
        return real(path, closeouts, read=read)

    monkeypatch.setattr(triage_batch_cmd, "save_closeouts", wrapped)


@pytest.mark.parametrize(
    "make",
    [TriageError, fail_exit, VisibilityUnreadable],
    ids=["triage", "fail-exit", "visibility"],
)
def test_a_collected_start_whose_takeback_fails_reports_both_errors_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch, make: object,
) -> None:  # fmt: skip
    _world_landed(world, tmp_path, "b1")
    checkout.released = True
    runner.fail = RuntimeError("tab refused")
    _fail_takeback(monkeypatch, make)

    code, out = _drive(tmp_path, "--once", "--yes")

    (line,) = _lines(out, "closeout")
    assert "tab refused" in line and "store moved" in line
    assert "exited 2" not in line  # a `fail_exit`'s carried text, never its code
    assert code == 1, out  # failed_write: --once exits 1, nothing escaped the action
    assert "Traceback" not in out


def test_a_takeback_that_keeps_failing_is_said_once() -> None:
    """The dedupe key is the dispatch error's, so the take-back's words never re-say it."""
    driver = object.__new__(triage_batch_cmd._Driver)
    driver.reported, driver.failed_write = set(), False
    batch = type("B", (), {"id": "b1"})()
    exc = RuntimeError("tab refused")

    first = driver._dispatch_failed(batch, "m", exc, "; taking back its start record failed too: x")
    second = driver._dispatch_failed(
        batch, "m", exc, "; taking back its start record failed too: y"
    )

    assert first.startswith("stopped: ") and second.startswith("stopped again")
    assert first.endswith("failed too: x")
    assert driver.failed_write


def test_a_collected_start_whose_takeback_succeeds_is_unchanged(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _world_landed(world, tmp_path, "b1")
    checkout.released = True
    runner.fail = RuntimeError("tab refused")

    code, out = _drive(tmp_path, "--once", "--yes")

    (line,) = _lines(out, "closeout")
    assert "tab refused" in line and "taking back" not in line
    assert load_judgements(tmp_path / "judgements.yaml").closeouts == []  # marker taken back


def _per_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plan the older, per-batch close-out (`recorded=False`, no members)."""
    real = triage_batch_cmd.drive_pass

    def plan(snap: object) -> object:
        out = real(snap)
        actions = [
            replace(a, items=(), batch="b1", recorded=False) if a.kind == "closeout" else a
            for a in out.actions
        ]
        return replace(out, actions=actions)

    monkeypatch.setattr(triage_batch_cmd, "drive_pass", plan)


def test_a_per_batch_start_whose_takeback_fails_reports_both_and_prints_no_error(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    _world_landed(world, tmp_path, "b1")
    checkout.released = True
    runner.fail = RuntimeError("tab refused")
    _per_batch(monkeypatch)
    real_save = triage_batch_cmd._save
    seen: list[int] = []

    def save(*a: object, **kw: object) -> None:
        seen.append(1)
        if len(seen) > 1:  # the start record's own write succeeded; the take-back fails
            raise TriageError("store moved")
        real_save(*a, **kw)

    monkeypatch.setattr(triage_batch_cmd, "_save", save)

    code, out = _drive(tmp_path, "--once", "--yes")

    (line,) = _lines(out, "closeout")
    assert "tab refused" in line and "store moved" in line
    assert "error:" not in out and "error:" not in capsys.readouterr().err
    assert batch_mod  # the module the take-back's writer lives beside


def test_a_per_batch_start_whose_takeback_succeeds_removes_the_event(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _world_landed(world, tmp_path, "b1")
    checkout.released = True
    runner.fail = RuntimeError("tab refused")
    _per_batch(monkeypatch)

    _drive(tmp_path, "--once", "--yes")

    (b,) = load_judgements(tmp_path / "judgements.yaml").batches
    assert [e.kind for e in b.events] == ["dispatch"]
