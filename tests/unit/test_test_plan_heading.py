"""The `## Test Plan` heading contract (super-fr#1315).

`## Test Plan` is a keyword heading: fr reads exactly that line. A heading that
is *almost* it (`## 6. Test Plan (post-merge)`, `### Test plan`) used to read as
"no Test Plan", which every downstream gate took as "nothing owed". The one
shared matcher, `fr.spec.find_test_plan_heading`, now tells exact from near-miss,
and every reader of the section turns a near-miss into an error naming the file,
the line and the fix.
"""

from __future__ import annotations

import pytest
from fr.spec import (
    TestPlanHeadingError,
    find_test_plan_heading,
    test_plan_section,
    test_plan_steps,
)

BODY = "\n1. Run it.\n2. Watch it.\n"


def _spec(heading: str, body: str = BODY, before: str = "") -> str:
    return f"# Widget\n\n## 1. Requirements\n\nR1.\n{before}\n{heading}\n{body}\n## Plans\n"


# --- the matcher -------------------------------------------------------------


def test_the_exact_heading_is_found_and_is_not_a_near_miss() -> None:
    found = find_test_plan_heading(_spec("## Test Plan"))
    assert found is not None and found.exact
    assert found.text == "## Test Plan"


def test_trailing_whitespace_is_still_exact() -> None:
    found = find_test_plan_heading(_spec("## Test Plan   "))
    assert found is not None and found.exact


@pytest.mark.parametrize(
    "heading",
    [
        "## 6. Test Plan",
        "## 6) Test Plan",
        "## §6 Test Plan",
        "## 6.1 Test Plan",
        "## Test Plan (post-merge, operator-driven)",
        "## 5. Test Plan (post-merge, operator-driven)",
        "## Test plan",
        "## TEST PLAN",
        "### Test Plan",
        "### Test Plan (post-merge — operator-driven)",
        "# Test Plan",
    ],
)
def test_a_near_miss_is_reported_with_its_line(heading: str) -> None:
    text = _spec(heading)
    found = find_test_plan_heading(text)
    assert found is not None and not found.exact
    assert found.text == heading
    assert text.splitlines()[found.line] == heading


@pytest.mark.parametrize(
    "heading",
    [
        "## Acceptance and test plan",
        "### G. Test Plan gates (`fr/spec.py`)",
        "#### Test Plan",  # deeper than a section heading: never a candidate
        "## Test Planning",
    ],
)
def test_headings_that_only_mention_a_test_plan_are_not_near_misses(heading: str) -> None:
    assert find_test_plan_heading(_spec(heading)) is None


def test_prose_mentioning_the_test_plan_is_nothing() -> None:
    text = "# W\n\nThe test plan below.\nSee `## Test Plan` in the spec.\nTest Plan\n"
    assert find_test_plan_heading(text) is None


def test_a_heading_inside_a_code_fence_is_nothing() -> None:
    text = "# W\n\n```markdown\n## 6. Test Plan\n```\n"
    assert find_test_plan_heading(text) is None


def test_a_sub_heading_under_the_real_section_is_not_a_near_miss() -> None:
    text = _spec("## Test Plan", body="\n### Test Plan steps\n\n1. Run it.\n")
    found = find_test_plan_heading(text)
    assert found is not None and found.exact
    assert [s.text for s in test_plan_steps(text)] == ["Run it."]


def test_the_exact_heading_wins_over_an_earlier_near_miss() -> None:
    text = _spec("## Test Plan", before="\n### Test plan\n\nOld notes.\n")
    found = find_test_plan_heading(text)
    assert found is not None and found.exact


# --- the readers: a near-miss is an error, never "no Test Plan" ---------------


def test_steps_refuse_a_near_miss_naming_the_file_line_and_fix() -> None:
    text = _spec("## 6. Test Plan (post-merge)")
    line = text.splitlines().index("## 6. Test Plan (post-merge)") + 1
    with pytest.raises(TestPlanHeadingError) as err:
        test_plan_steps(text, source="docs/superpowers/specs/x-design.md")
    msg = str(err.value)
    assert f"docs/superpowers/specs/x-design.md:{line}" in msg
    assert "## 6. Test Plan (post-merge)" in msg
    assert 'rename it to "## Test Plan"' in msg


def test_section_refuses_a_near_miss_too() -> None:
    with pytest.raises(TestPlanHeadingError):
        test_plan_section(_spec("## Test plan"))


def test_the_error_is_not_a_value_error() -> None:
    """Callers degrade a `ValueError` to "nothing here" (debt's held-plan read, the
    self-review's ops check). A near-miss read as nothing is the bug itself."""
    assert not issubclass(TestPlanHeadingError, ValueError)


def test_no_heading_at_all_is_still_no_steps() -> None:
    assert test_plan_steps("# W\n\n## Requirements\n\nR1.\n") == []
    assert test_plan_section("# W\n") is None


# --- every surface that reads the heading -------------------------------------

NEAR = "## 6. Test Plan (post-merge, operator-driven)"


def _near_spec() -> str:
    return _spec(NEAR)


def test_validate_artifacts_reports_a_near_miss_in_a_live_spec(tmp_path) -> None:  # noqa: ANN001
    from fr.artifacts.structure import validate_spec

    spec = tmp_path / "s.md"
    spec.write_text(_near_spec())
    [problem] = validate_spec(spec)
    assert NEAR in problem and 'rename it to "## Test Plan"' in problem
    assert problem.startswith(f"line {_near_spec().splitlines().index(NEAR) + 1}:")
    spec.write_text(_spec("## Test Plan"))
    assert validate_spec(spec) == []


def test_validate_artifacts_never_reads_an_archived_spec() -> None:
    from fr.artifacts.registry import ARTIFACT_KINDS

    assert ARTIFACT_KINDS["spec"].locator == "docs/superpowers/specs/*.md"


def test_the_repair_renames_a_level_two_near_miss_and_keeps_its_suffix(tmp_path) -> None:  # noqa: ANN001
    from fr.artifacts.runner import MIGRATIONS
    from fr.artifacts.spec_test_plan_heading import SPEC_TEST_PLAN_HEADING_REPAIR

    assert SPEC_TEST_PLAN_HEADING_REPAIR in MIGRATIONS.repairs("spec")
    spec = tmp_path / "s.md"
    spec.write_text(_near_spec())
    assert SPEC_TEST_PLAN_HEADING_REPAIR.applies(spec)
    SPEC_TEST_PLAN_HEADING_REPAIR.fn(spec)
    text = spec.read_text()
    assert "## Test Plan\n\n_(post-merge, operator-driven)_\n" in text
    assert NEAR not in text
    assert [s.text for s in test_plan_steps(text)] == ["Run it.", "Watch it."]
    assert not SPEC_TEST_PLAN_HEADING_REPAIR.applies(spec), (
        "idempotent: applying it makes the predicate False"
    )


def test_the_repair_leaves_other_levels_for_a_human(tmp_path) -> None:  # noqa: ANN001
    from fr.artifacts.spec_test_plan_heading import SPEC_TEST_PLAN_HEADING_REPAIR

    spec = tmp_path / "s.md"
    spec.write_text(_spec("### Test Plan"))
    assert not SPEC_TEST_PLAN_HEADING_REPAIR.applies(spec)
    spec.write_text(_spec("## Test Plan"))
    assert not SPEC_TEST_PLAN_HEADING_REPAIR.applies(spec)


def test_archive_holds_a_plan_whose_spec_heading_is_a_near_miss(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    from tests.unit import test_archive_owed as ao
    from tests.unit.fakes import FakeGhClient

    repo = ao._plan_repo(tmp_path, outcomes=[], test_plan=f"\n{NEAR}\n\n1. Walk it.\n")
    result = ao._archive(monkeypatch, repo, FakeGhClient())
    assert result.exit_code == 2, result.output
    assert (repo / "docs/superpowers/plans" / ao.PLAN).is_dir(), "nothing moved"
    out = " ".join(result.output.split())
    assert f"docs/superpowers/specs/{ao.SPEC_NAME}:" in out
    assert 'rename it to "## Test Plan"' in out


def test_closeout_outcome_refuses_a_near_miss_naming_the_fix(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    from fr.cli import app
    from typer.testing import CliRunner

    from tests.unit import test_closeout_outcome as co

    root = co._repo(tmp_path, spec=_near_spec())
    monkeypatch.chdir(root)
    res = CliRunner().invoke(
        app, ["closeout", "outcome", "--run", co.RUN_ID, "--step", "1", "--owed", "--why", "x"]
    )
    assert res.exit_code == 2, res.output
    out = " ".join(res.output.split())
    assert f"{co.SPEC_REL}:" in out and 'rename it to "## Test Plan"' in out
    assert "has no `## Test Plan` section" not in out
    assert co._entries(root) == []


def test_plan_self_review_errors_on_a_near_miss(tmp_path) -> None:  # noqa: ANN001
    from tests.unit import test_plan_acceptance_links as pal

    repo = pal._repo(tmp_path, matrix=True)
    spec = pal._spec(repo)
    spec.write_text(spec.read_text().replace("## Test Plan", NEAR))
    issues = pal._issues(repo, pal._create_plan(repo))
    hits = [i for i in issues if 'rename it to "## Test Plan"' in i.message]
    assert [i.severity for i in hits] == ["error"]
    # Its rows are still owed: the link check still sees a Test Plan.
    assert any("no acceptance rows linked" in i.message for i in issues)


def test_plan_self_review_is_silent_on_the_exact_heading(tmp_path) -> None:  # noqa: ANN001
    from tests.unit import test_plan_acceptance_links as pal

    repo = pal._repo(tmp_path, matrix=True)
    pal._spec(repo)
    issues = pal._issues(repo, pal._create_plan(repo))
    assert not any("rename it to" in i.message for i in issues)


def test_the_staleness_guard_refuses_a_live_near_miss(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    from tests.unit.acceptance_helpers import make_repo, row
    from tests.unit.test_acceptance_cmd import run_check

    root = make_repo(tmp_path, row())
    (root / "docs/superpowers/specs/near.md").write_text(_near_spec())
    result = run_check(root, monkeypatch)
    assert result.exit_code == 1
    out = " ".join(result.output.split())
    assert "docs/superpowers/specs/near.md:" in out and 'rename it to "## Test Plan"' in out
    # ...and still owes it rows: a near-miss is a Test Plan, uncited.
    assert "staleness: docs/superpowers/specs/near.md has a Test Plan" in out


def test_the_staleness_guard_never_judges_an_archived_near_miss(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    from tests.unit.acceptance_helpers import make_repo, row
    from tests.unit.test_acceptance_cmd import run_check

    root = make_repo(tmp_path, row())
    archived = root / "docs/superpowers/implemented/specs"
    archived.mkdir(parents=True, exist_ok=True)
    (archived / "old.md").write_text(_near_spec())
    result = run_check(root, monkeypatch)
    assert "old.md" not in result.output, result.output


def test_debt_never_reads_a_near_miss_spec_as_zero(tmp_path) -> None:  # noqa: ANN001
    import subprocess
    from datetime import UTC, datetime

    from fr.commands.debt_cmd import _is_zero
    from fr.debt.engine import compute, spec_heading_problems

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    specs = tmp_path / "docs/superpowers/specs"
    specs.mkdir(parents=True)
    (specs / "ok.md").write_text(_spec("## Test Plan"))
    (specs / "near.md").write_text(_near_spec())
    archived = tmp_path / "docs/superpowers/implemented/specs"
    archived.mkdir(parents=True)
    (archived / "old.md").write_text(_near_spec())

    [problem] = spec_heading_problems(tmp_path)
    assert problem.startswith("docs/superpowers/specs/near.md:")
    report = compute(tmp_path, forge=None, now=datetime(2026, 11, 2, tzinfo=UTC))
    assert report.sources["specs"].state == "unavailable"
    assert "near.md" in report.sources["specs"].why
    assert not _is_zero(report)

    (specs / "near.md").write_text(_spec("## Test Plan"))
    report = compute(tmp_path, forge=None, now=datetime(2026, 11, 2, tzinfo=UTC))
    assert report.sources["specs"].state == "read"


def test_the_closeout_brief_says_to_fix_the_heading_first(tmp_path) -> None:  # noqa: ANN001
    from fr.run.closeout import RunExtras, branch_closeout_brief

    brief = branch_closeout_brief(
        tmp_path,
        "feat/widget",
        run_extras=RunExtras(
            run_id="r",
            pr=None,
            spec_path="docs/superpowers/specs/s.md",
            plan_path=None,
            has_test_plan=True,
            out_of_scope=[],
            test_plan_problem='docs/superpowers/specs/s.md:9: … rename it to "## Test Plan"',
        ),
    )
    assert "FIX FIRST" in brief and 'rename it to "## Test Plan"' in brief


def test_the_run_closeout_brief_turns_a_near_miss_into_its_fix_first_line(
    tmp_path,
    monkeypatch,  # noqa: ANN001
) -> None:
    """End to end through `closeout_brief`: the run's spec has a near-miss heading, and
    the brief says FIX FIRST naming the file — it neither drops the Test Plan nor dies."""
    from tests.unit.test_closeout_awaiting_live import _brief
    from tests.unit.test_verification_walk import SPEC, _repo

    root = _repo(tmp_path)
    spec = root / SPEC
    spec.write_text(spec.read_text() + f"\n{NEAR}\n\n1. Walk it live.\n")
    brief = _brief(root, monkeypatch, "body")
    assert f"run the spec's Test Plan: {SPEC}" in brief
    assert "FIX FIRST" in brief and f"{SPEC}:" in brief
    assert 'rename it to "## Test Plan"' in brief


def test_no_reader_outside_fr_spec_spells_the_heading() -> None:
    """One matcher: the heading's literal lives in `fr.spec` alone (super-fr#1315). Any
    quote style, a regex or an f-string, in any shipped package, counts."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "packages"
    spelled = re.compile(r"""["'^]\s*#{1,3}\s*Test Plan""")
    offenders = [
        f"{p.relative_to(root)}:{n}"
        for p in sorted(root.glob("*/src/**/*.py"))
        if p.as_posix().endswith("/fr/spec.py") is False
        for n, line in enumerate(p.read_text().splitlines(), 1)
        if spelled.search(line) and "rename it to" not in line
    ]
    assert offenders == []
