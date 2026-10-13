"""Review fixes of exit-gates phase 1 (p1-r1..p1-r7)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fr.commands.run_cmd import _unrunnable_spec_warnings
from fr.parser import parse as parse_plan
from fr.plan_ops import self_review
from fr.verification.exit import exit_for_spec
from fr.verification.rows import load_remap
from typer.testing import CliRunner

from tests.unit.requirements_support import row, write_matrix
from tests.unit.test_plan_acceptance_links import _create_plan, _repo
from tests.unit.test_plan_self_review_verification import SPEC_REL, _row, _setup

SPEC = "docs/spec.md"
_SC = "    scenario: s.sh\n"


def _plain(tmp_path: Path, section: str | None, rows: list[dict[str, object]]) -> Path:
    (tmp_path / "docs").mkdir(exist_ok=True)
    body = "# Spec\n\n## Requirements\n\nR1. x\n"
    if section is not None:
        body += f"\n## Verification\n\n{section}\n"
    (tmp_path / SPEC).write_text(body)
    write_matrix(tmp_path, rows)
    return tmp_path


def test_p1_r1_a_gate_line_naming_an_unknown_row_is_an_error(tmp_path: Path) -> None:
    (msg,) = _setup(
        tmp_path, "strategy: candidate\ngate: typo-row=tester\n", [_row("a", _SC), _row("b", _SC)]
    )
    assert "typo-row" in msg and "`a`" not in msg and "a, b" in msg


def test_p1_r1_a_bullet_naming_an_unknown_row_is_an_error(tmp_path: Path) -> None:
    (msg,) = _setup(tmp_path, "strategy: candidate\n- typo-row: none — why\n", [_row("a", _SC)])
    assert "typo-row" in msg and "- typo-row:" in msg


def test_p1_r3_a_gate_only_section_is_an_error(tmp_path: Path) -> None:
    (msg,) = _setup(tmp_path, "gate: tester\n", [_row("a", _SC)])
    assert "strategy: <name|none>" in msg


def test_p1_r3_a_gate_section_with_a_strategy_is_fine(tmp_path: Path) -> None:
    assert _setup(tmp_path, "strategy: candidate\ngate: tester\n", [_row("a", _SC)]) == []


def test_p1_r2_load_remap_survives_a_non_utf8_file(tmp_path: Path) -> None:
    (tmp_path / ".fr").mkdir()
    (tmp_path / ".fr" / "triage.yaml").write_bytes(b"exit: \xff\xfe\n")
    remap, problem = load_remap(tmp_path)
    assert remap == {} and problem is not None


def test_p1_r2_json_carries_remap_problem(tmp_path: Path, monkeypatch) -> None:
    from fr.cli import app

    root = _plain(tmp_path, "strategy: candidate", [])
    (root / ".fr").mkdir()
    (root / ".fr" / "triage.yaml").write_text("exit: [not, a, mapping]\n")
    monkeypatch.chdir(root)
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    res = CliRunner().invoke(app, ["verification", "exit", "--spec", SPEC, "--json"])
    data = json.loads(res.stdout)
    assert data["remap_problem"] and "triage.yaml" in data["remap_problem"]


def test_p1_r4_the_brainstorm_warning_sees_rows_on_the_shape_default(tmp_path: Path) -> None:
    root = _plain(
        tmp_path,
        "- r-other: none — elsewhere",
        [row(SPEC, rid="r-plain"), row(SPEC, rid="r-other")],
    )
    program = root / ".fr" / "candidate-install"
    program.parent.mkdir(exist_ok=True)
    program.write_text("#!/bin/sh\n")
    program.chmod(0o755)
    assert "r-plain" not in "\n".join(_unrunnable_spec_warnings(root, SPEC))
    state = SimpleNamespace(workflow="fr-goal")
    text = "\n".join(_unrunnable_spec_warnings(root, SPEC, state))  # type: ignore[arg-type]
    assert "r-plain" in text and "scenario" in text


def test_p1_r5_exit_exposes_row_kinds_and_the_run_kind(tmp_path: Path) -> None:
    root = _plain(
        tmp_path,
        "strategy: candidate\n- r-live: live — needs the release\n- r-none: none — elsewhere\n",
        [row(SPEC, rid="r-live"), row(SPEC, rid="r-none"), row(SPEC, rid="r-run")],
    )
    result = exit_for_spec(root, SPEC)
    assert result.row_kinds == {"r-live": "live", "r-none": "none", "r-run": "candidate"}
    assert result.run_kind == "candidate"


def test_p1_r5_a_run_without_strategy_has_run_kind_none(tmp_path: Path) -> None:
    root = _plain(tmp_path, None, [row(SPEC, rid="r-a")])
    result = exit_for_spec(root, SPEC)
    assert result.run_kind == "none" and result.row_kinds == {"r-a": "none"}


def _review_warnings(tmp_path: Path, triage: str) -> list[str]:
    repo = _repo(tmp_path, matrix=True)
    (repo / ".fr").mkdir(exist_ok=True)
    (repo / ".fr" / "triage.yaml").write_text(triage)
    (repo / "docs" / "acceptance" / "matrix.yaml").write_text(
        "schema_version: 4\norg: derio-net\nrepo: own\nrows:\n" + _row("a")
    )
    (repo / SPEC_REL).write_text(
        "# Toy\n\n## Requirements\n\nR1. x\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n|--|--|--|--|\n"
    )
    plan_dir = _create_plan(repo)
    return [i.message for i in self_review(parse_plan(plan_dir)) if i.severity == "warn"]


def test_p1_r7_a_remap_key_naming_no_strategy_warns(tmp_path: Path) -> None:
    msgs = _review_warnings(
        tmp_path, "exit:\n  gates:\n    no-such-kind: tester\n    live: devops\n"
    )
    assert any("no-such-kind" in m for m in msgs)
    assert not any("`live`" in m for m in msgs)


def test_p1_r7_the_key_none_warns(tmp_path: Path) -> None:
    msgs = _review_warnings(tmp_path, "exit:\n  gates:\n    none: tester\n")
    assert any("`none`" in m for m in msgs)
