"""R6: `fr journal add --gate` help is built from `fr.gates.Gate`, byte-identical to before."""

from __future__ import annotations

import click
import typer.main
from fr.cli import app
from fr.gates import GATES

_TODAY = (
    "--kind decision only: the gate role that owns it "
    "(developer|reviewer|tester|devops|owner|security)."
)


def _gate_help() -> str:
    root = typer.main.get_command(app)
    assert isinstance(root, click.Group)
    journal = root.commands["journal"]
    assert isinstance(journal, click.Group)
    add = journal.commands["add"]
    (option,) = [p for p in add.params if p.name == "gate"]
    assert isinstance(option, click.Option) and option.help is not None
    return option.help


def test_the_gate_help_is_unchanged() -> None:
    assert _gate_help() == _TODAY


def test_the_gate_help_names_every_gate() -> None:
    text = _gate_help()
    assert all(gate in text for gate in GATES)
