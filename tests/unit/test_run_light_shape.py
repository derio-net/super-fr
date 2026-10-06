"""The `fr-goal-light` shape (spec 2026-09-29-fr-goal-light-path §A, R1-R3).

* R1 — a second shipped shape, reached by `fr run start fr-goal-light` or by
  the brainstorm record declaring `shape: fr-goal-light`, which rebinds the
  run: only while the run's first step is being resolved, only onto a shape
  that begins with that same step. Same-shape is a no-op.
* R2 — on the light shape the `plan` step refuses a plan with more than one
  agentic phase (derived `single-phase`); `[manual]` phases are allowed.
* R3 — one dispatched `fr-spec-reviewer` reviews spec and plan together, held
  to `spec-review`'s evidence gate.

Every walk runs the REAL shipped manifests in a real linked worktree.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fr.journal.model import JournalEntry, append_journal_entry, journal_path
from fr.record.model import RECORD_SCHEMA_VERSION
from fr.run import units
from fr.run.model import load_run_state
from fr.version_floor import CEILING_VERSION
from fr.workflow.check import check_workflow
from fr.workflow.resolve import resolve_workflow

from tests.unit.record_support import RUN, commit_all, fr, head, snapshot, write_record
from tests.unit.requirements_support import seed_requirements
from tests.unit.spec_review_support import spec_review_evidence

SPEC_REL = "docs/spec.md"
BRANCH = "feat/light"
LIGHT_IDS = [
    "brainstorm",
    "plan",
    "spec-plan-review",
    "plan-review",
    "implement",
    "journal-check",
    "deliver",
]
REPO_ROOT = Path(__file__).resolve().parents[2]


# --- the manifest --------------------------------------------------------------


def test_the_light_shape_resolves_from_the_shipped_dirs_and_checks_clean() -> None:
    manifest = resolve_workflow("fr-goal-light", REPO_ROOT)

    assert manifest.workflow == "fr-goal-light"
    assert check_workflow(manifest, None) == []
    assert [s.id for s in manifest.steps] == LIGHT_IDS
    (implement,) = [s for s in manifest.steps if s.id == "implement"]
    assert [m.id for m in implement.steps] == ["implement-phase", "review-phase"]


def test_spec_plan_review_is_one_hard_reviewer_dispatch_over_spec_and_plan() -> None:
    manifest = resolve_workflow("fr-goal-light", REPO_ROOT)
    (step,) = [s for s in manifest.steps if s.id == "spec-plan-review"]

    assert step.kind == "agent"
    assert step.agent == "super-fr:fr-spec-reviewer"
    assert step.tier == "hard"
    assert list(step.needs) == ["spec", "plan"]
    assert list(step.emits) == ["journal:spec", "acceptance"]
    # R3: the same evidence gate as fr-goal's `spec-review`, whatever that gate
    # becomes — and, since the spec is the contract (2026-09-29), no input gate.
    (full,) = [s for s in resolve_workflow("fr-goal", REPO_ROOT).steps if s.id == "spec-review"]
    assert list(step.evidence) == list(full.evidence) == ["review", "reviewer", "findings"]


def test_the_light_plan_step_declares_single_phase() -> None:
    manifest = resolve_workflow("fr-goal-light", REPO_ROOT)
    (step,) = [s for s in manifest.steps if s.id == "plan"]

    assert list(step.evidence) == ["single-phase"]


def test_the_wheel_copy_is_byte_identical() -> None:
    canonical = REPO_ROOT / "plugins" / "super-fr" / "workflows" / "fr-goal-light.yaml"
    wheel = REPO_ROOT / "packages" / "fr" / "src" / "fr" / "workflows" / "fr-goal-light.yaml"
    assert wheel.read_bytes() == canonical.read_bytes()


# --- walks -----------------------------------------------------------------------


def _root(tmp_path: Path) -> Path:
    from tests.integration.test_fr_goal_shape import _workspace

    root = _workspace(tmp_path, BRANCH)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / SPEC_REL).write_text("# spec\n")
    seed_requirements(root, SPEC_REL)
    commit_all(root, "spec")
    return root


def _ok(root: Path, argv: list[str]):
    out = fr(root, argv)
    assert out.exit_code == 0, (argv, out.output)
    return out


def _at_brainstorm(tmp_path: Path, shape: str = "fr-goal") -> Path:
    root = _root(tmp_path)
    _ok(root, ["run", "start", shape, "--branch", BRANCH, "--run-id", RUN])
    _ok(root, ["run", "advance", RUN])  # brainstorm: blocked on its operator gate
    commit_all(root, "at brainstorm")
    return root


def _brainstorm_record(root: Path, **overrides: object) -> Path:
    data: dict[str, object] = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "run": RUN,
        "step": "brainstorm",
        "outcome": "done",
        "emitted": {"spec": SPEC_REL},
        "evidence": {"answered_by": "agent"},
    }
    data.update(overrides)
    path = write_record(root, data)
    commit_all(root, "brainstorm record")
    return path


def _resolve_record(root: Path, record: Path, step: str = "brainstorm"):
    return fr(
        root, ["run", "resolve", RUN, "--step", step, "--record", str(record), "--no-advance"]
    )


def test_a_brainstorm_record_declaring_the_light_shape_rebinds_the_run(tmp_path: Path) -> None:
    root = _at_brainstorm(tmp_path)
    record = _brainstorm_record(root, shape="fr-goal-light")

    out = _resolve_record(root, record)

    assert out.exit_code == 0, out.output
    state = load_run_state(root, RUN)
    assert state.workflow == "fr-goal-light@1"
    assert list(state.steps) == LIGHT_IDS
    assert state.cursor == "plan"
    assert state.steps["brainstorm"].state == "done"
    assert state.steps["brainstorm"].emitted == {"spec": SPEC_REL}
    assert all(state.steps[s].state == "pending" for s in LIGHT_IDS[1:])
    assert state.steps["implement"].members == ["implement-phase", "review-phase"]
    # The rebound run advances against its new shape without drift.
    advanced = _ok(root, ["run", "advance", RUN])
    assert '"plan"' in advanced.output or "plan" in advanced.output
    assert load_run_state(root, RUN).steps["plan"].state == "running"


def test_the_rebind_rides_the_brainstorm_records_one_commit(tmp_path: Path) -> None:
    root = _at_brainstorm(tmp_path)
    record = _brainstorm_record(root, shape="fr-goal-light")
    before = head(root)

    assert _resolve_record(root, record).exit_code == 0

    from tests.unit.record_support import git

    assert git(root, "rev-list", "--count", f"{before}..HEAD").strip() == "1"


def test_a_same_shape_declaration_is_a_no_op(tmp_path: Path) -> None:
    root = _at_brainstorm(tmp_path)
    record = _brainstorm_record(root, shape="fr-goal")

    out = _resolve_record(root, record)

    assert out.exit_code == 0, out.output
    state = load_run_state(root, RUN)
    assert state.workflow == "fr-goal@1"
    assert state.cursor == "spec-review"


def _refused_unchanged(root: Path, record: Path, match: str, step: str = "brainstorm") -> None:
    sha, files = head(root), snapshot(root)
    out = _resolve_record(root, record, step)
    assert out.exit_code == 2, out.output
    assert match in " ".join(out.output.split()), out.output
    assert (head(root), snapshot(root)) == (sha, files)


def test_an_unknown_shape_is_refused(tmp_path: Path) -> None:
    root = _at_brainstorm(tmp_path)
    record = _brainstorm_record(root, shape="no-such-shape")

    _refused_unchanged(root, record, "no-such-shape")


def test_a_shape_beginning_with_another_step_is_refused(tmp_path: Path) -> None:
    root = _at_brainstorm(tmp_path)
    override = root / "docs" / "superpowers" / "workflows" / "other.yaml"
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_text(
        "workflow: other\nschema: 1\ndescription: x\nunit: run\n"
        "steps:\n  - id: design\n    kind: agent\n    emits: [spec]\n"
        "  - id: brainstorm\n    kind: agent\n"
    )
    commit_all(root, "override shape")
    record = _brainstorm_record(root, shape="other")

    _refused_unchanged(root, record, "begins with 'design'")


def test_a_rebind_after_the_first_step_is_refused(tmp_path: Path) -> None:
    root = _at_brainstorm(tmp_path)
    _ok(
        root,
        ["run", "resolve", RUN, "--step", "brainstorm", "--state", "done", "--answered-by", "agent",
         "--emitted", f"spec={SPEC_REL}"],
    )  # fmt: skip
    _ok(root, ["run", "advance", RUN])  # spec-review: running
    ev = spec_review_evidence(root, SPEC_REL)
    record = write_record(
        root,
        {
            "schema_version": RECORD_SCHEMA_VERSION,
            "run": RUN,
            "step": "spec-review",
            "outcome": "done",
            "shape": "fr-goal-light",
            "evidence": {"review": ev[1].split("=", 1)[1], "reviewer": ev[3].split("=", 1)[1]},
        },
    )
    commit_all(root, "record")

    _refused_unchanged(root, record, "only the run's first step", step="spec-review")


def test_the_rebind_helper_refuses_when_another_step_left_pending(tmp_path: Path) -> None:
    from fr.commands.run_cmd import _rebind_shape, _resolve_manifest_for_state
    from fr.run.model import RunStateError

    root = _at_brainstorm(tmp_path)
    state = load_run_state(root, RUN)
    manifest = _resolve_manifest_for_state(root, state)
    steps = dict(state.steps)
    steps["plan"] = steps["plan"].model_copy(update={"state": "running"})
    moved = state.model_copy(update={"steps": steps})

    with pytest.raises(RunStateError, match="plan"):
        _rebind_shape(moved, manifest, "brainstorm", "fr-goal-light", root)


# --- single-phase (R2) -----------------------------------------------------------


def _plan(root: Path, slug: str, tags: list[str]) -> str:
    from fr.plan_ops import PhaseSpec, create

    create(
        repo_root=root,
        slug=slug,
        spec=SPEC_REL,
        target_repo="derio-net/super-fr",
        fr_version=f">=3.0.0,<{CEILING_VERSION}",
        phases=[
            PhaseSpec(
                number=n,
                title=f"Phase {n}",
                tag=tag,  # type: ignore[arg-type]
                tasks=(
                    {
                        "number": 1,
                        "title": "t1",
                        "steps": [{"id": f"P{n}.T1.S1", "text": "do it"}],
                    },
                ),
            )
            for n, tag in enumerate(tags, start=1)
        ],
        prose="# p\n",
    )
    commit_all(root, "plan")
    return f"docs/superpowers/plans/{slug}"


def _at_light_plan(tmp_path: Path) -> Path:
    root = _at_brainstorm(tmp_path, shape="fr-goal-light")
    _ok(
        root,
        ["run", "resolve", RUN, "--step", "brainstorm", "--state", "done", "--answered-by", "agent",
         "--emitted", f"spec={SPEC_REL}"],
    )  # fmt: skip
    _ok(root, ["run", "advance", RUN])  # plan: running
    commit_all(root, "at plan")
    return root


def _resolve_plan(root: Path, plan_rel: str):
    return fr(
        root,
        ["run", "resolve", RUN, "--step", "plan", "--state", "done",
         "--emitted", f"plan={plan_rel}"],
    )  # fmt: skip


def test_two_agentic_phases_are_refused_on_the_light_plan_step(tmp_path: Path) -> None:
    root = _at_light_plan(tmp_path)
    plan_rel = _plan(root, "2026-09-29-two", ["agentic", "agentic"])

    out = _resolve_plan(root, plan_rel)

    assert out.exit_code == 2, out.output
    text = " ".join(out.output.split())
    assert "single-phase" in text
    assert "this plan has 2 (1, 2)" in text
    assert "start a new run on fr-goal" in text
    assert load_run_state(root, RUN).cursor == "plan"


def test_one_agentic_and_one_manual_phase_pass(tmp_path: Path) -> None:
    root = _at_light_plan(tmp_path)
    plan_rel = _plan(root, "2026-09-29-one", ["agentic", "manual"])

    out = _resolve_plan(root, plan_rel)

    assert out.exit_code == 0, out.output
    state = load_run_state(root, RUN)
    assert state.cursor == "spec-plan-review"
    assert units.evidence_of(state.steps["plan"], "step/plan") == {"single-phase": "phase 1"}


def test_single_phase_is_derived_never_passed(tmp_path: Path) -> None:
    root = _at_light_plan(tmp_path)
    plan_rel = _plan(root, "2026-09-29-one", ["agentic"])

    out = fr(
        root,
        ["run", "resolve", RUN, "--step", "plan", "--state", "done",
         "--emitted", f"plan={plan_rel}", "--evidence", "single-phase=yes"],
    )  # fmt: skip

    assert out.exit_code == 2, out.output


# --- spec-plan-review (R3) ---------------------------------------------------------


def _at_spec_plan_review(tmp_path: Path) -> Path:
    root = _at_light_plan(tmp_path)
    plan_rel = _plan(root, "2026-09-29-one", ["agentic"])
    _ok(root, ["run", "resolve", RUN, "--step", "plan", "--state", "done",
               "--emitted", f"plan={plan_rel}"])  # fmt: skip
    _ok(root, ["run", "advance", RUN])  # spec-plan-review: running
    assert load_run_state(root, RUN).steps["spec-plan-review"].state == "running"
    return root


_DONE = ["run", "resolve", RUN, "--step", "spec-plan-review", "--state", "done"]


def test_spec_plan_review_is_refused_without_review_evidence(tmp_path: Path) -> None:
    root = _at_spec_plan_review(tmp_path)

    out = fr(root, _DONE)

    assert out.exit_code == 2, out.output
    assert "review" in out.output and "reviewer" in out.output


def test_spec_plan_review_is_refused_while_a_plan_finding_is_open(tmp_path: Path) -> None:
    root = _at_spec_plan_review(tmp_path)
    evidence = spec_review_evidence(root, SPEC_REL)
    append_journal_entry(
        journal_path(root, "spec", "spec"),
        "spec",
        JournalEntry(
            kind="finding",
            scope="spec",
            id="pf-1",
            created=datetime.now().replace(microsecond=0).isoformat(),
            title="the phase has no RED step",
            body="target: plan",
            state="open",
            review_scope="in",
        ),
    )

    out = fr(root, [*_DONE, *evidence])

    assert out.exit_code == 2, out.output
    assert "pf-1" in out.output


def test_spec_plan_review_resolves_with_the_spec_review_evidence(tmp_path: Path) -> None:
    root = _at_spec_plan_review(tmp_path)

    out = fr(root, [*_DONE, *spec_review_evidence(root, SPEC_REL)])

    assert out.exit_code == 0, out.output
    assert load_run_state(root, RUN).cursor == "plan-review"


def test_an_invalid_repo_override_of_the_target_shape_is_refused(tmp_path: Path) -> None:
    root = _at_brainstorm(tmp_path)
    override = root / "docs" / "superpowers" / "workflows" / "fr-goal-light.yaml"
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_text(
        "workflow: fr-goal-light\nschema: 1\ndescription: x\nunit: run\n"
        "steps:\n  - id: brainstorm\n    kind: agent\n    emits: [spec]\n"
        "  - id: broken\n    kind: cli\n    needs: [nowhere]\n"
    )
    commit_all(root, "invalid override")
    record = _brainstorm_record(root, shape="fr-goal-light")

    _refused_unchanged(root, record, "not a valid workflow")


def test_a_failed_brainstorm_declaring_the_light_shape_does_not_rebind(tmp_path: Path) -> None:
    root = _at_brainstorm(tmp_path)
    record = _brainstorm_record(root, outcome="failed", shape="fr-goal-light")

    _resolve_record(root, record)

    state = load_run_state(root, RUN)
    assert state.workflow == "fr-goal@1"
    assert list(state.steps) == [s.id for s in resolve_workflow("fr-goal", root).steps]
    assert state.cursor == "brainstorm"
