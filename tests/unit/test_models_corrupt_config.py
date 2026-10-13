"""A corrupt models.yaml is reported, never a traceback (spec
2026-10-11-fr-small-fixes §C, R4-R6)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from fr.models import ModelsError, load_models
from fr.record.model import RECORD_SCHEMA_VERSION

from tests.unit.test_run_cli import _invoke_as_harness, _repo, _squash, _write_shape

RUN = "r1"
_SHAPE = (
    "workflow: chain\nschema: 1\nunit: run\nsteps:\n"
    "  - id: a\n    kind: agent\n  - id: b\n    kind: agent\n"
)


def test_load_models_names_the_file_for_invalid_yaml(tmp_path: Path) -> None:
    p = tmp_path / "models.yaml"
    p.write_text("claude-code: [unclosed")
    with pytest.raises(ModelsError) as ei:
        load_models(p)
    assert str(ei.value).startswith(str(p))
    assert "not valid YAML" in str(ei.value)


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("claude-code: [unclosed", "expected ',' or ']'"),
        ("claude-code:\n\tstandard: x\n", "found character '\\t'"),
        ('claude-code: "open', "found unexpected end of stream"),
    ],
)
def test_load_models_reports_the_problem_and_its_position(
    tmp_path: Path, text: str, problem: str
) -> None:
    """p1-r1: PyYAML's first line is its context ("while parsing …"), not the
    problem; the message names the problem and where it is."""
    p = tmp_path / "models.yaml"
    p.write_text(text)
    with pytest.raises(ModelsError) as ei:
        load_models(p)
    msg = str(ei.value)
    assert problem in msg
    assert "(line " in msg and ", column " in msg
    assert "while " not in msg


def test_load_models_structural_error_still_raises(tmp_path: Path) -> None:
    p = tmp_path / "models.yaml"
    p.write_text("- a\n- b\n")
    with pytest.raises(ModelsError, match="top level"):
        load_models(p)


@pytest.fixture
def corrupt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg = tmp_path / "xdg"
    (cfg / "fr").mkdir(parents=True)
    path = cfg / "fr" / "models.yaml"
    path.write_text("claude-code: [unclosed")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    return path


def _env(**extra: str | None) -> dict[str, str | None]:
    return {"FR_HARNESS": "claude-code", **extra}


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "chain", _SHAPE)
    return repo, shipped


def _start(repo: Path, shipped: Path, env: dict[str, str | None]):
    return _invoke_as_harness(
        repo, shipped, ["run", "start", "chain", "--branch", "feat/x", "--run-id", RUN], env
    )


def test_run_start_warns_and_still_starts(tmp_path: Path, corrupt: Path) -> None:
    repo, shipped = _setup(tmp_path)
    out = _start(repo, shipped, _env())
    assert out.exit_code == 0, out.output
    flat = _squash(out.output)
    assert "Traceback" not in flat
    assert flat.count("warning:") == 1
    assert str(corrupt) in flat
    assert list((repo / "docs" / "superpowers" / "runs").glob(f"{RUN}.yaml"))


def test_run_advance_exits_2_with_the_message(tmp_path: Path, corrupt: Path) -> None:
    repo, shipped = _setup(tmp_path)
    assert _start(repo, shipped, _env(FR_HARNESS=None)).exit_code == 0
    out = _invoke_as_harness(repo, shipped, ["run", "advance", RUN], _env())
    assert out.exit_code == 2, out.output
    flat = _squash(out.output)
    assert f"fr: {corrupt}: not valid YAML" in flat
    assert "Traceback" not in flat


@pytest.mark.parametrize(
    "argv",
    [
        ["models", "resolve", "--harness", "claude-code", "--tier", "standard"],
        ["models", "check"],
        ["models", "get"],
        ["models", "set", "--harness", "claude-code", "--tier", "standard", "--model", "m"],
        ["models", "apply", "--harness", "opencode"],
    ],
)
def test_models_commands_exit_2_with_the_message(
    tmp_path: Path, corrupt: Path, argv: list[str]
) -> None:
    repo, shipped = _setup(tmp_path)
    out = _invoke_as_harness(repo, shipped, argv, _env())
    assert out.exit_code == 2, out.output
    flat = _squash(out.output)
    assert f"fr: {corrupt}: not valid YAML" in flat
    assert "Traceback" not in flat


def test_run_advance_redispatch_exits_2_with_the_message(tmp_path: Path, corrupt: Path) -> None:
    repo, shipped = _setup(tmp_path)
    assert _start(repo, shipped, _env(FR_HARNESS=None)).exit_code == 0
    assert (
        _invoke_as_harness(repo, shipped, ["run", "advance", RUN], _env(FR_HARNESS=None)).exit_code
        == 0
    )
    out = _invoke_as_harness(repo, shipped, ["run", "advance", RUN, "--redispatch"], _env())
    assert out.exit_code == 2, out.output
    flat = _squash(out.output)
    assert f"fr: {corrupt}: not valid YAML" in flat
    assert "Traceback" not in flat


def test_run_start_on_opencode_warns_once_and_still_starts(tmp_path: Path, corrupt: Path) -> None:
    """The OpenCode start path also reads the config for binding health."""
    repo, shipped = _setup(tmp_path)
    out = _start(repo, shipped, _env(FR_HARNESS="opencode"))
    assert out.exit_code == 0, out.output
    flat = _squash(out.output)
    assert "Traceback" not in flat
    assert flat.count("warning:") == 1
    assert str(corrupt) in flat


def test_record_resolve_applies_then_reports_the_refused_advance(
    tmp_path: Path, corrupt: Path
) -> None:
    repo, shipped = _setup(tmp_path)
    assert _start(repo, shipped, _env(FR_HARNESS=None)).exit_code == 0
    assert (
        _invoke_as_harness(repo, shipped, ["run", "advance", RUN], _env(FR_HARNESS=None)).exit_code
        == 0
    )
    path = repo / "docs" / "superpowers" / "runs" / f"{RUN}.records" / "a.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {"schema_version": RECORD_SCHEMA_VERSION, "run": RUN, "step": "a", "outcome": "done"},
            sort_keys=False,
        )
    )
    for args in (["add", "-A"], ["commit", "-qm", "record", "--no-verify"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    out = _invoke_as_harness(
        repo, shipped, ["run", "resolve", RUN, "--step", "a", "--record", str(path)], _env()
    )

    assert out.exit_code == 2, out.output
    flat = _squash(out.output)
    assert "Traceback" not in flat
    assert f"record applied; the advance after it was refused: fr: {corrupt}" in flat
    assert not path.exists()
    from fr.run.model import load_run_state

    assert load_run_state(repo, RUN).steps["a"].state == "done"


def test_no_harness_reads_no_models_file(tmp_path: Path, corrupt: Path) -> None:
    repo, shipped = _setup(tmp_path)
    out = _start(repo, shipped, _env(FR_HARNESS=None))
    assert out.exit_code == 0, out.output
    assert "warning:" not in _squash(out.output)
    adv = _invoke_as_harness(repo, shipped, ["run", "advance", RUN], _env(FR_HARNESS=None))
    assert adv.exit_code == 0, adv.output


_CLI_NEXT = (
    "workflow: chain\nschema: 1\nunit: run\nsteps:\n"
    "  - id: a\n    kind: agent\n  - id: c\n    kind: cli\n    run: echo hi\n"
    "  - id: b\n    kind: agent\n"
)


def test_record_resolve_with_a_cli_step_next_reports_the_refused_advance(
    tmp_path: Path, corrupt: Path
) -> None:
    """The advance a record's resolve chains (here into a `kind: cli` step) is
    refused as one line, after the record is applied."""
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "chain", _CLI_NEXT)
    assert _start(repo, shipped, _env(FR_HARNESS=None)).exit_code == 0
    assert (
        _invoke_as_harness(repo, shipped, ["run", "advance", RUN], _env(FR_HARNESS=None)).exit_code
        == 0
    )
    path = repo / "docs" / "superpowers" / "runs" / f"{RUN}.records" / "a.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {"schema_version": RECORD_SCHEMA_VERSION, "run": RUN, "step": "a", "outcome": "done"},
            sort_keys=False,
        )
    )
    for args in (["add", "-A"], ["commit", "-qm", "record", "--no-verify"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    out = _invoke_as_harness(
        repo, shipped, ["run", "resolve", RUN, "--step", "a", "--record", str(path)], _env()
    )

    assert out.exit_code == 2, out.output
    flat = _squash(out.output)
    assert "Traceback" not in flat
    assert f"record applied; the advance after it was refused: fr: {corrupt}" in flat
    from fr.run.model import load_run_state

    state = load_run_state(repo, RUN)
    assert state.steps["a"].state == "done"
    assert state.steps["c"].state == "pending"
