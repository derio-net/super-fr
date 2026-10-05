"""super-fr#746 — the shell and the integrations must run the same `fr`.

A harness's shell tool runs `zsh -c`, which re-reads `~/.zshenv` and can
rebuild PATH; its hooks and plugin spawn `fr` without that shell. So PATH order
cannot choose `fr`. The integrations pin the `fr` they resolved in
`FR_HARNESS_FR` (an env var survives `.zshenv`), and `fr` compares itself to the
pin at CLI entry: a PATH-reached `fr` that disagrees refuses, one run from a
project venv (`uv run fr` — a deliberate choice) warns and continues.
"""

from __future__ import annotations

import sys
from pathlib import Path

import fr
import pytest
from typer.testing import CliRunner

from fr import __version__
from fr.binary_identity import (
    PIN_ENV,
    SKIP_ENV,
    current_identity,
    judge,
    runs_from_venv,
)
from fr.cli import app

OTHER = "0.0.1 /elsewhere/site-packages/fr"


def test_the_identity_names_the_version_and_the_package_directory() -> None:
    assert current_identity() == f"{__version__} {Path(fr.__file__).resolve().parent}"


def test_no_pin_is_no_opinion() -> None:
    assert judge({}, identity=OTHER, from_venv=False).action == "ok"


def test_a_pin_naming_this_fr_passes() -> None:
    assert judge({PIN_ENV: OTHER}, identity=OTHER, from_venv=False).action == "ok"


def test_a_path_reached_fr_that_disagrees_with_the_pin_refuses() -> None:
    verdict = judge({PIN_ENV: OTHER}, identity=current_identity(), from_venv=False)
    assert verdict.action == "refuse"
    # Names both binaries, so the reader can tell which one ran.
    assert OTHER in verdict.message
    assert current_identity() in verdict.message
    assert SKIP_ENV in verdict.message


def test_a_venv_fr_that_disagrees_with_the_pin_warns_and_continues() -> None:
    verdict = judge({PIN_ENV: OTHER}, identity=current_identity(), from_venv=True)
    assert verdict.action == "warn"
    assert OTHER in verdict.message


def test_the_skip_escape_silences_a_disagreement() -> None:
    env = {PIN_ENV: OTHER, SKIP_ENV: "1"}
    assert judge(env, identity=current_identity(), from_venv=False).action == "ok"


def test_an_empty_pin_is_no_pin() -> None:
    assert judge({PIN_ENV: ""}, identity=current_identity(), from_venv=False).action == "ok"


def test_uv_run_is_a_venv_and_a_uv_tool_is_not(tmp_path: Path) -> None:
    venv = tmp_path / ".venv"
    venv.mkdir()
    assert runs_from_venv({"VIRTUAL_ENV": str(venv)}, prefix=str(venv))
    # A uv tool's shim sets no VIRTUAL_ENV; another venv activated in the shell
    # is not the one this fr runs from.
    assert not runs_from_venv({}, prefix=str(venv))
    assert not runs_from_venv({"VIRTUAL_ENV": str(tmp_path / "other")}, prefix=str(venv))


def test_fr_identity_prints_the_identity() -> None:
    result = CliRunner().invoke(app, ["--identity"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == current_identity()


def test_fr_identity_is_answered_even_under_a_disagreeing_pin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(PIN_ENV, OTHER)
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    result = CliRunner().invoke(app, ["--identity"])
    assert result.exit_code == 0, result.output


def test_the_cli_refuses_a_path_reached_fr_under_a_disagreeing_pin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(PIN_ENV, OTHER)
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    result = CliRunner().invoke(app, ["skills"])
    assert result.exit_code == 2
    assert OTHER in result.output


def test_the_cli_warns_and_runs_a_venv_fr_under_a_disagreeing_pin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(PIN_ENV, OTHER)
    monkeypatch.setenv("VIRTUAL_ENV", sys.prefix)
    result = CliRunner().invoke(app, ["skills"])
    assert result.exit_code == 0, result.output
    assert OTHER in result.output


def test_the_cli_is_silent_under_a_pin_naming_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PIN_ENV, current_identity())
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    result = CliRunner().invoke(app, ["skills"])
    assert result.exit_code == 0, result.output
    assert PIN_ENV not in result.output
