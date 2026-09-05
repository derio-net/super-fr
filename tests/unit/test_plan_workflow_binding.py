"""A plan names its shape — spec §4.A.1 (Phase 12).

`resolve_workflow` answers *"given a name, which manifest?"*. Dispatch
needs the prior question — *"given a plan on disk, which name?"* — and
`_meta.yaml` carried no answer: `plan`, `spec`, `target_repo`,
`fr_version`, `created`, `parent_plan`, nothing naming a workflow. One
missing field made `unit`, `requires` and `needs` unreachable from every
shipped caller.

Two invariants this module exists to keep honest:

1. **Absence means exactly today.** A plan with no `workflow:` resolves
   `FR_GOAL_PHASE_DISPATCH` and ticks identically — the back-compat that
   lets the live bridge keep working through the upgrade.
2. **An unresolvable name is an ERROR, never a fallback to the default.**
   Falling back would dispatch a plan at the wrong granularity while
   reporting success.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fr._yaml import dump_plan_yaml

MINIMAL = Path(__file__).parent / "fixtures" / "v2_plan_minimal"

# A shape whose `needs` and `requires` genuinely DIFFER from
# FR_GOAL_PHASE_DISPATCH's ({spec, plan} / {git, tests, scm}) — a fixture
# that happened to need the same things would pass against the old
# hardcoded code and prove nothing.
SPEC_ONLY_YAML = """\
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


def _plan_dir(tmp_path: Path, *, workflow: str | None = None) -> Path:
    """A parseable plan folder, optionally naming a shape.

    `_meta.yaml` is (re)written in the canonical key order `plan_ops.create`
    emits — the fixture's own file predates `fr_version` and carries an
    unquoted date, which would make the byte-stability assertion about YAML
    scalar styles rather than about this field.
    """
    # `fr.parser._find_repo_root` is filesystem-only (walks up looking for
    # `.git`), so a marker directory is enough to give the plan a repo root
    # — which is where repo-authored shapes are searched.
    (tmp_path / ".git").mkdir(exist_ok=True)
    plan_dir = tmp_path / "docs" / "superpowers" / "plans" / "v2_plan_minimal"
    plan_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(MINIMAL, plan_dir)
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    (specs / "fixture-spec-design.md").write_text("# stub spec\n")
    meta: dict[str, object] = {
        "schema_version": 2,
        "plan": "2026-05-09-fixture-minimal",
        "spec": "docs/superpowers/specs/fixture-spec-design.md",
        "target_repo": "derio-net/superpowers-for-vk",
        "created": "2026-05-09",
    }
    if workflow is not None:
        meta["workflow"] = workflow
    (plan_dir / "_meta.yaml").write_text(dump_plan_yaml(meta))
    return plan_dir


def _shipped(tmp_path: Path, name: str, text: str) -> Path:
    root = tmp_path / "shipped"
    root.mkdir(exist_ok=True)
    (root / f"{name}.yaml").write_text(text)
    return root


def _repo_shape(repo_root: Path, name: str, text: str) -> None:
    d = repo_root / "docs" / "superpowers" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.yaml").write_text(text)


# ── Task 1: the field ──────────────────────────────────────────────────


def test_plan_meta_accepts_a_workflow_name() -> None:
    from fr.types import PlanMeta

    meta = PlanMeta(
        schema_version=2,
        plan="p",
        target_repo="o/r",
        created="2026-08-27",
        workflow="fr-goal",
    )

    assert meta.workflow == "fr-goal"


def test_plan_meta_still_forbids_unknown_keys() -> None:
    """`workflow` is accepted because it is DECLARED, not because the
    model went permissive — extra="forbid" is what makes the key a real
    schema change (hence the >=4.0.0 floor)."""
    from fr.types import PlanMeta
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PlanMeta(
            schema_version=2,
            plan="p",
            target_repo="o/r",
            created="2026-08-27",
            wrokflow="typo",  # type: ignore[call-arg]
        )


def test_a_meta_without_the_key_parses_and_names_no_shape(tmp_path: Path) -> None:
    """Back-compat: every plan in the wild predates this field."""
    from fr import parse

    plan = parse(_plan_dir(tmp_path))

    assert plan.meta.workflow is None


def test_a_meta_with_the_key_keeps_it_rather_than_dropping_it(tmp_path: Path) -> None:
    from fr import parse

    plan = parse(_plan_dir(tmp_path, workflow="spec-only-dispatch"))

    assert plan.meta.workflow == "spec-only-dispatch"


def test_the_workflow_key_round_trips_byte_stably(tmp_path: Path) -> None:
    """text → parse → dump reproduces the file. `workflow` is declared
    LAST so a plan written before it existed keeps its byte order."""
    from fr import parse

    plan_dir = _plan_dir(tmp_path, workflow="spec-only-dispatch")
    original = (plan_dir / "_meta.yaml").read_text()

    plan = parse(plan_dir)
    redumped = dump_plan_yaml(plan.meta.model_dump(exclude_none=True, exclude_defaults=True))

    assert redumped == original
    assert redumped.rstrip().endswith("workflow: spec-only-dispatch")


def test_a_meta_without_the_key_round_trips_without_growing_a_null(tmp_path: Path) -> None:
    """`workflow: null` in every existing plan would be a regression."""
    from fr import parse

    plan_dir = _plan_dir(tmp_path)
    plan = parse(plan_dir)

    redumped = dump_plan_yaml(plan.meta.model_dump(exclude_none=True, exclude_defaults=True))

    assert "workflow" not in redumped


# ── Task 2: plan → manifest ────────────────────────────────────────────


def test_a_plan_naming_no_shape_resolves_the_default(tmp_path: Path) -> None:
    """Absence means exactly today: the SAME object `tick` and `fr apply`
    have always defaulted to, not a re-parse that merely looks like it."""
    from fr import parse
    from fr.workflow.resolve import workflow_for_plan
    from fr.workflow.shapes import FR_GOAL_PHASE_DISPATCH

    plan = parse(_plan_dir(tmp_path))

    assert workflow_for_plan(plan, tmp_path) is FR_GOAL_PHASE_DISPATCH


def test_a_plan_naming_a_shipped_shape_resolves_it(tmp_path: Path) -> None:
    from fr import parse
    from fr.workflow.resolve import workflow_for_plan

    plan = parse(_plan_dir(tmp_path, workflow="spec-only-dispatch"))
    shipped = _shipped(tmp_path, "spec-only-dispatch", SPEC_ONLY_YAML)

    manifest = workflow_for_plan(plan, tmp_path, shipped_root=shipped)

    assert manifest.workflow == "spec-only-dispatch"
    assert manifest.unit == "phase"
    assert manifest.requires == ("git", "browser")


def test_a_repo_authored_shape_beats_the_shipped_one_of_the_same_name(tmp_path: Path) -> None:
    from fr import parse
    from fr.workflow.resolve import workflow_for_plan

    plan = parse(_plan_dir(tmp_path, workflow="spec-only-dispatch"))
    shipped = _shipped(tmp_path, "spec-only-dispatch", SPEC_ONLY_YAML)
    _repo_shape(
        tmp_path,
        "spec-only-dispatch",
        SPEC_ONLY_YAML.replace("requires: [git, browser]", "requires: [network]"),
    )

    manifest = workflow_for_plan(plan, tmp_path, shipped_root=shipped)

    assert manifest.requires == ("network",)


def test_a_shape_that_does_not_resolve_is_an_error_not_the_default(tmp_path: Path) -> None:
    """The refusal this whole section exists for. A silent fallback would
    dispatch at the wrong granularity while reporting success."""
    from fr import parse
    from fr.workflow.model import WorkflowError
    from fr.workflow.resolve import workflow_for_plan

    plan = parse(_plan_dir(tmp_path, workflow="no-such-shape"))
    shipped = _shipped(tmp_path, "spec-only-dispatch", SPEC_ONLY_YAML)

    with pytest.raises(WorkflowError) as exc:
        workflow_for_plan(plan, tmp_path, shipped_root=shipped)

    message = str(exc.value)
    assert "no-such-shape" in message
    # Names the PLAN (which one is broken) and both searched paths (where
    # to put the fix).
    assert plan.meta.plan in message
    assert str(tmp_path / "docs" / "superpowers" / "workflows" / "no-such-shape.yaml") in message
    assert str(shipped / "no-such-shape.yaml") in message


def test_the_repo_root_defaults_to_the_plans_own(tmp_path: Path) -> None:
    """The bridge has a `Plan` and no separate root to hand in; a plan
    parsed inside a repo already knows where its overrides live."""
    from dataclasses import replace as dc_replace

    from fr import parse
    from fr.workflow.resolve import workflow_for_plan

    plan = parse(_plan_dir(tmp_path, workflow="spec-only-dispatch"))
    plan = dc_replace(plan, repo_root=tmp_path)
    _repo_shape(tmp_path, "spec-only-dispatch", SPEC_ONLY_YAML)

    assert workflow_for_plan(plan).workflow == "spec-only-dispatch"


def test_a_named_shape_with_no_repo_root_to_search_fails_loudly(tmp_path: Path) -> None:
    """No root, no repo overrides — refusing beats quietly resolving only
    half the search order (the shipped half) and calling it resolution."""
    from dataclasses import replace as dc_replace

    from fr import parse
    from fr.workflow.model import WorkflowError
    from fr.workflow.resolve import workflow_for_plan

    plan = parse(_plan_dir(tmp_path, workflow="spec-only-dispatch"))
    plan = dc_replace(plan, repo_root=None)

    with pytest.raises(WorkflowError, match="repo root"):
        workflow_for_plan(plan)


def test_no_repo_root_is_still_fine_when_the_plan_names_no_shape(tmp_path: Path) -> None:
    """The default needs no lookup at all, so a rootless plan still ticks."""
    from dataclasses import replace as dc_replace

    from fr import parse
    from fr.workflow.resolve import workflow_for_plan
    from fr.workflow.shapes import FR_GOAL_PHASE_DISPATCH

    plan = dc_replace(parse(_plan_dir(tmp_path)), repo_root=None)

    assert workflow_for_plan(plan) is FR_GOAL_PHASE_DISPATCH


# ── Task 4: the authoring surface + the version floor ──────────────────


def _cli_repo(tmp_path: Path) -> Path:
    """A git repo with the MIGRATED superpowers layout (no archived-plans/,
    which `require_migrated_layout` hard-stops on)."""
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@x"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True)
    (repo / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (repo / "docs" / "superpowers" / "plans").mkdir()
    return repo


def _create(repo: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    from fr.cli import app
    from typer.testing import CliRunner

    monkeypatch.chdir(repo)
    return CliRunner().invoke(
        app,
        ["plan", "create", "--slug", "2026-08-27-shaped", "--target-repo", "o/r", *args],
    )


def _meta_text(repo: Path) -> str:
    return (
        repo / "docs" / "superpowers" / "plans" / "2026-08-27-shaped" / "_meta.yaml"
    ).read_text()


def test_plan_create_without_the_flag_writes_no_workflow_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`workflow: null` in every newly created plan would be a regression —
    the file must stay byte-identical to what today's fr writes."""
    repo = _cli_repo(tmp_path)

    result = _create(repo, monkeypatch)

    assert result.exit_code == 0, result.output
    text = _meta_text(repo)
    assert "workflow" not in text
    assert "fr_version: '>=3.0.0,<5.0.0'" in text


def test_plan_create_with_the_flag_writes_the_key_and_floors_fr_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`PlanMeta` is extra="forbid", so a plan carrying `workflow:` is a HARD
    parse failure on fr < 4.0.0 — not a warning. The floor is the plan
    telling older fr not to try."""
    from fr import parse

    repo = _cli_repo(tmp_path)

    result = _create(repo, monkeypatch, "--workflow", "fr-goal-phase-dispatch")

    assert result.exit_code == 0, result.output
    text = _meta_text(repo)
    assert "workflow: fr-goal-phase-dispatch" in text
    assert "fr_version: '>=4.0.0" in text
    plan = parse(repo / "docs" / "superpowers" / "plans" / "2026-08-27-shaped")
    assert plan.meta.workflow == "fr-goal-phase-dispatch"


def test_plan_create_refuses_a_workflow_plan_whose_fr_version_admits_older_fr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit constraint is the operator's, so it is REFUSED rather
    than silently rewritten — but one that lets fr 3.x load a plan it
    cannot parse is a promise the plan can't keep."""
    repo = _cli_repo(tmp_path)

    result = _create(
        repo,
        monkeypatch,
        "--workflow",
        "fr-goal-phase-dispatch",
        "--fr-version",
        ">=3.0.0,<5.0.0",
    )

    assert result.exit_code == 2, result.output
    assert "4.0.0" in result.output
    assert not (repo / "docs" / "superpowers" / "plans" / "2026-08-27-shaped").exists()


def test_plan_create_accepts_an_explicit_constraint_that_already_floors_at_4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _cli_repo(tmp_path)

    result = _create(
        repo,
        monkeypatch,
        "--workflow",
        "fr-goal-phase-dispatch",
        "--fr-version",
        ">=4.0.0,<4.5.0",
    )

    assert result.exit_code == 0, result.output
    assert "fr_version: '>=4.0.0,<4.5.0'" in _meta_text(repo)


def test_plan_create_leaves_fr_version_alone_without_the_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No shape, no floor: a plan that omits the key stays loadable by
    older fr, which is the whole reason the key is optional."""
    repo = _cli_repo(tmp_path)

    result = _create(repo, monkeypatch, "--fr-version", ">=3.0.0,<5.0.0")

    assert result.exit_code == 0, result.output
    assert "fr_version: '>=3.0.0,<5.0.0'" in _meta_text(repo)


# ── self-review validates the reference ────────────────────────────────


def test_self_review_errors_when_the_named_shape_does_not_resolve(tmp_path: Path) -> None:
    from fr import parse
    from fr.plan_ops import self_review

    plan = parse(_plan_dir(tmp_path, workflow="no-such-shape"))
    issues = self_review(plan)

    assert [i for i in issues if i.severity == "error" and "no-such-shape" in i.message]


def test_self_review_errors_when_the_named_shape_fails_check_workflow(tmp_path: Path) -> None:
    """Resolving is not enough — a shape with a capability outside the
    closed set would refuse every dispatch at tick time instead."""
    from fr import parse
    from fr.plan_ops import self_review

    plan_dir = _plan_dir(tmp_path, workflow="bad-shape")
    _repo_shape(
        tmp_path,
        "bad-shape",
        SPEC_ONLY_YAML.replace("workflow: spec-only-dispatch", "workflow: bad-shape").replace(
            "requires: [git, browser]", "requires: [teleport]"
        ),
    )

    issues = self_review(parse(plan_dir))

    assert [i for i in issues if i.severity == "error" and "teleport" in i.message]


def test_self_review_is_clean_for_a_plan_naming_a_valid_shape(tmp_path: Path) -> None:
    from fr import parse
    from fr.plan_ops import self_review

    plan_dir = _plan_dir(tmp_path, workflow="spec-only-dispatch")
    _repo_shape(tmp_path, "spec-only-dispatch", SPEC_ONLY_YAML)

    assert self_review(parse(plan_dir)) == []


def test_self_review_says_nothing_about_a_plan_that_names_no_shape(tmp_path: Path) -> None:
    """Back-compat: existing plans must not grow a new review error."""
    from fr import parse
    from fr.plan_ops import self_review

    assert self_review(parse(_plan_dir(tmp_path))) == []


# ── review r5-b6: an exact 3.x pin must not slip through ──────────────


def test_an_exact_pre_4_pin_is_recognised_as_admitting_fr_3() -> None:
    """The original five probes (`0.1.0`, `2.0.0`, `3.0.0`, `3.19.0`,
    `3.999.999`) answered `==3.5.0` with a flat "no fr 3.x is admitted" —
    the constraint shape most likely to be hand-typed, waved through."""
    from fr.commands.plan_cmd import _admits_pre_4

    for pinned in ("==3.5.0", "==3.1.0", "==2.5.0", "==1.0.0", "==3.20.0"):
        assert _admits_pre_4(pinned), pinned


def test_a_4_only_constraint_still_admits_nothing_pre_4() -> None:
    from fr.commands.plan_cmd import _admits_pre_4

    for four_plus in (">=4.0.0,<5.0.0", "==4.0.0", ">=4.1"):
        assert not _admits_pre_4(four_plus), four_plus
