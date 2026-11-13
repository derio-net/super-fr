"""R6 (spec 2026-11-04-repo-feature-settings): under `artifacts.acceptance: off` fr writes
no row, refuses a row-level gate, and every surface that read the matrix says the setting
is why it has nothing to say."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fr.acceptance.fold import load_effective
from fr.cli import app
from fr.settings import DISABLED
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import fragments_text, write_matrix_fragments
from tests.unit.settings_repo import git, land_on_main, make_repo

runner = CliRunner()
OFF = "artifacts:\n  acceptance: off\n"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = make_repo(tmp_path)
    land_on_main(root, OFF)
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    return root


def _refused(result: Any) -> None:
    assert result.exit_code == 2, result.output
    assert DISABLED in result.output
    assert "acceptance" in result.output


def test_add_set_status_and_init_are_refused_naming_the_setting(repo: Path) -> None:
    add = runner.invoke(
        app,
        ["acceptance", "add", "--id", "a", "--capability", "c", "--acceptance", "x",
         "--status", "not-implemented"],
    )  # fmt: skip
    _refused(add)
    _refused(
        runner.invoke(
            app, ["acceptance", "set-status", "--id", "a", "--status", "ci", "--notes", "n"]
        )
    )
    _refused(runner.invoke(app, ["acceptance", "init"]))
    assert not (repo / "docs" / "acceptance").exists()


def test_a_walk_write_is_refused_naming_the_setting(repo: Path) -> None:
    result = runner.invoke(
        app,
        ["acceptance", "set-status", "--id", "a", "--status", "walked", "--notes", "n",
         "--walk", "w.log"],
    )  # fmt: skip
    _refused(result)


def test_a_record_acceptance_section_is_refused_and_bytes_restored(tmp_path: Path) -> None:
    from fr.record.apply import RecordRefusedError, RecordTarget, apply_record

    from tests.unit.test_record_apply import _matrix_repo, _move

    root = _matrix_repo(tmp_path)
    git(root, "checkout", "-q", "main")
    land_on_main_local(root, OFF)
    git(root, "checkout", "-q", "feat/drops")
    before = fragments_text(root).encode()
    with pytest.raises(RecordRefusedError, match=DISABLED):
        apply_record(root, None, _move(), target=RecordTarget(message="m"))
    assert fragments_text(root).encode() == before


def land_on_main_local(root: Path, text: str) -> None:
    (root / ".fr").mkdir(exist_ok=True)
    (root / ".fr" / "settings.yaml").write_text(text)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "settings")


def test_a_row_level_gate_line_is_refused_but_a_run_level_one_is_valid(repo: Path) -> None:
    from fr.settings import spec_policy_problems

    spec = repo / "spec.md"
    spec.write_text("# S\n\n## Verification\n\nstrategy: none\ngate: row-a=tester\n")
    problems = spec_policy_problems(repo, spec)
    assert problems and DISABLED in problems[0] and "acceptance" in problems[0]
    spec.write_text("# S\n\n## Verification\n\nstrategy: none\ngate: tester\n")
    assert spec_policy_problems(repo, spec) == []


def test_status_says_disabled(repo: Path) -> None:
    result = runner.invoke(app, ["acceptance", "status", "--brief"])
    assert result.exit_code == 0, result.output
    assert DISABLED in result.output


def test_debt_says_disabled(repo: Path) -> None:
    result = runner.invoke(app, ["debt", "--offline"])
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[lines.index("Acceptance:") + 1] == f"  {DISABLED}", result.output


def test_pr_body_owed_sections_say_disabled(repo: Path) -> None:
    from fr.record import pr_body
    from fr.run.model import RunState, StepRecord

    state = RunState(
        run="r",
        workflow="fr-goal@1",
        branch="feat/x",
        started="2026-11-07T00:00:00+00:00",
        cursor="deliver",
        steps={"brainstorm": StepRecord(state="done", emitted={"spec": "docs/s.md"})},
    )
    want = f"no acceptance rows: {DISABLED} (artifacts.acceptance: off)."
    assert pr_body._pre_merge_owed(repo, state) == want
    assert pr_body._post_merge_owed(repo, state) == want


def test_self_review_and_proportionality_say_disabled(repo: Path) -> None:
    from fr import plan_ops, proportionality

    spec = repo / "docs" / "superpowers" / "specs" / "s.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# S\n\n## Test Plan\n\n1. x\n")
    plan: Any = SimpleNamespace(
        repo_root=repo,
        spec_path="docs/superpowers/specs/s.md",
        spec_file=spec,  # `Plan.spec_file`: the spec below the plan's artifact root
        meta=SimpleNamespace(spec=""),
        phases=[],
    )
    issues = plan_ops._acceptance_link_issues(plan)
    assert [i.severity for i in issues] == ["info"]
    assert DISABLED in issues[0].message
    lines = proportionality._phases(repo, plan, [])
    assert any(DISABLED in ln for ln in lines)


def _with_matrix(root: Path) -> None:
    (root / "docs" / "acceptance").mkdir(parents=True, exist_ok=True)
    write_matrix_fragments(root, "org: derio-net\nrepo: own\nrows: []\n")


@pytest.mark.parametrize("with_matrix", [False, True], ids=["no-matrix", "matrix"])
@pytest.mark.parametrize("command", ["check", "summary"])
def test_p2_r6_check_and_summary_say_disabled_and_exit_0(
    repo: Path, command: str, with_matrix: bool
) -> None:
    if with_matrix:
        _with_matrix(repo)
    result = runner.invoke(app, ["acceptance", command])
    assert result.exit_code == 0, result.output
    assert DISABLED in result.output
    assert "no docs/acceptance/matrix.yaml" not in result.output
    assert "debt" not in result.output.lower()


def test_p2_r6_the_staleness_guard_demands_no_rows_under_acceptance_off(repo: Path) -> None:
    """acceptance: off with test_plan: on: a Test Plan spec cited by no row is not stale."""
    from fr.acceptance.check import check

    _with_matrix(repo)
    spec = repo / "docs" / "superpowers" / "specs" / "2026-11-07-x-design.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# S\n\n## Test Plan\n\n1. x\n")
    result = check(load_effective(repo), repo)
    assert not [e for e in result.errors if e.startswith("staleness")], result.errors


def test_p2_r5_digest_says_disabled_and_report_backfill_are_refused(repo: Path) -> None:
    _with_matrix(repo)
    digest = runner.invoke(app, ["acceptance", "digest"])
    assert digest.exit_code == 0, digest.output
    assert DISABLED in digest.output
    for argv in (["acceptance", "report"], ["acceptance", "backfill"]):
        result = runner.invoke(app, argv)
        _refused(result)
    d = repo / "docs" / "acceptance"
    assert not any((d / n).exists() for n in ("report.html", "report.md"))
