"""CI tripwire: every shipped workflow manifest must pass `check_workflow`
(spec §4.A, Phase 6) — a malformed shipped shape fails CI, not a consumer's
run.

Deliberately requires the glob to be NON-empty (Phase 6 dispatch brief:
"a tripwire that passes vacuously over an empty glob is exactly the kind of
test that reads as coverage and provides none"). Phase 6 lands a minimal,
valid `fr-goal.yaml` **stub** — schema-valid but not yet the real pipeline —
so this test is green from the moment it exists; Phase 11 fleshes the stub
out into the spec §4.A example manifest and this test starts covering that
real content for free, no test-file change needed.
"""

from __future__ import annotations

from pathlib import Path

from fr.workflow.check import check_workflow
from fr.workflow.model import WorkflowError, parse_manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_WORKFLOWS_DIR = REPO_ROOT / "plugins" / "super-fr" / "workflows"


def test_at_least_one_shipped_workflow_manifest_exists() -> None:
    manifests = sorted(SHIPPED_WORKFLOWS_DIR.glob("*.yaml"))
    assert manifests, (
        f"no manifests under {SHIPPED_WORKFLOWS_DIR} — this test intentionally requires "
        "at least one (see module docstring); ship at least a minimal, valid stub"
    )


def test_every_shipped_workflow_manifest_passes_check_workflow() -> None:
    manifests = sorted(SHIPPED_WORKFLOWS_DIR.glob("*.yaml"))
    for path in manifests:
        try:
            manifest = parse_manifest(path.read_text())
        except WorkflowError as e:
            raise AssertionError(f"{path}: failed to parse: {e}") from e
        errors = check_workflow(manifest, None)
        assert not errors, f"{path}: {errors}"


# ── the wheel-internal copy must match the plugin copy (review r5-b5) ──
#
# `plugins/super-fr/workflows/` is canonical; `packages/fr/src/fr/workflows/`
# is the same bytes shipped INSIDE the `fr` wheel, so a host with no Claude
# Code marketplace clone (a hermes pod, an OpenCode consumer, a bare
# `uv tool install fr`) can still resolve a shipped shape. Two copies need a
# tripwire, or the packaged one silently rots into the version everyone
# without Claude Code actually runs.

PACKAGED_WORKFLOWS_DIR = REPO_ROOT / "packages" / "fr" / "src" / "fr" / "workflows"

_SYNC_HINT = (
    "run: cp plugins/super-fr/workflows/*.yaml packages/fr/src/fr/workflows/  "
    "(the plugin directory is canonical)"
)


def test_the_packaged_copy_holds_exactly_the_shipped_manifests() -> None:
    plugin = {p.name for p in SHIPPED_WORKFLOWS_DIR.glob("*.yaml")}
    packaged = {p.name for p in PACKAGED_WORKFLOWS_DIR.glob("*.yaml")}

    assert plugin == packaged, (
        f"shipped manifests differ: plugin-only={sorted(plugin - packaged)}, "
        f"packaged-only={sorted(packaged - plugin)} — {_SYNC_HINT}"
    )


def test_the_packaged_copy_is_byte_identical() -> None:
    for path in sorted(SHIPPED_WORKFLOWS_DIR.glob("*.yaml")):
        mirror = PACKAGED_WORKFLOWS_DIR / path.name
        assert mirror.read_bytes() == path.read_bytes(), f"{mirror} drifted — {_SYNC_HINT}"


def test_the_packaged_dir_is_reachable_through_importlib_resources() -> None:
    """The wheel copy is only worth having if `resolve_workflow` can find it
    the way an INSTALLED fr does — through `importlib.resources`, not through
    a path relative to this checkout."""
    from fr.workflow.resolve import packaged_shipped_workflows_dir

    found = packaged_shipped_workflows_dir()

    assert found is not None
    assert {p.name for p in found.glob("*.yaml")} == {
        p.name for p in SHIPPED_WORKFLOWS_DIR.glob("*.yaml")
    }


# ── the shipped fr-goal shape reviews per phase, not once at the end ──
#
# Methodology restoration (phase 1): `implement` is a grouped `for_each`
# carrying implement → review members, so the run cursor enforces
# review-and-fix inside every phase iteration. A trailing single `review`
# step is the flat shape this replaces.


def _shipped_fr_goal():
    return parse_manifest((SHIPPED_WORKFLOWS_DIR / "fr-goal.yaml").read_text())


def test_shipped_fr_goal_reviews_inside_the_phase_iteration() -> None:
    manifest = _shipped_fr_goal()

    assert check_workflow(manifest, None) == []
    group = next(s for s in manifest.steps if s.id == "implement")
    assert group.for_each == "phase"
    assert [m.id for m in group.steps] == ["implement-phase", "review-phase"]
    assert group.steps[1].needs == ("spec", "plan", "journal:plan")
    assert "review" not in [s.id for s in manifest.steps], (
        "the trailing single review step is replaced by the per-phase member"
    )


# ── the review gate is enforced by the cursor, not by prose (phase 3) ──
#
# spec §C / decision D3: an obligation enforced only by an instruction gets
# absorbed (#430). `journal-check` makes `fr run advance` itself refuse to
# proceed to `deliver` while a phase's review is owed, rather than relying on
# `deliver`'s skill prose to remember to check.


def test_shipped_fr_goal_runs_journal_check_between_implement_and_deliver() -> None:
    manifest = _shipped_fr_goal()

    assert check_workflow(manifest, None) == []
    step_ids = [s.id for s in manifest.steps]
    assert "journal-check" in step_ids, "the review gate must be a step in the shape"

    step = next(s for s in manifest.steps if s.id == "journal-check")
    assert step.kind == "cli"
    assert step.run is not None
    assert "{{ artifacts.plan }}" in step.run
    assert "--require-reviews" in step.run

    # ORDER is the whole point: after `deliver`, the PR already exists.
    implement_index = step_ids.index("implement")
    journal_check_index = step_ids.index("journal-check")
    deliver_index = step_ids.index("deliver")
    assert implement_index < journal_check_index < deliver_index, (
        f"journal-check must sit strictly between implement and deliver, got order {step_ids}"
    )


# ── the spec is the contract (spec 2026-09-29-spec-is-the-contract §A) ──
#
# The operator's input feeds brainstorm only. No step after it is gated on the
# input, so the evidence lists are 4.28.0's plus `visual` (#789) and
# `single-phase` (#820), which are not input-layer.

PACKAGED_WORKFLOWS_DIR = REPO_ROOT / "packages" / "fr" / "src" / "fr" / "workflows"
_INPUT_GATES = ("requirements", "coverage", "fidelity", "requirement-rows")


def _step(manifest, step_id: str):
    return next(s for s in manifest.steps if s.id == step_id)


def _both_copies(name: str):
    return [
        parse_manifest((d / f"{name}.yaml").read_text())
        for d in (SHIPPED_WORKFLOWS_DIR, PACKAGED_WORKFLOWS_DIR)
    ]


def test_shipped_fr_goal_evidence_is_the_4_28_lists_plus_visual() -> None:
    for manifest in _both_copies("fr-goal"):
        assert check_workflow(manifest, None) == []
        assert _step(manifest, "brainstorm").evidence == ()
        assert _step(manifest, "spec-review").evidence == ("review", "reviewer", "findings")
        assert _step(manifest, "deliver").evidence == ("tests", "proportionality", "visual")
        members = {m.id: m for m in _step(manifest, "implement").steps}
        assert members["review-phase"].agent is None


def test_shipped_fr_goal_light_evidence_carries_no_input_gate() -> None:
    for manifest in _both_copies("fr-goal-light"):
        assert check_workflow(manifest, None) == []
        assert _step(manifest, "brainstorm").evidence == ()
        assert _step(manifest, "plan").evidence == ("single-phase",)
        assert _step(manifest, "spec-plan-review").evidence == ("review", "reviewer", "findings")
        assert _step(manifest, "deliver").evidence == ("tests", "proportionality", "visual")


def test_run_resolve_knows_no_input_gate() -> None:
    from fr.commands import run_cmd

    for name in _INPUT_GATES:
        assert name not in run_cmd._VERIFIABLE_EVIDENCE
        assert name not in run_cmd._DERIVED_EVIDENCE
        assert name not in run_cmd._DERIVED_FROM


# The removals, undone — the 4.29–4.40 shape an in-flight cursor was started
# against.
_WITH_THE_GATES = (
    (
        "    emits: [spec, journal:spec, acceptance]\n",
        "    emits: [spec, journal:spec, acceptance]\n    evidence: [requirements]\n",
    ),
    (
        "    evidence: [review, reviewer, findings]\n\n  - id: plan\n",
        "    evidence: [review, reviewer, findings, requirements, coverage, fidelity]\n"
        "\n  - id: plan\n",
    ),
    (
        "    evidence: [tests, proportionality, visual]\n",
        "    evidence: [tests, proportionality, requirement-rows, visual]\n",
    ),
)


def test_a_cursor_started_with_the_input_gates_does_not_drift(tmp_path: Path) -> None:
    """Drift compares step and member ids only: every removal is a field, so a
    run started on the 4.29–4.40 shape keeps advancing on this one (R8)."""
    from fr.commands.run_cmd import _check_step_drift
    from fr.run.model import load_run_state

    from tests.unit.test_run_cli import _invoke, _repo

    text = (SHIPPED_WORKFLOWS_DIR / "fr-goal.yaml").read_text()
    for new, old in _WITH_THE_GATES:
        assert new in text, new
        text = text.replace(new, old, 1)
    old_shipped = tmp_path / "old"
    old_shipped.mkdir()
    (old_shipped / "fr-goal.yaml").write_text(text)
    repo = _repo(tmp_path)
    started = _invoke(
        repo, old_shipped, ["run", "start", "fr-goal", "--branch", "b", "--run-id", "r1"]
    )
    assert started.exit_code == 0, started.output

    _check_step_drift(load_run_state(repo, "r1"), _shipped_fr_goal())  # raises on drift


# ── visual evidence (spec 2026-09-28-ui-visual-evidence §C) ──────────────────


def test_shipped_fr_goal_declares_visual_on_the_three_ui_stages() -> None:
    """`visual` on implement-phase, review-phase and deliver — each stage opens
    its own screenshots. A step owing no `visual` row derives `none`."""
    manifest = _shipped_fr_goal()
    implement = _step(manifest, "implement")
    members = {m.id: m for m in implement.steps}

    assert check_workflow(manifest, None) == []
    assert members["implement-phase"].evidence == ("visual",)
    assert members["review-phase"].evidence == ("review", "reviewer", "findings", "visual")
    assert _step(manifest, "deliver").evidence[-1] == "visual"
