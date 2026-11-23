"""The devops promotion and the pre-merge hold (spec 2026-10-22-fr-ops R13, R14, §H)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.gates import POST_MERGE_GATES, PRE_MERGE_HOLD_GATES
from fr.ops.load import plan_has_ops
from fr.run.model import RunState, StepRecord
from fr.verification.exit import exit_for_spec, run_exit
from fr.verification.labels import desired_labels

from tests.unit.requirements_support import row, write_matrix

SPEC = "docs/superpowers/specs/s.md"
PLAN = "docs/superpowers/plans/p"
OPS = """schema_version: 1
ops:
  - id: create-key
    summary: create the key
    phase: {phase}
"""
LEGACY_STEP = """\
- id: P1.T1.S1
  text: |
    Do it.
    ```yaml
    # manual-operation
    id: legacy-op
    why_manual: needs a UI
    ```
"""


def _repo(tmp_path: Path, *, gate: str = "developer", ops: str | None = None) -> RunState:
    (tmp_path / "docs/superpowers/specs").mkdir(parents=True)
    (tmp_path / SPEC).write_text(f"# S\n\n## Verification\n\nstrategy: none\ngate: {gate}\n")
    write_matrix(tmp_path, [row(SPEC, rid="r1")])
    (tmp_path / PLAN).mkdir(parents=True)
    if ops is not None:
        (tmp_path / PLAN / "ops.yaml").write_text(OPS.format(phase=ops))
    return RunState(
        run="r",
        workflow="fr-goal@1",
        branch="feat/x",
        started="2026-10-22T00:00:00+00:00",
        cursor="deliver",
        steps={
            "brainstorm": StepRecord(state="done", emitted={"spec": SPEC}),
            "plan": StepRecord(state="done", emitted={"plan": PLAN}),
        },
    )


def test_a_plan_without_ops_keeps_its_exit_exactly(tmp_path: Path) -> None:
    state = _repo(tmp_path)
    exit_ = run_exit(tmp_path, state)
    assert exit_.gates == frozenset({"developer"}) and not exit_.is_gated
    assert exit_.gates == exit_for_spec(tmp_path, SPEC).gates
    assert not plan_has_ops(tmp_path, tmp_path / PLAN)


@pytest.mark.parametrize("phase", ["pre-merge", "post-merge"])
def test_any_op_adds_devops_beside_the_declared_gate(tmp_path: Path, phase: str) -> None:
    state = _repo(tmp_path, ops=phase)
    exit_ = run_exit(tmp_path, state)
    assert exit_.gates == frozenset({"developer", "devops"})
    assert exit_.run_gate == "developer" and exit_.is_gated
    names = {lb.name for lb in desired_labels(exit_.kinds, exit_.gates)}
    assert "gate:devops" in names


def test_a_declared_tester_gate_is_kept_beside_devops(tmp_path: Path) -> None:
    state = _repo(tmp_path, gate="tester", ops="post-merge")
    assert run_exit(tmp_path, state).gates == frozenset({"tester", "devops"})


def test_a_legacy_step_block_counts_as_an_op(tmp_path: Path) -> None:
    state = _repo(tmp_path)
    (tmp_path / PLAN / "01.yaml").write_text(
        "phase: 1\ntitle: t\ntasks:\n  - id: P1.T1\n    title: t\n    steps:\n"
        + "\n".join("      " + ln for ln in LEGACY_STEP.splitlines())
        + "\n"
    )
    assert plan_has_ops(tmp_path, tmp_path / PLAN)
    assert "devops" in run_exit(tmp_path, state).gates


def test_an_archived_plan_still_promotes(tmp_path: Path) -> None:
    state = _repo(tmp_path, ops="post-merge")
    archived = tmp_path / "docs/superpowers/implemented/plans/p"
    archived.parent.mkdir(parents=True)
    (tmp_path / PLAN).rename(archived)
    assert "devops" in run_exit(tmp_path, state).gates


def test_an_unreadable_ops_yaml_holds_rather_than_drops_the_gate(tmp_path: Path) -> None:
    state = _repo(tmp_path)
    (tmp_path / PLAN / "ops.yaml").write_text("schema_version: 1\nops: [ {id: \n")
    assert "devops" in run_exit(tmp_path, state).gates


def test_the_gate_constants() -> None:
    assert PRE_MERGE_HOLD_GATES == frozenset({"devops"})
    assert POST_MERGE_GATES == frozenset({"tester", "devops"})


def _queue_view(labels: tuple[str, ...]) -> tuple[list[str], list[str]]:
    """What the pass does with a green, approved batch PR carrying *labels*: the queue's
    entries and the held reports (the retired train's `held` lines, kept: R22)."""
    from datetime import UTC, datetime

    from fr.triage.approval import Approved
    from fr.triage.batch import QueueEntry
    from fr.triage.batch_drive import LivePr, Snapshot, drive_pass
    from fr.triage.model import Batch, PullRequest
    from fr.triage.wave_queue import QueueConfig

    batch = Batch.model_validate({
        "id": "b1", "title": "b1", "ids": ["super-fr#1"], "wave": 1,
        "events": [{"kind": "dispatch", "at": "2026-11-20T09:00:00Z", "runner": "fake",
                    "handle": "h", "branch": "feat/batch-b1"}],
    })  # fmt: skip
    pr = PullRequest(repo="o/r", number=1001, title="t", state="OPEN", is_draft=False,
                     merged_at=None, created_at="2026-11-20T09:30:00+00:00", url="u",
                     head_ref="feat/batch-b1", head_oid="h1", labels=list(labels))  # fmt: skip
    live = LivePr(number=1001, state="OPEN", draft=False, head="h1", labels=labels)
    snap = Snapshot(
        batches=(batch,), stages={"b1": "pr-open"}, queue=(QueueEntry(batch, pr),),
        live={"b1": live}, repos={"b1": "o/r"}, now=datetime(2026, 11, 20, 12, tzinfo=UTC),
        approvals={"b1": Approved("h1")}, wave_queues={"o/r": QueueConfig()},
    )  # fmt: skip
    plan = drive_pass(snap)
    opened = [a.kind for q in plan.queues for a in q.actions if a.kind == "queue-open"]
    return opened, [a.detail for a in plan.actions if a.kind == "held"]


def test_the_merge_path_holds_a_pr_labelled_gate_devops() -> None:
    entries, held = _queue_view(("approved-fr", "gate:devops"))
    assert entries == []  # the DevOps stage owns that merge, not the queue
    assert any("gate:devops" in h and "fr ops gate" in h for h in held)


def test_the_merge_path_lets_a_passed_devops_gate_through() -> None:
    entries, held = _queue_view(("approved-fr", "gate:devops", "gate:devops-passed"))
    assert entries == ["queue-open"] and held == []


def test_a_gate_tester_label_does_not_hold_the_merge() -> None:
    entries, held = _queue_view(("approved-fr", "gate:tester"))
    assert entries == ["queue-open"] and held == []


def test_p2_r5_gates_off_promotes_no_devops_gate(tmp_path: Path) -> None:
    """R8: under `gates: off` a plan with ops is still not promoted to `devops`."""
    from fr.verification.exit import _promote

    from tests.unit.settings_repo import git

    state = _repo(tmp_path, ops="pre-merge")
    assert run_exit(tmp_path, state).ops_promoted is True
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / ".fr").mkdir()
    (tmp_path / ".fr" / "settings.yaml").write_text("artifacts:\n  gates: off\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "settings")
    exit_ = run_exit(tmp_path, state)
    assert "devops" not in exit_.gates and exit_.ops_promoted is False
    assert _promote(exit_, tmp_path, state) is exit_
