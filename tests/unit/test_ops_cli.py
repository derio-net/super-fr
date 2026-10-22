"""`fr ops` — the CLI surface over the op engine (spec 2026-10-22-fr-ops R3, R17).

`status` reads, never writes; the whole group is gated by the artifact trigger.
"""

from __future__ import annotations

from fr.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_ops_group_is_registered() -> None:
    result = runner.invoke(app, ["ops", "--help"])
    assert result.exit_code == 0, result.output
    assert "status" in result.output


def test_the_ops_group_is_gated_by_the_artifact_trigger() -> None:
    """R17: the whole group, `status` included, is gated — never exempt."""
    from fr.artifacts import trigger

    assert "ops" not in trigger.READ_ONLY_COMMANDS
