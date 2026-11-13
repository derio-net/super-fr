"""R7 and R8 (spec 2026-11-04-repo-feature-settings): a spec the repo's policy forbids is
refused at the steps that accept it and by `fr validate artifacts`; close-out, archive,
staleness and the exit compute nothing the setting turned off."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.settings import DISABLED, spec_policy_problems

from tests.unit.settings_repo import land_on_main, make_repo

PLAN_SPEC = "# S\n\n## Test Plan\n\n1. do it\n"
GATE_SPEC = "# S\n\n## Verification\n\nstrategy: none\ngate: tester\n"


def _spec(root: Path, text: str) -> Path:
    path = root / "docs" / "superpowers" / "specs" / "2026-11-07-x-design.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = make_repo(tmp_path)
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    return root


def test_test_plan_off_refuses_a_spec_carrying_one(repo: Path) -> None:
    land_on_main(repo, "artifacts:\n  test_plan: off\n")
    problems = spec_policy_problems(repo, _spec(repo, PLAN_SPEC))
    assert len(problems) == 1 and DISABLED in problems[0] and "test_plan" in problems[0]
    assert spec_policy_problems(repo, _spec(repo, GATE_SPEC)) == []


def test_gates_off_refuses_any_gate_line(repo: Path) -> None:
    land_on_main(repo, "artifacts:\n  gates: off\n")
    problems = spec_policy_problems(repo, _spec(repo, GATE_SPEC))
    assert len(problems) == 1 and DISABLED in problems[0] and "gates" in problems[0]
    assert spec_policy_problems(repo, _spec(repo, PLAN_SPEC)) == []


def test_the_defaults_refuse_nothing(repo: Path) -> None:
    assert spec_policy_problems(repo, _spec(repo, PLAN_SPEC + "\n" + GATE_SPEC)) == []


def test_validate_artifacts_refuses_the_spec(repo: Path) -> None:
    from fr.artifacts.structure import validate_spec

    land_on_main(repo, "artifacts:\n  test_plan: off\n")
    assert any(DISABLED in p for p in validate_spec(_spec(repo, PLAN_SPEC)))


def test_closeout_and_archive_owe_no_test_plan_outcomes(repo: Path) -> None:
    from fr.archive import missing_outcomes

    spec = _spec(repo, PLAN_SPEC)
    assert missing_outcomes(repo, spec) != []
    land_on_main(repo, "artifacts:\n  test_plan: off\n")
    assert missing_outcomes(repo, spec) == []


def test_the_staleness_guard_does_not_require_a_row_citing_the_test_plan(repo: Path) -> None:
    from fr.acceptance.check import spec_test_plan

    spec = _spec(repo, PLAN_SPEC)
    assert spec_test_plan(repo, spec) == (True, None)
    land_on_main(repo, "artifacts:\n  test_plan: off\n")
    assert spec_test_plan(repo, spec) == (False, None)


def test_gates_off_computes_no_gate_and_no_gate_label(repo: Path) -> None:
    from fr.verification.exit import exit_for_spec
    from fr.verification.labels import desired_labels

    spec = _spec(repo, GATE_SPEC)
    rel = spec.relative_to(repo).as_posix()
    assert exit_for_spec(repo, rel).run_gate == "tester"
    land_on_main(repo, "artifacts:\n  gates: off\n")
    exit_ = exit_for_spec(repo, rel)
    assert exit_.run_gate == "none" and exit_.gates == frozenset() and exit_.gated_rows == ()
    assert not [d for d in desired_labels(exit_.kinds, exit_.gates) if d.name.startswith("gate:")]


def test_resolve_refuses_the_spec_at_brainstorm_and_leaves_the_record(tmp_path: Path) -> None:
    from tests.integration.test_fr_goal_shape import _workspace
    from tests.unit.record_support import RUN, fr, git, write_record
    from tests.unit.requirements_support import seed_requirements

    root = _workspace(tmp_path, "feat/x")
    base = tmp_path / "base"
    land_on_main(base, "artifacts:\n  test_plan: off\n")
    git(root, "fetch", "-q", "origin")
    assert (
        fr(root, ["run", "start", "fr-goal", "--branch", "feat/x", "--run-id", RUN]).exit_code == 0
    )
    assert "blocked on operator gate" in fr(root, ["run", "advance", RUN]).output
    spec_rel = "docs/superpowers/specs/2026-09-25-x-design.md"
    (root / spec_rel).parent.mkdir(parents=True, exist_ok=True)
    (root / spec_rel).write_text(PLAN_SPEC)
    seed_requirements(root, spec_rel)
    (root / spec_rel).write_text((root / spec_rel).read_text() + "\n## Test Plan\n\n1. x\n")
    rec = write_record(
        root, {"run": RUN, "step": "brainstorm", "outcome": "done", "emitted": {"spec": spec_rel}}
    )
    before = rec.read_bytes()
    out = fr(root, ["run", "resolve", RUN, "--step", "brainstorm", "--record", str(rec)])
    assert out.exit_code == 2, out.output
    assert DISABLED in out.output and "test_plan" in out.output
    assert rec.read_bytes() == before


def test_one_wording_for_a_disabled_feature() -> None:
    """No surface spells "disabled by repo setting" differently (R6): the Python ones read
    `fr.settings.DISABLED`; the one shell hook that cannot import it must match it."""
    import re

    root = Path(__file__).resolve().parents[2]
    variants = re.compile(
        r"disabled (?:by|in|via) (?:the )?(?:repo(?:sitory)?|project)'?s? settings?", re.I
    )
    for base in (root / "packages" / "fr" / "src", root / "plugins" / "super-fr" / "hooks"):
        for path in base.rglob("*"):
            if path.suffix not in {".py", ".sh"}:
                continue
            for hit in variants.findall(path.read_text()):
                assert hit == DISABLED, (path, hit)
    hook = (root / "plugins" / "super-fr" / "hooks" / "fr-acceptance-nag.sh").read_text()
    assert DISABLED in hook


def test_every_problem_is_reported_at_once(repo: Path) -> None:
    """p2-r4: gates off AND acceptance off with a row-level gate line names both."""
    land_on_main(repo, "artifacts:\n  test_plan: off\n  gates: off\n  acceptance: off\n")
    text = PLAN_SPEC + "\n## Verification\n\nstrategy: none\ngate: row-a=tester\n"
    problems = spec_policy_problems(repo, _spec(repo, text))
    assert len(problems) == 3, problems
    assert ["test_plan" in problems[0], "gates" in problems[1], "acceptance" in problems[2]] == [
        True,
        True,
        True,
    ]


@pytest.mark.parametrize(
    ("setting", "section", "named"),
    [
        ("test_plan: off", "\n## Test Plan\n\n1. x\n", "test_plan"),
        ("gates: off", "\n## Verification\n\nstrategy: none\ngate: tester\n", "gates"),
        ("gates: off", "\n## Verification\n\nstrategy: none\ngate: row-a=tester\n", "gates"),
    ],
    ids=["test-plan", "run-level-gate", "row-level-gate"],
)
def test_p2_r5_resolve_refuses_the_spec_at_spec_review(
    tmp_path: Path, setting: str, section: str, named: str
) -> None:
    from tests.unit.record_support import fr, git, write_record
    from tests.unit.test_record_apply import (
        RUN,
        _at_spec_review,
        _resolve,
        _spec_review_record,
    )

    root = _at_spec_review(tmp_path)
    land_on_main(tmp_path / "base", f"artifacts:\n  {setting}\n")
    git(root, "fetch", "-q", "origin")
    spec = root / "docs" / "spec.md"
    spec.write_text(spec.read_text() + section)
    rec = write_record(root, _spec_review_record())
    before = rec.read_bytes()
    out = _resolve(root, rec, step="spec-review", item=None)
    assert out.exit_code == 2, out.output
    assert DISABLED in out.output and f"artifacts.{named}: off" in out.output
    assert rec.read_bytes() == before
    assert "spec-review" in fr(root, ["run", "status", RUN]).output
