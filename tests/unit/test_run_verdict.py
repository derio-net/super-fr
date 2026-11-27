"""The typed verdict and the adapter that prints it (spec 2026-11-27-run-verdict R1-R3)."""

from __future__ import annotations

from fr.run.verdict import Say


def test_say_defaults_are_rich_console_print_defaults() -> None:
    line = Say("x")
    assert (line.text, line.markup, line.soft_wrap, line.style) == ("x", True, False, None)


def test_say_and_verdict_are_frozen() -> None:
    import dataclasses

    import pytest

    from fr.run.verdict import Verdict

    with pytest.raises(dataclasses.FrozenInstanceError):
        Say("x").text = "y"  # type: ignore[misc]
    verdict: Verdict[str] = Verdict("w")
    assert (verdict.refusal, verdict.exit_code, verdict.warnings) == ((), 2, ())
    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict.witness = "v"  # type: ignore[misc]


def test_run_refusal_keeps_lines_exit_code_and_cause() -> None:
    from fr.run.verdict import RunRefusal

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
