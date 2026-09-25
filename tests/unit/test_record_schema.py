"""The `record` kind and the `emits:` vocabulary behind it (spec
`2026-09-25-lean-cost-aware-process-design.md` §5.C.1, §5.C.2.1)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SHIPPED = REPO / "plugins" / "super-fr" / "workflows" / "fr-goal.yaml"
PACKAGED = REPO / "packages" / "fr" / "src" / "fr" / "workflows" / "fr-goal.yaml"

# The spec's own §5.C.1 example, ellipses filled in.
SPEC_EXAMPLE = textwrap.dedent(
    """\
    schema_version: 1
    run: 2026-09-25-feat-x
    step: implement-phase
    item: phase/2
    outcome: done                  # done | failed | blocked
    ticks: [P2.T1.S1, P2.T1.S2]
    refactor: {P2.T2: "none: two tuple entries, nothing to extract"}
    journal:
      - {kind: decision, id: d-p2-guard, title: "guard", body: "why"}
      - {kind: finding, id: p2-f1, title: "f", body: "b", review_scope: in}
    resolves:
      - {id: p2-f1, state: fixed, body: "fixed it"}
    acceptance:                    # brainstorm only
      - {id: row-a, capability: c, acceptance: a, origin: ["o:d/x.md"], status: not-implemented}
    evidence: {review: r-p2, reviewer: agent-1}
    """
)


def test_the_spec_example_parses() -> None:
    from fr.record.model import parse_record

    record = parse_record(SPEC_EXAMPLE)
    assert record.step == "implement-phase"
    assert record.item == "phase/2"
    assert [t.id for t in record.tick_items()] == ["P2.T1.S1", "P2.T1.S2"]
    assert record.refactor == {"P2.T2": "none: two tuple entries, nothing to extract"}
    assert [j.id for j in record.journal] == ["d-p2-guard", "p2-f1"]
    assert record.resolves[0].state == "fixed"
    assert record.acceptance[0].status == "not-implemented"
    assert record.evidence == {"review": "r-p2", "reviewer": "agent-1"}


@pytest.mark.parametrize(
    "text, needle",
    [
        ("bogus: 1\n", "bogus"),
        ("ticks: [P2.T1]\n", "P<n>.T<m>.S<k>"),
        ("refactor: {T2: x}\n", "task id"),
        ("journal: [{kind: nope, title: t}]\n", "journal"),
        ("resolves: [{id: f, state: deferred, body: b}]\n", "tracked_by"),
        ("schema_version: 2\n", "schema_version"),
        ("- a list\n", "mapping"),
    ],
)
def test_a_malformed_record_is_refused_with_its_problem_named(text: str, needle: str) -> None:
    from fr.record.model import RecordError, parse_record

    with pytest.raises(RecordError, match=needle):
        parse_record(text)


def _step(emits: tuple[str, ...]):
    from fr.workflow.model import Step

    return Step(id="s", kind="agent", emits=emits)


@pytest.mark.parametrize(
    "emits, expected",
    [
        ((), {"outcome", "evidence"}),
        (("journal:plan",), {"outcome", "evidence", "journal", "resolves"}),
        (("plan:ticks",), {"outcome", "evidence", "ticks", "refactor"}),
        (("acceptance",), {"outcome", "evidence", "acceptance"}),
        (("spec", "pr"), {"outcome", "evidence"}),
        (
            ("journal:plan", "plan:ticks"),
            {"outcome", "evidence", "journal", "resolves", "ticks", "refactor"},
        ),
    ],
)
def test_allowed_sections_follow_the_emits_table(emits, expected) -> None:
    from fr.record.model import allowed_sections

    assert allowed_sections(_step(emits)) == expected


def test_a_member_with_no_emits_falls_back_to_its_group() -> None:
    from fr.record.model import allowed_sections

    assert "ticks" in allowed_sections(_step(()), _step(("plan:ticks",)))


def test_the_record_path_is_step_and_item() -> None:
    from fr.record.model import record_path

    p = record_path(Path("/r"), "run-1", "implement-phase", "phase/2")
    assert p == Path("/r/docs/superpowers/runs/run-1.records/implement-phase__phase-2.yaml")
    assert record_path(Path("/r"), "run-1", "deliver").name == "deliver.yaml"


def test_both_fr_goal_manifests_are_identical_and_carry_the_new_tokens() -> None:
    assert SHIPPED.read_text() == PACKAGED.read_text()
    steps = {s["id"]: s for s in yaml.safe_load(SHIPPED.read_text())["steps"]}
    members = {m["id"]: m for m in steps["implement"]["steps"]}
    assert "plan:ticks" in members["implement-phase"]["emits"]
    assert "acceptance" in steps["brainstorm"]["emits"]
    assert "acceptance" in steps["deliver"]["emits"]


def test_workflow_check_accepts_the_new_tokens() -> None:
    from fr.workflow.artifacts import RECORD_EMIT_TOKENS
    from fr.workflow.check import check_workflow
    from fr.workflow.model import parse_manifest

    assert {"plan:ticks", "acceptance"} <= RECORD_EMIT_TOKENS
    assert check_workflow(parse_manifest(SHIPPED.read_text())) == []


def test_the_record_kind_is_registered_and_validated(tmp_path: Path) -> None:
    from fr.artifacts.registry import artifact_kind, iter_artifact_paths

    kind = artifact_kind("record")
    assert kind.current_version == 1
    good = tmp_path / "docs/superpowers/runs/r.records/implement-phase__phase-2.yaml"
    good.parent.mkdir(parents=True)
    good.write_text(SPEC_EXAMPLE)
    assert list(iter_artifact_paths(tmp_path, "record")) == [good]
    assert kind.validate(good) == []
    bad = good.with_name("deliver.yaml")
    bad.write_text("bogus: 1\n")
    assert kind.validate(bad)
    # The records dir never reaches the run kind's own locator.
    assert list(iter_artifact_paths(tmp_path, "run")) == []
