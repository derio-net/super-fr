"""The `smoke` set (spec 2026-11-19-local-suite-cost §3.E): one CLI round trip per
top-level `fr` command group. `--fr-scope` always runs it, whatever changed, so a
broken import or registration anywhere in the CLI shows in the fast tier too."""

from __future__ import annotations

import pytest
import typer
from fr.cli import app
from typer.testing import CliRunner

_ROOT = typer.main.get_command(app)
COMMANDS = sorted(_ROOT.commands)  # type: ignore[attr-defined]


@pytest.mark.smoke
@pytest.mark.parametrize("command", COMMANDS)
def test_every_top_level_command_answers_its_help(command: str) -> None:
    result = CliRunner().invoke(app, [command, "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage" in result.output


@pytest.mark.smoke
def test_the_smoke_set_covers_every_top_level_command() -> None:
    assert len(COMMANDS) >= 30, COMMANDS
