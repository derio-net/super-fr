"""Phase-4 review fixes to the DevOps stage (spec 2026-10-22-fr-ops R15, p4-r1..r11)."""

from __future__ import annotations

from pathlib import Path

from fr.journal.model import JournalEntry, append_journal_entry, journal_path
from fr.ops.evidence import record_op
from fr.ops.gate import run
from fr.run.model import RunState, StepRecord, save_run_state
from typer.testing import CliRunner

from tests.unit.test_ops_gate import (
    HEAD,
    PLAN,
    SPEC,
    SPEC_SLUG,
    FakePrompt,
    _exec,
    _gate,
    _host,
    _record_stages,
)
from tests.unit.test_ops_gate import ops_root as ops_root  # noqa: F401 — the fixture


def _outcome(root: Path, sid: str, kind: str = "discovery", **extra: object) -> None:
    entry = JournalEntry(kind=kind, scope="spec", id=sid, created="2026-10-22T10:00:00+00:00",
                         title=sid, body="x", **extra)  # type: ignore[arg-type]  # fmt: skip
    append_journal_entry(journal_path(root, "spec", SPEC_SLUG), SPEC_SLUG, entry)


# ----------------------------------------------- p4-r1: the ops profile is pinned


def test_a_pr_modified_ops_profile_is_refused_before_anything_comes_up(ops_root: Path) -> None:
    gate, host, *_ = _gate(ops_root)
    host.changed = [".devcontainer/ops/devcontainer.json"]
    result = run(gate)
    assert result.failed == 1 and result.code == 2
    assert ".devcontainer/ops/devcontainer.json" in result.why and "own PR" in result.why
    assert not any(a[:2] == ["isolation", "up"] for a, _ in host.calls)
    diff = next(a for a, _ in host.calls if a[:1] == ["diff"])
    assert diff[1:3] == ["origin/main", HEAD]
    assert ".devcontainer/ops" in diff and ".devcontainer/fr-profiles.yaml" in diff


def test_a_reused_workspace_is_checked_too(ops_root: Path) -> None:
    gate, host, *_ = _gate(ops_root, up=True)
    host.changed = [".devcontainer/fr-profiles.yaml"]
    result = run(gate)
    assert result.failed == 1 and result.code == 2
    assert not any(a[:2] == ["isolation", "exec"] for a, _ in host.calls)


# --------------------------------- p4-r2: nothing the PR pre-commits closes anything


def test_pre_committed_done_entries_close_no_checked_op(ops_root: Path) -> None:
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    gate, host, tree, *_ = _gate(ops_root)
    tree.snapshot_head()
    run(gate)
    argvs = [a for a, _ in host.calls]
    assert _exec("ops", "apply", "pre", "--plan", PLAN, "--yes") in argvs
    assert _exec("ops", "apply", "mut", "--plan", PLAN, "--yes", "--yes-mutating") in argvs


def test_the_merge_gate_reads_live_status_not_the_journal(ops_root: Path) -> None:
    _record_stages(ops_root, 1)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    gate, host, tree, forge, prompt, _ = _gate(ops_root, up=True)  # live rows: OPEN
    result = run(gate)
    assert result.failed == 2 and "pre-merge ops are still open" in result.why
    assert not [c for c in forge.calls if c[0] == "merge"]


def test_the_merge_confirmation_shows_the_live_state(ops_root: Path) -> None:
    _record_stages(ops_root, 1)
    gate, host, tree, forge, prompt, _ = _gate(ops_root, up=True, live_closed=True)
    host.how["mut"] = "checked"
    run(gate)
    merge_q = next(a for a in prompt.asked if a.startswith("MERGE"))
    assert "pre: DONE" in merge_q and "mut: DONE" in merge_q


def test_a_pre_committed_attestation_closes_nothing(ops_root: Path) -> None:
    (ops_root / PLAN / "ops.yaml").write_text(
        "schema_version: 1\nops:\n  - {id: hand, summary: in a UI, phase: pre-merge}\n"
    )
    record_op(ops_root, "p", op="hand", result="attested", phase="pre-merge",
              attested_by="operator", reason="did it")  # fmt: skip
    gate, host, tree, *_ = _gate(ops_root)
    host.live = {"hand": "DONE"}
    host.how["hand"] = "attested"
    host.fail_apply = {"hand"}  # no apply: by hand, then attest on the ops branch
    tree.snapshot_head()
    result = run(gate)
    assert result.failed == 1 and "hand" in result.why


def test_an_attestation_added_on_the_ops_branch_closes_it(ops_root: Path) -> None:
    (ops_root / PLAN / "ops.yaml").write_text(
        "schema_version: 1\nops:\n  - {id: hand, summary: in a UI, phase: pre-merge}\n"
    )
    gate, host, tree, *_ = _gate(ops_root)
    tree.snapshot_head()  # nothing at the head
    record_op(ops_root, "p", op="hand", result="attested", phase="pre-merge",
              attested_by="operator", reason="did it")  # fmt: skip
    host.live = {"hand": "DONE"}
    host.how["hand"] = "attested"
    result = run(gate)
    assert result.failed != 1


def test_a_pre_committed_ran_outcome_is_asked_again(ops_root: Path) -> None:
    _outcome(ops_root, "test-plan-step-1")
    gate, host, tree, forge, prompt, _ = _gate(ops_root)
    tree.snapshot_head()
    run(gate)
    assert any(a.startswith("Test Plan step 1") for a in prompt.asked)
    rec = next(a for k, (a, _) in ((k, v) for k, v in tree.calls if k == "fr")
               if a[:2] == ["closeout", "outcome"])  # fmt: skip
    assert "--supersede" in rec


# ------------------------------------------------- p4-r3: an owed step recovers


def test_an_owed_step_then_a_ran_outcome_closes_it(ops_root: Path) -> None:
    from fr.ops.holds import gated_steps

    _outcome(ops_root, "test-plan-step-1", "owed")
    _outcome(ops_root, "test-plan-step-1-2", "discovery")
    steps = gated_steps(ops_root, _state_with_ops(), "devops")
    assert [k for _, k in steps] == ["discovery"]


def test_an_owed_step_resolved_fixed_closes_it(ops_root: Path) -> None:
    from fr.ops.holds import gated_steps

    _outcome(ops_root, "test-plan-step-1", "owed")
    _outcome(ops_root, "test-plan-step-1-fixed", "finding", resolves="test-plan-step-1",
             state="fixed")  # fmt: skip
    assert [k for _, k in gated_steps(ops_root, _state_with_ops(), "devops")] == ["discovery"]


def _state_with_ops() -> RunState:
    from tests.unit.test_ops_gate import _state

    return _state()


def test_stage_6_names_the_recovery_command_and_a_rerun_completes(ops_root: Path) -> None:
    gate, host, tree, forge, *_ = _gate(ops_root, prompt=FakePrompt(answers=["owed later"]))
    first = run(gate)
    assert first.failed == 6
    assert "fr isolation exec" in first.why and "--branch chore/ops-p" in first.why
    assert "fr closeout outcome --run run-1 --step 1" in first.why
    _outcome(ops_root, "test-plan-step-1-2", "discovery")  # what that command records
    from fr.ops.gate import Gate

    second = run(Gate(gate.target, host, forge, FakePrompt(), [].append, _host(ops_root)))
    assert second.ok and second.ran == (6, 7, 8)


def test_closeout_outcome_supersedes_an_owed_step(tmp_path: Path, monkeypatch) -> None:
    import subprocess

    from fr.cli import app

    root = tmp_path / "r"
    (root / "docs/superpowers/specs").mkdir(parents=True)
    (root / SPEC).write_text("# S\n\n## Test Plan\n\n- [devops] walk it\n")
    steps = {"brainstorm": StepRecord(state="done", emitted={"spec": SPEC})}
    save_run_state(root, RunState(run="r1", workflow="fr-goal@1", branch="feat/x",
                   started="2026-10-22T00:00:00+00:00", cursor="deliver",
                   steps=steps))  # fmt: skip
    subprocess.run(["git", "init", "-q", "-b", "feat/x", str(root)], check=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(root), "config", k, v], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "s"], check=True)
    monkeypatch.chdir(root)
    cli = CliRunner()
    base = ["closeout", "outcome", "--run", "r1", "--step", "1"]
    assert cli.invoke(app, [*base, "--owed", "--why", "later"]).exit_code == 0
    done = cli.invoke(app, [*base, "--ran", "--evidence", "walked"])
    assert done.exit_code == 0, done.output
    again = cli.invoke(app, [*base, "--ran", "--evidence", "twice"])
    assert again.exit_code != 0 and "already recorded" in again.output
    forced = cli.invoke(app, [*base, "--na", "--reason", "x", "--supersede"])
    assert forced.exit_code == 0, forced.output
    text = journal_path(root, "spec", SPEC_SLUG).read_text()
    assert "id=test-plan-step-1-2 " in text and "id=test-plan-step-1-3 " in text


# ------------------------------------------- p4-r4: stage 8 files the open ends


def test_stage_8_archives_with_the_out_of_scope_ids(ops_root: Path) -> None:
    entry = JournalEntry(kind="finding", scope="plan", id="p9-r1",
                         created="2026-10-22T10:00:00+00:00", title="t", body="b",
                         state="open")  # fmt: skip
    path = journal_path(ops_root, "plan", "p")
    append_journal_entry(path, "p", entry)
    append_journal_entry(path, "p", JournalEntry(
        kind="finding", scope="plan", id="p9-r1-oos", created="2026-10-22T10:01:00+00:00",
        title="t", body="b", state="open", resolves="p9-r1", out_of_scope=True))  # fmt: skip
    gate, host, tree, *_ = _gate(ops_root)
    assert run(gate).ok
    args = [a for k, (a, _) in ((k, v) for k, v in tree.calls if k == "fr") if a[:1] == ["archive"]]
    assert args == [["archive", "--branch", "feat/x", "--issues", "plan/p/p9-r1"]]


def test_stage_8_files_nothing_without_a_tracker_or_findings(ops_root: Path) -> None:
    gate, host, tree, *_ = _gate(ops_root)
    assert run(gate).ok
    args = [a for k, (a, _) in ((k, v) for k, v in tree.calls if k == "fr") if a[:1] == ["archive"]]
    assert args == [["archive", "--branch", "feat/x", "--no-issues"]]


# ----------------------------------------------------- p4-r10: a ready refusal


def test_a_ready_refusal_surfaces_as_a_refusal(ops_root: Path) -> None:
    gate, host, *_ = _gate(ops_root)
    host.ready_code = 2
    result = run(gate)
    assert result.failed == 3 and result.code == 2 and "refused" in result.why


# ------------------------------------------- p4-r11: marked only once pushed


def test_a_failed_push_leaves_the_stage_not_done(ops_root: Path) -> None:
    gate, host, tree, forge, *_ = _gate(ops_root)
    tree.push_error = "rejected"
    result = run(gate)
    assert result.failed == 1 and "rejected" in result.why
    assert 1 not in _host(ops_root).stages()
    tree.push_error = None
    from fr.ops.gate import Gate

    again = run(Gate(gate.target, host, forge, FakePrompt(), [].append, _host(ops_root)))
    assert again.ok and again.ran[0] == 1


def test_a_stage_is_committed_then_pushed_then_marked(ops_root: Path) -> None:
    gate, host, tree, *_ = _gate(ops_root)
    seen: list[str] = []
    real_mark = gate.state.mark

    def mark(n: int, *, head: str | None = None) -> None:
        seen.append(f"mark {n} after {tree.calls[-1][0]}")
        real_mark(n, head=head)

    gate.state.mark = mark  # type: ignore[method-assign]
    run(gate)
    assert seen[0] == "mark 1 after push"
