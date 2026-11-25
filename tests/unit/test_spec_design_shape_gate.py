"""The spec gate (spec 2026-11-24-show-me-visuals R7, R8): `brainstorm` and every
spec-reviewing step (`spec-review` on fr-goal, `spec-plan-review` on fr-goal-light)
refuse, exit 2 and before anything is written, a spec with no valid `## Design shape`,
naming the spec and the two valid forms."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.record.model import RECORD_SCHEMA_VERSION
from fr.run.model import load_run_state
from fr.shape import TWO_FORMS

from tests.unit.record_support import RUN, commit_all, fr, head, snapshot, write_record

pytestmark = pytest.mark.own_artifacts

SPEC_REL = "docs/spec.md"
NO_SECTION = "# spec\n\n## Requirements\n\nR1. The widget is built.\n"
PROSE_SECTION = NO_SECTION + "\n## Design shape\n\nWe add a widget to the module.\n"
FENCED_SECTION = NO_SECTION + "\n## Design shape\n\n```diff\n fr/\n+  widget.py\n```\n"
NONE_SECTION = NO_SECTION + "\n## Design shape\n\nnone — nothing moves between modules\n"


def _flat(text: str) -> str:
    return " ".join(text.split())


def _at_brainstorm(tmp_path: Path, spec_text: str, shape: str = "fr-goal") -> Path:
    from tests.integration.test_fr_goal_shape import _workspace
    from tests.unit.requirements_support import seed_requirements

    root = _workspace(tmp_path, "feat/x")
    (root / "docs").mkdir(parents=True, exist_ok=True)
    seed_requirements(root, SPEC_REL)  # the matrix row; the spec text is ours
    (root / SPEC_REL).write_text(spec_text)
    commit_all(root, "spec")
    for argv in (
        ["run", "start", shape, "--branch", "feat/x", "--run-id", RUN],
        ["run", "advance", RUN],
    ):
        assert fr(root, argv).exit_code == 0, argv
    commit_all(root, "at brainstorm")
    return root


def _brainstorm_record(root: Path, outcome: str = "done") -> Path:
    path = write_record(
        root,
        {
            "schema_version": RECORD_SCHEMA_VERSION,
            "run": RUN,
            "step": "brainstorm",
            "outcome": outcome,
            "emitted": {"spec": SPEC_REL},
            "evidence": {"answered_by": "agent"},
        },
    )
    commit_all(root, "brainstorm record")
    return path


def _resolve(root: Path, record: Path, step: str = "brainstorm"):
    argv = ["run", "resolve", RUN, "--step", step, "--record", str(record), "--no-advance"]
    return fr(root, argv)


def _assert_refused_unchanged(root: Path, record: Path, step: str = "brainstorm") -> str:
    sha, files = head(root), snapshot(root)
    out = _resolve(root, record, step)
    assert out.exit_code == 2, out.output
    flat = _flat(out.output)
    assert SPEC_REL in flat and _flat(TWO_FORMS) in flat, out.output
    assert "## Design shape" in flat
    assert (head(root), snapshot(root)) == (sha, files)
    return flat


@pytest.mark.parametrize(
    ("spec_text", "named"),
    [(NO_SECTION, "missing"), (PROSE_SECTION, "no fenced code block")],
    ids=["no-section", "prose-only"],
)
def test_brainstorm_refuses_a_spec_without_a_valid_design_shape(
    tmp_path: Path, spec_text: str, named: str
) -> None:
    root = _at_brainstorm(tmp_path, spec_text)
    flat = _assert_refused_unchanged(root, _brainstorm_record(root))
    assert named in flat
    assert load_run_state(root, RUN).steps["brainstorm"].state != "done"


@pytest.mark.parametrize("spec_text", [FENCED_SECTION, NONE_SECTION], ids=["fenced", "none"])
def test_brainstorm_accepts_a_valid_design_shape(tmp_path: Path, spec_text: str) -> None:
    root = _at_brainstorm(tmp_path, spec_text)
    out = _resolve(root, _brainstorm_record(root))
    assert out.exit_code == 0, out.output
    assert load_run_state(root, RUN).steps["brainstorm"].state == "done"


def test_a_failed_brainstorm_record_is_not_checked(tmp_path: Path) -> None:
    root = _at_brainstorm(tmp_path, NO_SECTION)
    out = _resolve(root, _brainstorm_record(root, outcome="failed"))
    assert "## Design shape" not in out.output, out.output
    assert load_run_state(root, RUN).steps["brainstorm"].state == "failed"


def test_spec_review_refuses_a_spec_that_lost_its_design_shape(tmp_path: Path) -> None:
    from tests.unit.test_record_apply import _at_spec_review, _spec_review_record

    root = _at_spec_review(tmp_path)
    (root / SPEC_REL).write_text(NO_SECTION)
    commit_all(root, "the section went missing")
    record = write_record(root, _spec_review_record())
    commit_all(root, "spec-review record")
    _assert_refused_unchanged(root, record, step="spec-review")
    assert load_run_state(root, RUN).steps["spec-review"].state == "running"


def test_spec_plan_review_on_the_light_shape_refuses_the_same_way(tmp_path: Path) -> None:
    from tests.unit.spec_review_support import spec_review_evidence
    from tests.unit.test_run_light_shape import _at_spec_plan_review

    root = _at_spec_plan_review(tmp_path)
    evidence = spec_review_evidence(root, SPEC_REL)
    (root / SPEC_REL).write_text(PROSE_SECTION)
    commit_all(root, "the section became prose")
    sha, files = head(root), snapshot(root)
    out = fr(root, ["run", "resolve", RUN, "--step", "spec-plan-review", "--state", "done",
                    *evidence])  # fmt: skip
    assert out.exit_code == 2, out.output
    flat = _flat(out.output)
    assert "spec-plan-review" in flat and SPEC_REL in flat and _flat(TWO_FORMS) in flat
    assert (head(root), snapshot(root)) == (sha, files)
    assert load_run_state(root, RUN).steps["spec-plan-review"].state == "running"
