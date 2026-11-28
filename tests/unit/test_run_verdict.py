"""The typed verdict and the adapter that prints it (spec 2026-11-27-run-verdict R1-R3)."""

from __future__ import annotations

import dataclasses
from io import StringIO

import pytest
import typer
from fr.commands import run_cmd
from fr.run.verdict import RunRefusal, Say, Verdict
from rich.console import Console


def _recording() -> Console:
    return Console(
        file=StringIO(), width=80, force_terminal=True, color_system="standard", highlight=False
    )


def _out(console: Console) -> str:
    file = console.file
    assert isinstance(file, StringIO)
    return file.getvalue()


def test_say_defaults_are_rich_console_print_defaults() -> None:
    line = Say("x")
    assert (line.text, line.markup, line.soft_wrap, line.style) == ("x", True, False, None)


def test_say_and_verdict_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        Say("x").text = "y"  # type: ignore[misc]
    verdict: Verdict[str] = Verdict("w")
    assert (verdict.refusal, verdict.exit_code, verdict.warnings) == ((), 2, ())
    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict.witness = "v"  # type: ignore[misc]


def test_run_refusal_keeps_lines_exit_code_and_cause() -> None:
    lines = (Say("a"), Say("b", markup=False))
    assert RunRefusal(lines).exit_code == 2
    cause = ValueError("boom")
    try:
        try:
            raise cause
        except ValueError as e:
            raise RunRefusal(lines, exit_code=75) from e
    except RunRefusal as r:
        assert r.lines == lines
        assert r.exit_code == 75
        assert r.__cause__ is cause


def _expected(*prints: tuple[str, dict[str, object]]) -> str:
    console = _recording()
    for text, kwargs in prints:
        console.print(text, **kwargs)  # type: ignore[arg-type]
    return _out(console)


def test_settle_prints_warnings_then_refusal_with_each_lines_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console = _recording()
    monkeypatch.setattr(run_cmd, "err_console", console)
    verdict: Verdict[str] = Verdict(
        None,
        refusal=(
            Say("[bold]refused[/bold]"),
            Say("[x] " + "long " * 30, markup=False, soft_wrap=True),
        ),
        exit_code=75,
        warnings=(Say("careful", style="red"),),
    )
    with pytest.raises(typer.Exit) as exc:
        run_cmd._settle(verdict)
    assert exc.value.exit_code == 75
    out = _out(console)
    assert "\x1b[31m" in out
    assert out.index("careful") < out.index("refused")
    assert out == _expected(
        ("careful", {"style": "red"}),
        ("[bold]refused[/bold]", {}),
        ("[x] " + "long " * 30, {"markup": False, "soft_wrap": True}),
    )


def test_settle_returns_the_witness_after_its_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    console = _recording()
    monkeypatch.setattr(run_cmd, "err_console", console)
    assert run_cmd._settle(Verdict("ok", warnings=(Say("note"),))) == "ok"
    assert _out(console) == _expected(("note", {}))


def test_refusals_prints_lines_and_exits_keeping_the_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console = _recording()
    monkeypatch.setattr(run_cmd, "err_console", console)
    cause = OSError("disk")
    with pytest.raises(typer.Exit) as exc:
        with run_cmd._refusals():
            try:
                raise cause
            except OSError as e:
                raise RunRefusal((Say("[red]no[/red]"), Say("a [b]", markup=False)), 3) from e
    assert exc.value.exit_code == 3
    assert exc.value.__cause__ is cause
    assert _out(console) == _expected(("[red]no[/red]", {}), ("a [b]", {"markup": False}))


def test_refusals_passes_through_without_a_refusal() -> None:
    with run_cmd._refusals():
        pass


def test_the_unobserved_channel_is_the_one_run_cmd_takes() -> None:
    from fr.run import unobserved

    run_cmd._take_unobserved()  # drain anything an earlier test left
    unobserved.note_unobserved("questions")
    unobserved.note_unobserved("questions")
    unobserved.note_unobserved("commands")
    assert run_cmd._take_unobserved() == {"unobserved": "questions,commands"}
    assert run_cmd._take_unobserved() == {}
    assert run_cmd._UNOBSERVED is unobserved.UNOBSERVED
