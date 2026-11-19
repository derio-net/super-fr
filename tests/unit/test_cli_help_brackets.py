"""Rich markup must never eat bracketed text in a command's help (spec 2026-11-19 R4, R5)."""

from __future__ import annotations

import re
from collections import Counter

import click
import typer
import typer.main
from fr.cli import app
from typer.testing import CliRunner

_BOX = str.maketrans("", "", "│╭╮╰╯─")
_BRACKET = re.compile(r"\[[^\[\]]*\]")


def _norm(text: str) -> str:
    return " ".join(text.translate(_BOX).split())


def _spans(text: str | None) -> list[str]:
    if not text:
        return []
    return [_norm(m) for m in _BRACKET.findall(text.replace("\\[", "["))]


def _walk(cmd: click.Command, path: tuple[str, ...]):
    yield path, cmd
    if isinstance(cmd, click.Group):
        for name, sub in cmd.commands.items():
            yield from _walk(sub, (*path, name))


def missing_spans(root_app: typer.Typer, path: tuple[str, ...] = ("fr",)) -> list[str]:
    """Every `[...]` span in a help string that the rendered --help lacks."""
    root = typer.main.get_command(root_app)
    found: list[str] = []
    runner = CliRunner()
    env = {"COLUMNS": "1000", "TERMINAL_WIDTH": "1000"}
    for cmd_path, cmd in _walk(root, path):
        expected: list[str] = _spans(cmd.help)
        expected += [s for p in cmd.params for s in _spans(getattr(p, "help", None))]
        if not expected:
            continue
        ctx_args = list(cmd_path[1:]) + ["--help"]
        result = runner.invoke(root_app, ctx_args, env=env)
        rendered = _norm(result.output)
        # count-based: a span the page shows elsewhere (usage line, another help) must
        # not mask an eaten one, so the page needs it as often as the sources hold it
        for span, n in Counter(expected).items():
            if rendered.count(span) < n:
                found.append(f"{' '.join(cmd_path)}: {span}")
    return found


def test_the_checker_reports_an_unescaped_bracket() -> None:
    demo = typer.Typer()

    @demo.command()
    def go(tool: str = typer.Option("", help="a <x>[@<v>] ref")) -> None: ...

    @demo.command()
    def other() -> None: ...

    problems = missing_spans(demo, ("demo",))
    assert problems and "[@<v>]" in problems[0]


def test_the_checker_passes_an_escaped_bracket() -> None:
    demo = typer.Typer()

    @demo.command()
    def go(tool: str = typer.Option("", help=r"a <x>\[@<v>] ref")) -> None: ...

    @demo.command()
    def other() -> None: ...

    assert missing_spans(demo, ("demo",)) == []


def test_a_duplicated_span_with_one_copy_eaten_is_reported() -> None:
    demo = typer.Typer()

    @demo.command()
    def go(
        a: str = typer.Option("", help=r"shown \[bold] here"),
        b: str = typer.Option("", help="eaten [bold] here"),
    ) -> None: ...

    @demo.command()
    def other() -> None: ...

    # one [bold] survives (escaped), the other is eaten: presence alone would pass
    problems = missing_spans(demo, ("demo",))
    assert problems and "[bold]" in problems[0]


def test_a_span_also_in_the_usage_line_does_not_mask_an_eaten_one() -> None:
    demo = typer.Typer()

    @demo.command()
    def go(tool: str = typer.Option("", help="see [OPTIONS][bold]")) -> None: ...

    @demo.command()
    def other() -> None: ...

    problems = missing_spans(demo, ("demo",))
    assert any("[bold]" in p for p in problems)


def test_every_fr_help_shows_its_bracketed_text() -> None:
    problems = missing_spans(app)
    assert problems == [], "bracketed help text eaten by Rich markup:\n" + "\n".join(problems)
