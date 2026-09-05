"""Workflow shape manifest schema + parser — spec §4.A, Phase 6.

`fr.workflow.model.parse_manifest` is the ONE way a manifest enters the
system (resolution, `fr workflow check`, and — later phases — `fr run`
all go through it), so every structural failure (unknown top-level key,
unsupported schema) is asserted here as a `WorkflowError`, never a raw
pydantic/yaml exception leaking to a caller.
"""

from __future__ import annotations

import pytest
from fr.workflow.model import Step, WorkflowError, WorkflowManifest, parse_manifest

# The spec §4.A example manifest, verbatim shape (trimmed to keep the test
# file readable — every step kind/field combination the spec shows is
# still represented at least once).
FULL_MANIFEST = """
workflow: fr-goal
schema: 1
description: TDD feature delivery, goal to reviewed PR.

unit: run
requires: [git, tests, scm]

steps:
  - id: isolate
    kind: cli
    run: fr isolation up --branch {{ run.branch }}

  - id: brainstorm
    kind: agent
    skill: super-fr:fr-brainstorming
    gate: operator
    emits: [spec, journal:spec]

  - id: spec-review
    kind: agent
    needs: [spec]
    emits: [journal:spec]

  - id: plan
    kind: agent
    skill: super-fr:fr-plan
    needs: [spec]
    emits: [plan, journal:plan]

  - id: plan-review
    kind: cli
    run: fr plan self-review {{ artifacts.plan }}

  - id: implement
    kind: agent
    agent: super-fr:fr-phase-executor
    needs: [spec, plan]
    for_each: phase
    tier: from_phase
    emits: [journal:plan]

  - id: review
    kind: agent
    skill: superpowers:requesting-code-review
    needs: [spec, plan]
    emits: [journal:plan]

  - id: deliver
    kind: cli
    run: fr run deliver {{ run.id }}
    emits: [pr]
"""


def test_parses_the_spec_example_manifest() -> None:
    manifest = parse_manifest(FULL_MANIFEST)
    assert isinstance(manifest, WorkflowManifest)
    assert manifest.workflow == "fr-goal"
    assert manifest.schema_version == 1
    assert manifest.description == "TDD feature delivery, goal to reviewed PR."
    assert manifest.unit == "run"
    assert manifest.requires == ("git", "tests", "scm")
    assert [s.id for s in manifest.steps] == [
        "isolate",
        "brainstorm",
        "spec-review",
        "plan",
        "plan-review",
        "implement",
        "review",
        "deliver",
    ]


def test_cli_step_carries_run() -> None:
    manifest = parse_manifest(FULL_MANIFEST)
    isolate = manifest.steps[0]
    assert isolate.kind == "cli"
    assert isolate.run == "fr isolation up --branch {{ run.branch }}"
    assert isolate.skill is None
    assert isolate.agent is None
    assert isolate.gate is None
    assert isolate.tier is None
    assert isolate.for_each is None
    assert isolate.needs == ()
    assert isolate.emits == ()


def test_agent_step_with_skill_and_gate() -> None:
    manifest = parse_manifest(FULL_MANIFEST)
    brainstorm = manifest.steps[1]
    assert brainstorm.kind == "agent"
    assert brainstorm.skill == "super-fr:fr-brainstorming"
    assert brainstorm.gate == "operator"
    assert brainstorm.emits == ("spec", "journal:spec")


def test_agent_step_with_needs() -> None:
    manifest = parse_manifest(FULL_MANIFEST)
    spec_review = manifest.steps[2]
    assert spec_review.needs == ("spec",)
    assert spec_review.emits == ("journal:spec",)


def test_agent_step_with_agent_for_each_and_tier() -> None:
    manifest = parse_manifest(FULL_MANIFEST)
    implement = manifest.steps[5]
    assert implement.kind == "agent"
    assert implement.agent == "super-fr:fr-phase-executor"
    assert implement.for_each == "phase"
    assert implement.tier == "from_phase"
    assert implement.needs == ("spec", "plan")


def test_step_id_and_kind_are_required() -> None:
    with pytest.raises(WorkflowError):
        parse_manifest(
            "workflow: x\nschema: 1\nunit: run\nsteps:\n  - kind: cli\n    run: echo hi\n"
        )
    with pytest.raises(WorkflowError):
        parse_manifest("workflow: x\nschema: 1\nunit: run\nsteps:\n  - id: a\n    run: echo hi\n")


def test_unknown_top_level_key_fails_loud() -> None:
    text = FULL_MANIFEST + "\nsome_unknown_key: true\n"
    with pytest.raises(WorkflowError):
        parse_manifest(text)


def test_unknown_step_key_fails_loud() -> None:
    text = """
workflow: x
schema: 1
unit: run
steps:
  - id: a
    kind: cli
    run: echo hi
    bogus: true
"""
    with pytest.raises(WorkflowError):
        parse_manifest(text)


def test_schema_2_is_rejected_naming_the_supported_version() -> None:
    text = "workflow: x\nschema: 2\nunit: run\nsteps: []\n"
    with pytest.raises(WorkflowError) as exc_info:
        parse_manifest(text)
    message = str(exc_info.value)
    assert "1" in message
    assert "2" in message


def test_missing_schema_fails_loud() -> None:
    text = "workflow: x\nunit: run\nsteps: []\n"
    with pytest.raises(WorkflowError):
        parse_manifest(text)


def test_unit_must_be_one_of_run_phase_spec() -> None:
    text = "workflow: x\nschema: 1\nunit: nonsense\nsteps: []\n"
    with pytest.raises(WorkflowError):
        parse_manifest(text)


def test_kind_must_be_cli_or_agent() -> None:
    text = "workflow: x\nschema: 1\nunit: run\nsteps:\n  - id: a\n    kind: robot\n"
    with pytest.raises(WorkflowError):
        parse_manifest(text)


def test_description_defaults_to_empty_string() -> None:
    text = "workflow: x\nschema: 1\nunit: run\nsteps: []\n"
    manifest = parse_manifest(text)
    assert manifest.description == ""
    assert manifest.requires == ()
    assert manifest.steps == ()


def test_manifest_and_step_are_frozen() -> None:
    manifest = parse_manifest(FULL_MANIFEST)
    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError on frozen mutation
        manifest.workflow = "other"  # type: ignore[misc]
    step = manifest.steps[0]
    with pytest.raises(Exception):  # noqa: B017
        step.id = "other"  # type: ignore[misc]


def test_not_a_mapping_fails_loud() -> None:
    with pytest.raises(WorkflowError):
        parse_manifest("- just\n- a\n- list\n")


def test_invalid_yaml_fails_loud() -> None:
    with pytest.raises(WorkflowError):
        parse_manifest("workflow: [unterminated\n")


def test_step_pydantic_type_is_reachable_directly() -> None:
    step = Step(id="a", kind="cli", run="echo hi")
    assert step.id == "a"
    assert step.kind == "cli"
