"""What a run-engine check concluded, as data a command prints (spec 2026-11-27-run-verdict R1).

Audit design 6.1 (docs/superpowers/audits/2026-11-16-architecture-review.md): `fr/run`
decides, `fr/commands` prints. A check returns a `Verdict` (or raises `RunRefusal`), each
line of it a `Say` that carries exactly what the old `err_console.print` call passed, so
the command's adapter prints the same bytes. `Say`'s defaults are `rich.Console.print`'s
own, so `Say(text)` prints what `print(text)` printed.

Engine code: stdlib only, no `typer`, no `rich`, no `fr.commands`
(`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class Say:
    """One line as a command prints it to stderr, with that print's own options."""

    text: str
    markup: bool = True
    soft_wrap: bool = False
    style: str | None = None


@dataclass(frozen=True)
class Verdict[T]:
    """A check's result: its witness, or the refusal lines and exit code; warnings print first."""

    witness: T | None
    refusal: tuple[Say, ...] = ()
    exit_code: int = 2
    warnings: tuple[Say, ...] = ()


class RunRefusal(Exception):  # noqa: N818 — the spec's name (R1): a refusal, not an error
    """A refusal raised by run-engine code; the calling command prints `lines` and exits."""

    def __init__(self, lines: tuple[Say, ...], exit_code: int = 2) -> None:
        super().__init__("\n".join(line.text for line in lines))
        self.lines = lines
        self.exit_code = exit_code


Warn = Callable[[Say], None]
"""How run-engine code sends a warning to the command that called it."""


@contextmanager
def noted_on_crash(warnings: list[Say]) -> Iterator[None]:
    """Attach the warnings a `Verdict` has queued so far to an unexpected exception.

    A queued warning prints only when the command settles the `Verdict`; an error other
    than `RunRefusal` escaping first would drop it. As exception notes it rides the
    traceback instead (lens finding l-errors-r2).
    """
    try:
        yield
    except RunRefusal:
        raise
    except Exception as e:
        for warning in warnings:
            e.add_note(warning.text)
        raise
