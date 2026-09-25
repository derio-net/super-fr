"""Phase-3 review fixes to the step-record engine (spec
2026-09-25-lean-cost-aware-process §5.C): p3-r1 (operator claims verified on
the record path), p3-r2 (the flag form reaches deliver's live-PR check),
p3-r3 (atomicity: crash, retry, restore), p3-r4 (flags beside --record),
p3-r7 (deliver's tests= gate through a record), p3-r9 (where a record may
live) and p3-r10 (one line, stdout and stderr together)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.journal.model import effective_finding_states, journal_path, parse_journal
from fr.parser import parse
from fr.run import units
from fr.run.model import load_run_state

from tests.unit.record_support import (
    PLAN_REL,
    RUN,
    SLUG,
    commit_all,
    fr,
    git,
    head,
    implement_record,
    snapshot,
    started_run,
    write_record,
)
from tests.unit.test_deliver_pr_body import PR, _at_deliver, _body
from tests.unit.test_record_apply import _implemented, _resolve, _review_record


def _world(root: Path) -> dict[str, object]:
    """Everything a resolve decides, minus timestamps — what "converges to the
    same final state as a clean apply" compares."""
    entries = parse_journal(journal_path(root, "plan", SLUG).read_text())
    phase = parse(root / PLAN_REL).phases[0]
    state = load_run_state(root, RUN)
    return {
        "ids": sorted(e.id for e in entries),
        "findings": effective_finding_states(entries),
        "ticks": {k: v.state for k, v in phase.state.steps.items()},
        "complete": bool(phase.state.completion.at),
        "units": units.unit_states(state.steps["implement"]),
        "cursor": state.cursor,
        "dirty": git(root, "status", "--porcelain", "--", "docs").strip(),
    }


def _clean_apply(tmp_path: Path) -> dict[str, object]:
    (tmp_path / "clean").mkdir()
    root = started_run(tmp_path / "clean")
    record = write_record(root, implement_record())
    commit_all(root, "record")
    out = _resolve(root, record)
    assert out.exit_code == 0, out.output
    return _world(root)


def _crash(root: Path, record: Path) -> None:
    try:
        out = _resolve(root, record)
    except KeyboardInterrupt:
        return
    assert out.exit_code != 0, out.output


# --- p3-r1 -------------------------------------------------------------------


def test_a_record_fixing_an_out_of_scope_finding_as_operator_is_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.transcript_sessions import asked_at

    (tmp_path / "w").mkdir()
    root = _implemented(
        tmp_path / "w",
        resolves=[{"id": "p1-f1", "state": "out-of-scope", "body": "not ours"}],
    )
    fix = {"id": "p1-f1", "state": "fixed", "body": "fixed anyway", "answered_by": "operator"}
    record = write_record(root, _review_record(resolves=[fix]))
    # A question answered long BEFORE the finding went out of scope answered
    # something else: the claim is observable here, and does not hold.
    asked_at(tmp_path / "projects", "2000-01-01T00:00:00.000Z", session_id="s-q")
    monkeypatch.setenv("FR_HARNESS", "claude-code")
    monkeypatch.setenv("FR_TRANSCRIPT_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s-q")
    files, before = snapshot(root), head(root)

    out = _resolve(root, record, step="review-phase")

    assert out.exit_code == 2, out.output
    assert "no answered question" in out.output
    assert snapshot(root) == files and head(root) == before


# --- p3-r3 -------------------------------------------------------------------


def test_a_crash_at_the_commit_restores_everything_and_a_retry_converges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import run_cmd

    clean = _clean_apply(tmp_path)
    (tmp_path / "crash").mkdir()
    root = started_run(tmp_path / "crash")
    record = write_record(root, implement_record())
    commit_all(root, "record")
    files, before = snapshot(root), head(root)

    def die(*_a: object, **_k: object) -> None:
        raise KeyboardInterrupt

    with monkeypatch.context() as m:
        m.setattr(run_cmd, "commit_records", die)
        _crash(root, record)

    # Every byte — the cursor and the journal included — is back, record too.
    assert snapshot(root) == files and head(root) == before
    assert record.exists()
    out = _resolve(root, record)
    assert out.exit_code == 0, out.output
    assert _world(root) == clean
    assert not record.exists()


def test_a_retry_heals_a_half_applied_tree_instead_of_wedging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A kill between the writes and the commit runs no restore at all: the
    journal and plan carry the record, the cursor does not. Re-applying the
    same record is a no-op for what already landed."""
    from fr.commands import run_cmd
    from fr.record import apply as engine

    clean = _clean_apply(tmp_path)
    (tmp_path / "half").mkdir()
    root = started_run(tmp_path / "half")
    record = write_record(root, implement_record())
    commit_all(root, "record")

    def die(*_a: object, **_k: object) -> None:
        raise KeyboardInterrupt

    with monkeypatch.context() as m:
        m.setattr(engine, "_restore", lambda *_a: None)
        m.setattr(run_cmd, "resolve_in_process", die)
        _crash(root, record)
    assert "d-p1" in journal_path(root, "plan", SLUG).read_text(), "not half-applied"
    assert record.exists()

    out = _resolve(root, record)

    assert out.exit_code == 0, out.output
    assert _world(root) == clean


def test_a_retry_whose_entry_changed_still_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import run_cmd
    from fr.record import apply as engine

    root = started_run(tmp_path)
    record = write_record(root, implement_record())
    commit_all(root, "record")

    def die(*_a: object, **_k: object) -> None:
        raise KeyboardInterrupt

    with monkeypatch.context() as m:
        m.setattr(engine, "_restore", lambda *_a: None)
        m.setattr(run_cmd, "resolve_in_process", die)
        _crash(root, record)
    journal = [
        {"kind": "decision", "id": "d-p1", "title": "kept it flat", "body": "a different why"}
    ]
    record = write_record(root, implement_record(journal=journal, resolves=None))

    out = _resolve(root, record)

    assert out.exit_code == 2, out.output
    assert "d-p1" in out.output and "already exists" in out.output


def test_a_raise_after_a_commit_landed_leaves_the_tree_equal_to_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`deliver` commits mid-way (before its closeout lines); restoring after
    that would put the tree BEHIND the commit that recorded it."""
    from fr import gh as fr_gh
    from fr.commands import run_cmd
    from fr.record.pr_body import REQUIRED_SECTIONS

    root = _at_deliver(tmp_path)
    body = "\n".join(REQUIRED_SECTIONS)
    monkeypatch.setattr(fr_gh, "view_pr_body", lambda ref, *, cwd=None: body)
    data = {
        "run": RUN, "step": "deliver", "outcome": "done",
        "emitted": {"pr": PR}, "evidence": {"tests": "suite.log"},
    }  # fmt: skip
    rec = write_record(root, data)
    commit_all(root, "deliver record")
    (root / "suite.log").write_text("n passed\n")  # newer than the unit

    def boom(*_a: object, **_k: object) -> list[str]:
        raise RuntimeError("after the commit")

    monkeypatch.setattr(run_cmd, "_closeout_handoff_lines", boom)
    out = fr(root, ["run", "resolve", RUN, "--step", "deliver", "--record", str(rec)])

    assert out.exit_code != 0, out.output
    assert git(root, "status", "--porcelain", "--", "docs").strip() == ""
    assert load_run_state(root, RUN).steps["deliver"].state == "done"
    assert not rec.exists()


# --- p3-r2 / p3-r7 -----------------------------------------------------------


def _flag_deliver(root: Path):
    return fr(
        root,
        [
            "run", "resolve", RUN, "--step", "deliver", "--state", "done",
            "--emitted", f"pr={PR}", "--evidence", "tests=suite.log",
        ],
    )  # fmt: skip


def test_the_flag_form_deliver_is_refused_without_the_out_of_scope_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr import gh as fr_gh

    root = _at_deliver(tmp_path)
    live = {"body": "## Summary\n\n## Findings\n\n## Proportionality\n\n## Cost\n"}
    monkeypatch.setattr(fr_gh, "view_pr_body", lambda ref, *, cwd=None: live["body"])

    out = _flag_deliver(root)

    assert out.exit_code == 2, out.output
    assert "Out-of-scope findings" in out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "running"
    assert _body(root).exists()

    live["body"] = _body(root).read_text()
    (root / "suite.log").write_text("n passed\n")
    out = _flag_deliver(root)
    assert out.exit_code == 0, out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "done"
    assert not _body(root).exists()


@pytest.mark.parametrize("log", ["absent", "stale"])
def test_deliver_tests_log_gate_fires_through_a_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, log: str
) -> None:
    from fr import gh as fr_gh

    root = _at_deliver(tmp_path)
    monkeypatch.setattr(fr_gh, "view_pr_body", lambda ref, *, cwd=None: "")
    if log == "absent":
        (root / "suite.log").unlink()
    else:
        os.utime(root / "suite.log", (946684800, 946684800))  # 2000-01-01
    data = {
        "run": RUN, "step": "deliver", "outcome": "done",
        "emitted": {"pr": PR}, "evidence": {"tests": "suite.log"},
    }  # fmt: skip
    rec = write_record(root, data)
    files, before = snapshot(root), head(root)

    out = fr(root, ["run", "resolve", RUN, "--step", "deliver", "--record", str(rec)])

    assert out.exit_code == 2, out.output
    assert "tests=suite.log" in out.output
    assert snapshot(root) == files and head(root) == before
    assert load_run_state(root, RUN).steps["deliver"].state == "running"


# --- p3-r4 -------------------------------------------------------------------


@pytest.mark.parametrize(
    "flags",
    [
        ["--no-questions", "--reason", "x"],
        ["--answered-by", "agent"],
        ["--agent", "a-1"],
        ["--harness", "claude-code"],
        ["--model", "m"],
    ],
)
def test_flags_the_record_carries_are_refused_beside_it(tmp_path: Path, flags: list[str]) -> None:
    root = started_run(tmp_path)
    record = write_record(root, implement_record())
    files = snapshot(root)
    argv = ["run", "resolve", RUN, "--step", "implement-phase", "--item", "phase/1"]

    out = fr(root, [*argv, "--record", str(record), *flags])

    assert out.exit_code == 2, out.output
    assert flags[0] in out.output
    assert snapshot(root) == files


def test_a_brainstorm_record_expresses_the_no_questions_bypass(tmp_path: Path) -> None:
    from tests.integration.test_fr_goal_shape import _workspace

    root = _workspace(tmp_path, "feat/x")
    assert (
        fr(root, ["run", "start", "fr-goal", "--branch", "feat/x", "--run-id", RUN]).exit_code == 0
    )
    assert "blocked on operator gate" in fr(root, ["run", "advance", RUN]).output
    spec = root / "docs" / "superpowers" / "specs" / "2026-09-25-x-design.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# x design\n")
    data = {
        "run": RUN, "step": "brainstorm", "outcome": "done",
        "emitted": {"spec": "docs/superpowers/specs/2026-09-25-x-design.md"},
        "no_questions": True, "reason": "the request decided everything",
    }  # fmt: skip
    rec = write_record(root, data)

    out = fr(root, ["run", "resolve", RUN, "--step", "brainstorm", "--record", str(rec)])

    assert out.exit_code == 0, out.output
    state = load_run_state(root, RUN)
    assert state.steps["brainstorm"].state == "done"
    journals = "".join(
        p.read_text() for p in (root / "docs" / "superpowers" / "journals").rglob("*.md")
    )
    assert "gate-no-questions-brainstorm" in journals
    assert "the request decided everything" in journals


# --- p3-r9 -------------------------------------------------------------------


def test_a_record_outside_the_runs_records_dir_is_refused(tmp_path: Path) -> None:
    root = started_run(tmp_path)
    stray = root / "notes.yaml"
    stray.write_text(write_record(root, implement_record()).read_text())
    commit_all(root, "stray")
    files, before = snapshot(root), head(root)

    out = _resolve(root, stray)

    assert out.exit_code == 2, out.output
    assert "records dir" in out.output
    assert snapshot(root) == files and head(root) == before


def test_a_relative_record_path_resolves_against_the_repo_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = started_run(tmp_path)
    record = write_record(root, implement_record())
    commit_all(root, "record")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    out = _resolve(root, record.relative_to(root))

    assert out.exit_code == 0, out.output
    assert not record.exists()


# --- p3-r10 ------------------------------------------------------------------


def test_a_successful_resolve_prints_one_line_on_stdout_and_stderr_together(
    tmp_path: Path,
) -> None:
    root = started_run(tmp_path)
    record = write_record(root, implement_record())
    commit_all(root, "record")

    out = _resolve(root, record)

    assert out.exit_code == 0, out.output
    assert len(out.output.splitlines()) == 1, out.output
    assert "fr: committed" not in out.output
