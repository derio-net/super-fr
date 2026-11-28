"""`fr.run.dod.definition_of_done` (spec 2026-11-27-ops-gate-truth R17): a run's Definition
of Done, derived from what its spec, plan and journals already declare — each post-merge
gate's `gate_items`, the plan's `[manual]` phases and the open `owed` entries no other group
already reports."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fr.journal.model import JournalEntry, append_journal_entry, journal_path, owed_body
from fr.ops.evidence import record_op
from fr.run.dod import DefinitionOfDone, DodError, definition_of_done
from fr.run.model import RunState, StepRecord

from tests.unit.requirements_support import row, write_matrix

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
SPEC = "docs/superpowers/specs/2026-11-27-g-design.md"
SPEC_SLUG = "2026-11-27-g"
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
MANUAL = """schema_version: 2
phase:
  number: {n}
  title: Walk it live {n}
  tag: manual
  depends_on: [1]
  tracking_issue: null
  files: []
tasks:
  - number: 1
    title: Walk
    steps:
      - id: P{n}.T1.S1
        text: Walk the widget
state:
  steps:
    P{n}.T1.S1:
      state: "{tick}"
      ticked_at: null
      note: null
  completion:
    at: null
    note: null
    observed_prs: []
"""


def _state(*, spec: bool = True, plan: bool = True) -> RunState:
    steps = {}
    if spec:
        steps["brainstorm"] = StepRecord(state="done", emitted={"spec": SPEC})
    if plan:
        steps["plan"] = StepRecord(state="done", emitted={"plan": PLAN})
    return RunState(run="run-1", workflow="fr-goal@1", branch="feat/x",
                    started="2026-11-27T00:00:00+00:00", cursor="deliver",
                    steps=steps)  # fmt: skip


def _walk() -> dict:
    return {"strategy": "live", "harness": "a", "model": "m", "outcome": "pass",
            "at": "2026-11-27T10:00:00Z", "evidence": "e"}  # fmt: skip


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
    plan = root / PLAN
    shutil.copytree(FIXTURE, plan)
    (plan / "01.yaml").write_text((plan / "01.yaml").read_text().replace('state: " "', "state: x"))
    (plan / "02.yaml").write_text(MANUAL.format(n=2, tick=" "))
    (plan / "03.yaml").write_text(MANUAL.format(n=3, tick="x"))
    (plan / "ops.yaml").write_text(OPS)
    return root


def _entry(root: Path, scope: str, slug: str, **kw: object) -> None:
    entry = JournalEntry(scope=scope, created="2026-11-27T10:00:00+00:00", **kw)  # type: ignore[arg-type]
    append_journal_entry(journal_path(root, scope, slug), slug, entry)  # type: ignore[arg-type]


def _owed(root: Path, scope: str, slug: str, eid: str, key: str, title: str) -> None:
    body = owed_body(what="w", why="y", how="h", key=key)
    _entry(root, scope, slug, kind="owed", id=eid, title=title, body=body)


def _group(dod: DefinitionOfDone, name: str) -> dict[str, tuple[bool, str]]:
    found = [g for g in dod.groups if g.name == name]
    assert len(found) == 1, [g.name for g in dod.groups]
    return {i.what: (i.discharged, i.why) for i in found[0].items}


def test_the_gate_groups_hold_their_gate_items_discharged_ones_included(tmp_path: Path) -> None:
    root = _repo(tmp_path, rd={"status": "walked", "walks": [_walk()]})
    dod = definition_of_done(root, _state())
    devops = _group(dod, "gate:devops")
    assert set(devops) == {"op k [post-merge]", "Test Plan step 1 (devops)", "row rd (devops)"}
    assert devops["row rd (devops)"] == (True, "walked")
    assert not devops["op k [post-merge]"][0]
    tester = _group(dod, "gate:tester")
    assert set(tester) == {"Test Plan step 2 (tester)", "row rt (tester)"}
    assert not dod.discharged


def test_manual_phases_an_unticked_one_owed_a_ticked_one_discharged(tmp_path: Path) -> None:
    dod = definition_of_done(_repo(tmp_path), _state())
    manual = _group(dod, "manual phases")
    assert [w for w in manual] == ["phase 2 [manual]", "phase 3 [manual]"]
    assert not manual["phase 2 [manual]"][0] and "Walk it live 2" in manual["phase 2 [manual]"][1]
    assert manual["phase 3 [manual]"][0]


def test_owed_holds_open_entries_not_reported_by_another_group(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _owed(root, "spec", SPEC_SLUG, "test-plan-step-1", f"spec:{SPEC_SLUG}#step1", "step 1 owed")
    _owed(root, "plan", "p", "manual-phase-2", "plan:p#p2", "p: manual phase 2 is not ticked")
    _owed(root, "plan", "p", "walk-the-dog", "plan:p#p1", "walk the dog after merge")
    _owed(root, "spec", SPEC_SLUG, "paid", f"spec:{SPEC_SLUG}#step9", "settled already")
    _entry(root, "spec", SPEC_SLUG, kind="finding", id="paid-done", resolves="paid",
           state="fixed", title="settled", body="done")  # fmt: skip
    owed = _group(definition_of_done(root, _state()), "owed")
    assert owed == {"owed walk-the-dog (plan journal)": (False, "walk the dog after merge")}


def test_discharged_only_when_every_item_is(tmp_path: Path) -> None:
    root = _repo(tmp_path, rd={"status": "walked", "walks": [_walk()]},
                 rt={"status": "walked", "walks": [_walk()]})  # fmt: skip
    (root / PLAN / "02.yaml").write_text(MANUAL.format(n=2, tick="x"))
    record_op(root, "p", op="k", result="attested", phase="post-merge", attested_by="operator")
    for n in (1, 2):
        _entry(root, "spec", SPEC_SLUG, kind="discovery", id=f"test-plan-step-{n}",
               title=f"Test Plan step {n}: ran", body="ran it")  # fmt: skip
    dod = definition_of_done(root, _state())
    assert dod.discharged, [(g.name, i) for g in dod.groups for i in g.items if not i.discharged]
    assert dod.owed() == []


def test_a_run_with_no_plan_or_no_spec_yields_the_groups_it_can(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    no_plan = definition_of_done(root, _state(plan=False))
    assert _group(no_plan, "manual phases") == {}
    assert "gate:tester" in [g.name for g in no_plan.groups]
    no_spec = definition_of_done(root, _state(spec=False))
    assert "gate:devops" in [g.name for g in no_spec.groups]  # promoted by the plan's ops
    assert _group(no_spec, "owed") == {}
    nothing = definition_of_done(root, _state(spec=False, plan=False))
    assert nothing.discharged


def test_an_unreadable_plan_is_a_dod_error(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / PLAN / "_meta.yaml").write_text("schema_version: [\n")
    with pytest.raises(DodError):
        definition_of_done(root, _state())


def test_an_unreadable_ops_file_is_a_dod_error(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / PLAN / "ops.yaml").write_text("ops: [\n")
    with pytest.raises(DodError):
        definition_of_done(root, _state())


def test_p3_r3_a_recorded_plan_that_cannot_be_found_is_a_dod_error(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    shutil.rmtree(root / PLAN)
    with pytest.raises(DodError, match="plan"):
        definition_of_done(root, _state())


def test_p3_r1_excluded_resolution_records_do_not_close_an_owed_entry(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _owed(root, "plan", "p", "walk-the-dog", "plan:p#p1", "walk the dog after merge")
    _entry(root, "plan", "p", kind="finding", id="dog-walked", resolves="walk-the-dog",
           state="fixed", title="walked", body="done")  # fmt: skip
    assert _group(definition_of_done(root, _state()), "owed") == {}
    held = definition_of_done(root, _state(), exclude_entries={"plan": {"dog-walked"}})
    assert "owed walk-the-dog (plan journal)" in _group(held, "owed")


def test_p3_r1_an_excluded_manual_tick_reads_unticked(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    dod = definition_of_done(root, _state(), exclude_manual_ticks={3})
    discharged, why = _group(dod, "manual phases")["phase 3 [manual]"]
    assert not discharged and "PR head" in why
