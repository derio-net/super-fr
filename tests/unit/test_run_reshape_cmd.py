"""`fr run reshape` and the read-only commands on a drifted cursor
(spec 2026-10-05-run-upgrade-midflight §A, §B)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.unit.test_run_cli import (
    _GATE_SHAPE,
    _clear_cli_gate,
    _invoke,
    _repo,
    _write_shape,
)

_DRIFTED = _GATE_SHAPE + '  - id: journal-check\n    kind: cli\n    run: "true"\n'
_SCHEMA_2 = _GATE_SHAPE.replace("schema: 1", "schema: 2")


def _drifted(tmp_path: Path) -> tuple[Path, Path]:
    """A run started on `gated`, a gate cleared on it, then the shape gains a
    step AFTER the cursor — the #891 case."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _clear_cli_gate(repo, shipped, "--answered-by", "operator")
    _write_shape(shipped, "gated", _DRIFTED)
    return repo, shipped


def _run_file(repo: Path) -> Path:
    return repo / "docs" / "superpowers" / "runs" / "r1.yaml"


def _head_subject(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%s"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit_count(repo: Path) -> int:
    return int(
        subprocess.run(
            ["git", "-C", str(repo), "rev-list", "--count", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )


def test_preview_prints_the_diff_and_writes_nothing(tmp_path: Path) -> None:
    repo, shipped = _drifted(tmp_path)
    before, commits = _run_file(repo).read_bytes(), _commit_count(repo)

    result = _invoke(repo, shipped, ["run", "reshape", "r1"])

    assert result.exit_code == 0, result.output
    assert "added: journal-check" in result.output
    assert _run_file(repo).read_bytes() == before
    assert _commit_count(repo) == commits


def test_yes_rewrites_the_cursor_in_one_chore_commit(tmp_path: Path) -> None:
    repo, shipped = _drifted(tmp_path)
    commits = _commit_count(repo)

    result = _invoke(repo, shipped, ["run", "reshape", "r1", "--yes"])

    assert result.exit_code == 0, result.output
    assert "journal-check" in _run_file(repo).read_text()
    assert _commit_count(repo) == commits + 1
    assert _head_subject(repo).startswith("chore(fr):")
    # and the cursor is readable again
    assert _invoke(repo, shipped, ["run", "gates", "r1"]).exit_code == 0
    again = _invoke(repo, shipped, ["run", "reshape", "r1", "--yes"])
    assert again.exit_code == 0 and "nothing to reshape" in again.output


def test_no_drift_says_nothing_to_reshape(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _clear_cli_gate(repo, shipped, "--answered-by", "operator")

    result = _invoke(repo, shipped, ["run", "reshape", "r1"])

    assert result.exit_code == 0, result.output
    assert "nothing to reshape" in result.output


def test_a_refusal_exits_2_and_writes_nothing(tmp_path: Path) -> None:
    repo, shipped = _drifted(tmp_path)
    # `after` (the step behind the cursor) loses a sibling: remove `brainstorm`,
    # the cursor, from the shape.
    _write_shape(
        shipped,
        "gated",
        "workflow: gated\nschema: 1\nunit: run\nsteps:\n"
        '  - id: after\n    kind: cli\n    run: "true"\n',
    )
    before = _run_file(repo).read_bytes()

    result = _invoke(repo, shipped, ["run", "reshape", "r1", "--yes"])

    assert result.exit_code == 2, result.output
    assert "brainstorm" in result.output
    assert _run_file(repo).read_bytes() == before


def test_advance_on_a_drifted_cursor_names_the_reshape_command(tmp_path: Path) -> None:
    repo, shipped = _drifted(tmp_path)

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    assert "fr run reshape r1" in " ".join(result.output.split())


# --- R4: read-only commands answer a drifted cursor ----------------------------


def test_gates_answers_a_drifted_cursor_with_one_warning(tmp_path: Path) -> None:
    repo, shipped = _drifted(tmp_path)

    result = _invoke(repo, shipped, ["run", "gates", "r1"])

    out = " ".join(result.output.split())
    assert result.exit_code == 0, result.output
    assert "brainstorm: operator gate answered by the operator" in out
    assert out.count("fr run reshape") == 1
    assert "journal-check" in out


def test_status_answers_a_drifted_cursor_with_one_warning(tmp_path: Path) -> None:
    repo, shipped = _drifted(tmp_path)

    result = _invoke(repo, shipped, ["run", "status", "r1"])

    out = " ".join(result.output.split())
    assert result.exit_code == 0, result.output
    assert out.count("fr run reshape") == 1


def test_a_schema_mismatch_still_refuses_gates(tmp_path: Path) -> None:
    repo, shipped = _drifted(tmp_path)
    _write_shape(shipped, "gated", _SCHEMA_2)

    result = _invoke(repo, shipped, ["run", "gates", "r1"])

    assert result.exit_code == 2, result.output


def test_check_answers_a_drifted_cursor_with_one_warning(tmp_path: Path) -> None:
    repo, shipped = _drifted(tmp_path)
    before = _invoke(repo, shipped, ["run", "check", "r1"])

    out = " ".join(before.output.split())
    assert "was started against a different version" in out
    assert out.count("fr run reshape") == 1
    # A drift is a warning here, never the reason `check` fails.
    assert before.exit_code == 0, before.output


def test_reshape_across_a_schema_change_refuses_naming_supersede(tmp_path: Path) -> None:
    repo, shipped = _drifted(tmp_path)
    # The cursor records a schema the shape no longer declares (a shape this
    # fr cannot parse at all is a different refusal, made by the resolver).
    run_file = _run_file(repo)
    run_file.write_text(run_file.read_text().replace("gated@1", "gated@2"))
    subprocess.run(["git", "commit", "-qam", "schema drift"], cwd=repo, check=True)
    before = run_file.read_bytes()
    commits = _commit_count(repo)

    result = _invoke(repo, shipped, ["run", "reshape", "r1", "--yes"])

    assert result.exit_code == 2, result.output
    assert "--supersede" in " ".join(result.output.split())
    assert _run_file(repo).read_bytes() == before
    assert _commit_count(repo) == commits
