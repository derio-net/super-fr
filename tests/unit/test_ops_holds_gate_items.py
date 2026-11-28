"""`fr.ops.holds.gate_items` / `gate_blockers` (spec 2026-11-27-ops-gate-truth R10): every
thing a post-merge gate owns — ops (devops only), Test Plan steps and acceptance rows —
discharged or not, each with a one-line reason; rows judged by `row_walked`."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.model import Walk
from fr.journal.model import JournalEntry, append_journal_entry, journal_path
from fr.ops.evidence import record_op
from fr.ops.holds import GateItem, devops_blockers, gate_blockers, gate_items
from fr.run.model import RunState, StepRecord

from tests.unit.requirements_support import row, write_matrix

SPEC = "docs/superpowers/specs/2026-11-27-g-design.md"
PLAN = "docs/superpowers/plans/p"
SECTION = """## Verification

strategy: none
gate: developer
- rt: live — the tester walks it
- rd: live — the devops stage walks it
gate: rd=devops
"""
TEST_PLAN = """## Test Plan

- [devops] (rows: rd) walk the stage
- [tester] (rows: rt) click the page
"""
OPS = "schema_version: 1\nops:\n  - id: k\n    summary: s\n    phase: post-merge\n"
STATE = RunState(
    run="run-1",
    workflow="fr-goal@1",
    branch="feat/x",
    started="2026-11-27T00:00:00+00:00",
    cursor="deliver",
    steps={
        "brainstorm": StepRecord(state="done", emitted={"spec": SPEC}),
        "plan": StepRecord(state="done", emitted={"plan": PLAN}),
    },
)


def _walk(outcome: str = "pass", at: str = "2026-11-27T10:00:00Z", harness: str = "a") -> dict:
    return {"strategy": "live", "harness": harness, "model": "m", "outcome": outcome,
            "at": at, "evidence": "e"}  # fmt: skip


def _repo(tmp_path: Path, *, rd: dict | None = None, rt: dict | None = None) -> Path:
    root = tmp_path / "r"
    (root / "docs/superpowers/specs").mkdir(parents=True)
    (root / SPEC).write_text(f"# G\n\n{SECTION}\n{TEST_PLAN}")
    write_matrix(
        root,
        [
            {**row(SPEC, rid="rd", status="walk-owed"), **(rd or {})},
            {**row(SPEC, rid="rt", status="walk-owed"), **(rt or {})},
        ],
    )
    (root / PLAN).mkdir(parents=True)
    (root / PLAN / "ops.yaml").write_text(OPS)
    return root


def _outcome(root: Path, n: int) -> None:
    slug = "2026-11-27-g"
    entry = JournalEntry(kind="discovery", scope="spec", id=f"test-plan-step-{n}",
                         created="2026-11-27T10:00:00+00:00", title=f"step {n} ran",
                         body="ran it")  # fmt: skip
    append_journal_entry(journal_path(root, "spec", slug), slug, entry)


def _by_what(items: list[GateItem]) -> dict[str, GateItem]:
    return {i.what: i for i in items}


def test_devops_items_list_every_op_step_and_row_with_reasons(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    items = _by_what(gate_items(root, STATE, "devops"))
    assert set(items) == {"op k [post-merge]", "Test Plan step 1 (devops)", "row rd (devops)"}
    assert not any(i.discharged for i in items.values())
    assert "no walk" in items["row rd (devops)"].why
    assert "no recorded outcome" in items["Test Plan step 1 (devops)"].why


def test_a_walked_row_and_recorded_step_and_closed_op_are_discharged(tmp_path: Path) -> None:
    root = _repo(tmp_path, rd={"status": "walked", "walks": [_walk()]})
    _outcome(root, 1)
    record_op(root, "p", op="k", result="attested", phase="post-merge", attested_by="operator")
    items = gate_items(root, STATE, "devops")
    assert all(i.discharged for i in items), items
    assert gate_blockers(root, STATE, "devops") == []


def test_a_failing_latest_walk_holds_the_row(tmp_path: Path) -> None:
    walks = [_walk(), _walk("fail", "2026-11-27T11:00:00Z")]
    root = _repo(tmp_path, rd={"status": "walked", "walks": walks})
    item = _by_what(gate_items(root, STATE, "devops"))["row rd (devops)"]
    assert not item.discharged and "latest walk failed" in item.why


def test_a_row_still_owing_a_harness_says_which(tmp_path: Path) -> None:
    root = _repo(tmp_path, rd={"harnesses": ["a", "b"], "walks": [_walk()]})
    item = _by_what(gate_items(root, STATE, "devops"))["row rd (devops)"]
    assert not item.discharged and "b" in item.why and "owed" in item.why


def test_exclude_walks_turns_a_walked_row_owed(tmp_path: Path) -> None:
    root = _repo(tmp_path, rd={"status": "walked", "walks": [_walk()]})
    excluded = {"rd": {Walk.model_validate(_walk())}}
    item = _by_what(gate_items(root, STATE, "devops", exclude_walks=excluded))["row rd (devops)"]
    assert not item.discharged


def test_gate_blockers_are_the_owed_lines_and_devops_blockers_equals_them(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    blockers = gate_blockers(root, STATE, "devops")
    assert blockers == devops_blockers(root, STATE)
    assert any(b.startswith("row rd (devops): ") for b in blockers)
    assert any(b.startswith("op k [post-merge]: ") for b in blockers)


def test_tester_items_hold_no_op(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    items = _by_what(gate_items(root, STATE, "tester"))
    assert set(items) == {"Test Plan step 2 (tester)", "row rt (tester)"}


def test_under_acceptance_off_no_row_is_an_item(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    monkeypatch.setattr("fr.settings.disabled", lambda r, f: f == "acceptance")
    items = _by_what(gate_items(root, STATE, "devops"))
    assert not any(w.startswith("row ") for w in items)
