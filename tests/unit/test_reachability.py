"""Reachability derived from a shape's inputs (spec §4.E, Phase 8).

The 2026-05-17 gate hardcoded one refusal: `fr apply --yes --to <runner>`
declines unless the plan and spec are merged to `origin/HEAD`, because the
runner works from its own checkout of main. §4.E replaces it with a rule
read off the shape: **a step's `needs` are inputs and must be reachable;
its `emits` are outputs and need not be.**

The consequence that matters is asymmetric, and both halves are pinned
here: a `unit: run` shape dispatches with no spec or plan on main (both are
its outputs), while a `unit: phase` shape still refuses an unmerged plan,
in wording an operator who has seen the old gate recognises.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from fr.workflow.model import parse_manifest

MINIMAL = Path(__file__).parent / "fixtures" / "v2_plan_minimal"

REPO = "derio-net/superpowers-for-vk"

RUN_SHAPE = parse_manifest(
    "workflow: fr-goal\nschema: 1\nunit: run\n"
    "steps:\n"
    "  - id: brainstorm\n    kind: agent\n    emits: [spec]\n"
    "  - id: plan\n    kind: agent\n    needs: [spec]\n    emits: [plan]\n"
    "  - id: implement\n    kind: agent\n    needs: [spec, plan]\n    emits: [pr]\n"
)

PHASE_SHAPE = parse_manifest(
    "workflow: fr-goal\nschema: 1\nunit: phase\n"
    "steps:\n  - id: implement\n    kind: agent\n    needs: [spec, plan]\n    emits: [pr]\n"
)

REPORT_SHAPE = parse_manifest(
    "workflow: research\nschema: 1\nunit: run\n"
    "steps:\n  - id: write\n    kind: agent\n    emits: [report]\n"
)


# ── required_inputs: needs minus emits, repo-tracked only ──────────────


def test_a_run_shape_that_emits_its_spec_and_plan_requires_nothing() -> None:
    from fr.workflow.reachability import required_inputs

    assert required_inputs(RUN_SHAPE) == frozenset()


def test_a_phase_shape_requires_the_spec_and_plan_it_never_emits() -> None:
    from fr.workflow.reachability import required_inputs

    assert required_inputs(PHASE_SHAPE) == frozenset({"spec", "plan"})


def test_only_repo_tracked_artifacts_are_required() -> None:
    """`pr`, `report` and `journal:*` are real inputs with no path on
    `origin/HEAD` to look for — requiring them could only ever mean
    refusing forever."""
    from fr.workflow.reachability import required_inputs

    shape = parse_manifest(
        "workflow: x\nschema: 1\nunit: phase\n"
        "steps:\n"
        "  - id: a\n    kind: agent\n    needs: [plan, report, 'journal:plan']\n    emits: [pr]\n"
    )

    assert required_inputs(shape) == frozenset({"plan"})


def test_an_artifact_emitted_before_it_is_needed_is_not_required() -> None:
    from fr.workflow.reachability import required_inputs

    shape = parse_manifest(
        "workflow: x\nschema: 1\nunit: run\n"
        "steps:\n"
        "  - id: a\n    kind: agent\n    emits: [plan]\n"
        "  - id: b\n    kind: agent\n    needs: [plan]\n    emits: [pr]\n"
    )

    assert required_inputs(shape) == frozenset()


def test_the_shipped_phase_dispatch_shape_is_what_keeps_the_old_gate_alive() -> None:
    """`fr apply --to` still refuses an unmerged plan because the shape it
    dispatches says it needs one — not because `apply_cmd` says so."""
    from fr.workflow.check import check_workflow
    from fr.workflow.reachability import required_inputs
    from fr.workflow.shapes import FR_GOAL_PHASE_DISPATCH

    assert check_workflow(FR_GOAL_PHASE_DISPATCH) == []
    assert required_inputs(FR_GOAL_PHASE_DISPATCH) == frozenset({"spec", "plan"})


# ── check_reachable over an item graph ─────────────────────────────────


def _repo_with_origin(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    for k, v in (("user.email", "t@x"), ("user.name", "T")):
        subprocess.run(["git", "-C", str(work), "config", k, v], check=True)
    (work / "README.md").write_text("seed\n")
    subprocess.run(["git", "-C", str(work), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-q", "-m", "seed"], check=True)
    subprocess.run(
        ["git", "-C", str(work), "push", "-q", "-u", "origin", "HEAD"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(work), "remote", "set-head", "origin", "--auto"],
        check=True,
        capture_output=True,
    )
    return work


def _land_plan(work: Path, *, push: bool, workflow: str | None = None) -> Path:
    """Commit (and optionally push) the fixture plan.

    `workflow` writes the §4.A.1 shape reference into `_meta.yaml` — the
    datum that makes the gate read the PLAN's shape instead of the
    built-in default.
    """
    import shutil

    plan_dir = work / "docs" / "superpowers" / "plans" / "v2_plan_minimal"
    plan_dir.parent.mkdir(parents=True)
    shutil.copytree(MINIMAL, plan_dir)
    if workflow is not None:
        meta = plan_dir / "_meta.yaml"
        meta.write_text(meta.read_text().rstrip("\n") + f"\nworkflow: {workflow}\n")
    spec_dir = work / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True)
    (spec_dir / "fixture-spec-design.md").write_text("# stub spec\n")
    subprocess.run(["git", "-C", str(work), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-q", "-m", "land"], check=True)
    if push:
        subprocess.run(
            ["git", "-C", str(work), "push", "-q", "origin", "HEAD"],
            check=True,
            capture_output=True,
        )
    return plan_dir


def _plan_at(plan_dir: Path):
    from dataclasses import replace as dc_replace

    from fr import parse

    plan = parse(plan_dir)
    return dc_replace(plan, meta=plan.meta.model_copy(update={"target_repo": REPO}))


def test_a_phase_unit_dispatch_refuses_an_unmerged_plan(tmp_path: Path) -> None:
    from fr_dispatch.item_graph import build_items
    from fr_dispatch.reachability import check_reachable

    work = _repo_with_origin(tmp_path)
    plan_dir = _land_plan(work, push=False)
    items = build_items(PHASE_SHAPE, _plan_at(plan_dir))

    refusal = check_reachable(items, work)

    assert refusal is not None
    # Recognisable to an operator who has seen the 2026-05-17 gate.
    assert "refuse to dispatch" in refusal
    assert "not at origin/HEAD" in refusal
    assert "_meta.yaml" in refusal
    assert "01.yaml" in refusal
    assert "fixture-spec-design.md" in refusal


def test_a_phase_unit_dispatch_passes_once_the_plan_and_spec_are_merged(tmp_path: Path) -> None:
    from fr_dispatch.item_graph import build_items
    from fr_dispatch.reachability import check_reachable

    work = _repo_with_origin(tmp_path)
    plan_dir = _land_plan(work, push=True)
    items = build_items(PHASE_SHAPE, _plan_at(plan_dir))

    assert check_reachable(items, work) is None


def test_a_run_unit_dispatch_is_allowed_with_no_spec_or_plan_on_main(tmp_path: Path) -> None:
    """The asymmetry §4.E exists for: the run EMITS its spec and plan, so
    the same unmerged tree that refuses a phase dispatch allows this one."""
    from fr_dispatch.item_graph import build_items
    from fr_dispatch.reachability import check_reachable

    work = _repo_with_origin(tmp_path)
    plan_dir = _land_plan(work, push=False)
    plan = _plan_at(plan_dir)

    phase_items = build_items(PHASE_SHAPE, plan)
    run_items = build_items(RUN_SHAPE, plan, run_id="2026-08-14-ticket-polling")

    assert check_reachable(phase_items, work) is not None
    assert check_reachable(run_items, work) is None


def test_a_shape_that_emits_only_a_document_has_nothing_to_check(tmp_path: Path) -> None:
    from fr_dispatch.item_graph import build_items
    from fr_dispatch.reachability import check_reachable

    work = _repo_with_origin(tmp_path)
    items = build_items(REPORT_SHAPE, repo=REPO, run_id="2026-08-14-market-scan")

    assert check_reachable(items, work) is None


def test_the_refusal_names_the_item_so_a_multi_item_tick_says_which(tmp_path: Path) -> None:
    from fr_dispatch.item_graph import build_items
    from fr_dispatch.reachability import check_reachable

    work = _repo_with_origin(tmp_path)
    plan_dir = _land_plan(work, push=False)
    items = build_items(PHASE_SHAPE, _plan_at(plan_dir))

    refusal = check_reachable(items, work)

    assert refusal is not None
    assert items[0].id in refusal


def test_a_cross_repo_input_is_checked_through_the_tracker_when_one_is_given(
    tmp_path: Path,
) -> None:
    """A ref in another repo cannot be resolved by this repo's git — the
    coordinate is only checkable through a client that can read that repo.
    Without one it is skipped, exactly as the 2026-05-17 gate skipped a
    cross-repo spec (the operator is trusted for it)."""
    import shutil

    from fr import parse
    from fr_dispatch.item_graph import build_items
    from fr_dispatch.reachability import check_reachable

    from tests.unit.fakes import FakeGhClient

    work = _repo_with_origin(tmp_path)
    plan_dir = work / "docs" / "superpowers" / "plans" / "v2_plan_minimal"
    plan_dir.parent.mkdir(parents=True)
    shutil.copytree(MINIMAL, plan_dir)
    meta = plan_dir / "_meta.yaml"
    meta.write_text(
        meta.read_text().replace(
            "spec: docs/superpowers/specs/fixture-spec-design.md",
            "spec: other-org/other-repo:docs/superpowers/specs/elsewhere-design.md",
        )
    )
    subprocess.run(["git", "-C", str(work), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-q", "-m", "land"], check=True)
    subprocess.run(
        ["git", "-C", str(work), "push", "-q", "origin", "HEAD"],
        check=True,
        capture_output=True,
    )
    items = build_items(PHASE_SHAPE, parse(plan_dir))

    # No client: the cross-repo spec is trusted, so the plan alone decides.
    assert check_reachable(items, work) is None

    absent = FakeGhClient()
    refusal = check_reachable(items, work, gh=absent)
    assert refusal is not None
    assert "other-org/other-repo" in refusal

    present = FakeGhClient()
    present.remote_files.add(("other-org/other-repo", "docs/superpowers/specs/elsewhere-design.md"))
    assert check_reachable(items, work, gh=present) is None


# ── the old gate, now derived ──────────────────────────────────────────


def test_apply_cmds_gate_reads_the_shape_rather_than_hardcoding_plan_and_spec() -> None:
    """The refusal is still `_check_plan_reachable_on_origin_head(plan,
    repo_root)` — the name and signature existing callers and tests use —
    but what it looks for now comes from `required_inputs`."""
    import inspect

    from fr.commands import apply_cmd

    src = inspect.getsource(apply_cmd._check_plan_reachable_on_origin_head)
    assert "required_inputs" in src


# ── the gate reads the PLAN's shape (spec §4.A.1, Phase 12) ───────────
#
# TEST CHANGE DECLARED: this section's single test used to monkeypatch
# `apply_cmd.FR_GOAL_PHASE_DISPATCH` — the module-level constant the gate
# read. `apply_cmd` no longer holds a shape of its own (it resolves the
# plan's), so the seam moved from "patch the module constant" to "write
# the shape reference into the plan and author the shape in the repo",
# which is the surface an operator actually has. The BEHAVIOUR asserted is
# unchanged: a shape that does not need the plan stops gating on it.

SPEC_ONLY_SHAPE_YAML = """\
workflow: spec-only-dispatch
schema: 1
unit: phase
requires: [git, browser]
steps:
  - id: implement
    kind: agent
    needs: [spec]
    emits: [pr]
"""
"""Deliberately DIFFERENT from `FR_GOAL_PHASE_DISPATCH` in both axes this
phase wires: `needs: [spec]` (not `{spec, plan}`) and `requires:
[git, browser]` (not `{git, tests, scm}`). A fixture shape that happened
to need the same things would pass against the old hardcoded code and
prove nothing."""


def _author_repo_shape(work: Path, name: str, text: str) -> None:
    d = work / "docs" / "superpowers" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.yaml").write_text(text)


def test_a_shape_that_does_not_need_the_plan_does_not_gate_on_it(tmp_path) -> None:
    """The derivation is real, not decorative: a plan whose OWN shape drops
    `plan` from its needs stops being refused for an unmerged plan — same
    unmerged tree, different verdict, chosen by the plan."""
    from fr.commands import apply_cmd

    work = _repo_with_origin(tmp_path)
    default_plan = _plan_at(_land_plan(work, push=False))

    assert apply_cmd._check_plan_reachable_on_origin_head(default_plan, work) != []

    other = _repo_with_origin(tmp_path / "second")
    _author_repo_shape(other, "spec-only-dispatch", SPEC_ONLY_SHAPE_YAML)
    shaped_plan = _plan_at(_land_plan(other, push=False, workflow="spec-only-dispatch"))

    missing = apply_cmd._check_plan_reachable_on_origin_head(shaped_plan, other)

    assert [str(p) for p in missing] == ["docs/superpowers/specs/fixture-spec-design.md"]


def test_a_plan_naming_an_unresolvable_shape_raises_rather_than_defaulting(tmp_path) -> None:
    """Never a silent fallback: defaulting here would gate a plan on the
    WRONG shape's inputs and then dispatch it at the wrong granularity."""
    import pytest
    from fr.commands import apply_cmd
    from fr.workflow.model import WorkflowError

    work = _repo_with_origin(tmp_path)
    plan = _plan_at(_land_plan(work, push=True, workflow="no-such-shape"))

    with pytest.raises(WorkflowError, match="no-such-shape"):
        apply_cmd._check_plan_reachable_on_origin_head(plan, work)


def test_apply_refuses_a_plan_whose_shape_cannot_be_resolved(tmp_path, monkeypatch) -> None:
    """End of the wire: `fr apply --yes --to` exits 2 naming the shape, and
    makes no GitHub calls — an unresolvable shape must not read as an
    origin/HEAD problem, and must never dispatch."""
    from fr.commands import apply_cmd

    from tests.unit.fakes import FakeGhClient

    work = _repo_with_origin(tmp_path)
    plan_dir = _land_plan(work, push=True, workflow="no-such-shape")

    fake = FakeGhClient()
    monkeypatch.setattr(apply_cmd, "_make_gh_client", lambda: fake)

    rc, text, json_out = apply_cmd._apply_one(plan_dir, fake, yes=True, to="vk")

    assert rc == 2
    assert "no-such-shape" in text
    assert "origin/HEAD" not in text
    assert json_out.get("workflow_error")
    assert fake.calls == []


RUN_SHAPE_YAML = """\
workflow: run-goal
schema: 1
unit: run
requires: [git]
steps:
  - id: brainstorm
    kind: agent
    emits: [spec]
  - id: plan
    kind: agent
    needs: [spec]
    emits: [plan]
  - id: implement
    kind: agent
    needs: [spec, plan]
    emits: [pr]
"""


def test_a_plan_declaring_a_run_shape_passes_the_gate_with_nothing_on_main(tmp_path) -> None:
    """The §4.E asymmetry, now reachable from the operator's side: the plan
    NAMES a run-unit shape whose spec and plan are its own outputs, so the
    same unmerged tree that refuses a phase-unit dispatch stops refusing.

    The choice is the plan's — no monkeypatching, no constant swap.
    """
    from fr.commands import apply_cmd

    work = _repo_with_origin(tmp_path)
    _author_repo_shape(work, "run-goal", RUN_SHAPE_YAML)
    plan = _plan_at(_land_plan(work, push=False, workflow="run-goal"))

    assert apply_cmd._check_plan_reachable_on_origin_head(plan, work) == []


def test_a_plan_declaring_no_shape_still_refuses_the_same_unmerged_tree(tmp_path) -> None:
    """The other half, unchanged: today's plans name no shape, resolve
    FR_GOAL_PHASE_DISPATCH, and are still refused until plan + spec merge."""
    from fr.commands import apply_cmd

    work = _repo_with_origin(tmp_path)
    plan = _plan_at(_land_plan(work, push=False))

    missing = [str(p) for p in apply_cmd._check_plan_reachable_on_origin_head(plan, work)]

    assert "docs/superpowers/specs/fixture-spec-design.md" in missing
    assert any("_meta.yaml" in p for p in missing)
