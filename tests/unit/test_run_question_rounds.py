"""The operator gate counts answered question ROUNDS and verifies the declared
count (spec `2026-09-26-dynamic-brainstorm-question-rounds-design.md` §3.B's
"Threading the declaration to the gate", §3.C, Test Plan 3, 4 and 7).

Every case runs through BOTH ways a declaration reaches `_gate_provenance`:
`fr run resolve --record` (the path fr-goal uses — a record's `questions:`
section) and the flag form (`--question-rounds/--round-two-trigger/
--round-two-reason`). A test of the flags alone would pass while the record
path never saw the value (Test Plan 7). Every refusal leaves the workspace —
cursor, record, journals — byte-identical and HEAD unmoved.

Transcripts are built from the CAPTURED records in `tests/fixtures/transcripts/`
via `tests.unit.transcript_sessions`, only re-keyed and re-timed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fr.journal.model import journal_path, parse_journal
from fr.run.model import load_run_state
from fr.run.telemetry import parse_timestamp

from tests.unit.record_support import (
    RUN,
    fr,
    head,
    implement_record,
    snapshot,
    started_run,
    write_record,
)
from tests.unit.transcript_sessions import (
    bash_rows,
    conversation_at,
    question_rows,
    text_row,
)

SPEC = "docs/superpowers/specs/2026-09-26-x-design.md"
SPEC_SLUG = "2026-09-26-x"
SESSION = "s-rounds"
PATHS = ["record", "flags"]
ANNOUNCED = "(Round 1 of 2) Which store owns the cursor?"
ROUND_TWO = {"rounds": 2, "trigger": "design-risk", "reason": "B vs C changes the store"}


def _blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """An fr-goal run blocked on its brainstorm operator gate, in a Claude Code
    session whose transcript lives under `tmp_path/projects`. Returns the
    workspace and a transcript stamp at/after the moment the gate blocked."""
    from tests.integration.test_fr_goal_shape import _workspace

    root = _workspace(tmp_path, "feat/x")
    start = ["run", "start", "fr-goal", "--branch", "feat/x", "--run-id", RUN]
    assert fr(root, start).exit_code == 0
    assert "blocked on operator gate" in fr(root, ["run", "advance", RUN]).output
    spec = root / SPEC
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# x design\n")
    blocked_at = parse_timestamp(load_run_state(root, RUN).steps["brainstorm"].at)
    assert blocked_at is not None
    monkeypatch.setenv("FR_HARNESS", "claude-code")
    monkeypatch.setenv("FR_TRANSCRIPT_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SESSION)
    return root, blocked_at.strftime("%Y-%m-%dT%H:%M:%S.999Z")


def _transcript(tmp_path: Path, at: str, rounds: list[str | None]) -> None:
    """A session with one answered round per entry, each closed by a `Bash`
    call; the entry is the first question's text (`None` keeps the captured)."""
    rows: list[dict[str, Any]] = []
    for n, first in enumerate(rounds):
        rows += question_rows(at, tool_use_id=f"toolu_q{n}a", first_question=first)
        rows.append(text_row(at))
        rows += question_rows(at, tool_use_id=f"toolu_q{n}b")
        rows += bash_rows(at, tool_use_id=f"toolu_b{n}")
    conversation_at(tmp_path / "projects", rows, session_id=SESSION)


def _flags(questions: dict[str, Any] | None) -> list[str]:
    if questions is None:
        return []
    argv = ["--question-rounds", str(questions["rounds"])]
    if "trigger" in questions:
        argv += ["--round-two-trigger", questions["trigger"]]
    if "reason" in questions:
        argv += ["--round-two-reason", questions["reason"]]
    return argv


def _resolve_brainstorm(root: Path, path: str, questions: dict[str, Any] | None):
    """Resolve the brainstorm gate `done` declaring `questions` via `path`.
    The record is written first, so a snapshot taken after this call's
    record write is what "byte-identical" compares against."""
    if path == "record":
        data: dict[str, Any] = {
            "run": RUN, "step": "brainstorm", "outcome": "done", "emitted": {"spec": SPEC},
        }  # fmt: skip
        if questions is not None:
            data["questions"] = questions
        rec = write_record(root, data)
        return lambda: fr(
            root, ["run", "resolve", RUN, "--step", "brainstorm", "--record", str(rec)]
        )
    argv = ["run", "resolve", RUN, "--step", "brainstorm", "--state", "done"]
    argv += ["--emitted", f"spec={SPEC}", *_flags(questions)]
    return lambda: fr(root, argv)


def _refused(root: Path, run, *needles: str) -> None:
    files, before = snapshot(root), head(root)
    out = run()
    assert out.exit_code == 2, out.output
    flat = " ".join(out.output.split())
    for needle in needles:
        assert needle in flat, flat
    assert snapshot(root) == files and head(root) == before
    assert load_run_state(root, RUN).steps["brainstorm"].state == "blocked"


def _cleared(root: Path, run) -> Any:
    out = run()
    assert out.exit_code == 0, out.output
    step = load_run_state(root, RUN).steps["brainstorm"]
    assert step.state == "done"
    return step


def _decisions(root: Path) -> list[str]:
    target = journal_path(root, "spec", SPEC_SLUG)
    if not target.is_file():
        return []
    return [e.id for e in parse_journal(target.read_text()) if e.id.startswith("gate-")]


# --- §3.C, row by row --------------------------------------------------------


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("declared", [None, {"rounds": 1}])
def test_one_round_declared_one_is_the_operator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str, declared: dict | None
) -> None:
    root, at = _blocked(tmp_path, monkeypatch)
    _transcript(tmp_path, at, [None])

    step = _cleared(root, _resolve_brainstorm(root, path, declared))

    assert step.answered_by == "operator"
    assert _decisions(root) == []  # rounds: 1 is the default and writes nothing


@pytest.mark.parametrize("path", PATHS)
def test_an_announced_design_risk_second_round_is_the_operator_and_journalled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    root, at = _blocked(tmp_path, monkeypatch)
    _transcript(tmp_path, at, [ANNOUNCED, None])

    step = _cleared(root, _resolve_brainstorm(root, path, ROUND_TWO))

    assert step.answered_by == "operator"
    assert _decisions(root) == ["gate-question-rounds-brainstorm"]
    entry = parse_journal(journal_path(root, "spec", SPEC_SLUG).read_text())[0]
    assert entry.kind == "decision"
    assert "design-risk" in entry.body and "B vs C changes the store" in entry.body


@pytest.mark.parametrize("path", PATHS)
def test_the_round_two_decision_is_logged_once_on_a_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    root, at = _blocked(tmp_path, monkeypatch)
    _transcript(tmp_path, at, [ANNOUNCED, None])
    target = journal_path(root, "spec", SPEC_SLUG)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"# Journal: {SPEC_SLUG}\n\n"
        "<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm "
        "created=2026-09-26T00:00:00 -->\n"
        "### gate-question-rounds-brainstorm · decision · an earlier attempt\n\nfirst\n"
    )

    _cleared(root, _resolve_brainstorm(root, path, ROUND_TWO))

    assert _decisions(root) == ["gate-question-rounds-brainstorm"]


@pytest.mark.parametrize("path", PATHS)
def test_an_unannounced_design_risk_second_round_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    root, at = _blocked(tmp_path, monkeypatch)
    _transcript(tmp_path, at, [None, None])

    _refused(
        root,
        _resolve_brainstorm(root, path, ROUND_TWO),
        "not told a second round would follow",
        "Round 1 of 2",
    )


@pytest.mark.parametrize("path", PATHS)
def test_an_operator_requested_second_round_needs_no_announcement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    root, at = _blocked(tmp_path, monkeypatch)
    _transcript(tmp_path, at, [None, None])
    declared = {"rounds": 2, "trigger": "operator-request", "reason": "asked to go deeper"}

    step = _cleared(root, _resolve_brainstorm(root, path, declared))

    assert step.answered_by == "operator"
    assert _decisions(root) == ["gate-question-rounds-brainstorm"]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("declared", [None, {"rounds": 1}])
def test_two_rounds_declared_one_is_refused_naming_both_numbers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str, declared: dict | None
) -> None:
    root, at = _blocked(tmp_path, monkeypatch)
    _transcript(tmp_path, at, [ANNOUNCED, None])

    _refused(
        root,
        _resolve_brainstorm(root, path, declared),
        "shows 2 answered question rounds",
        "declares 1",
        "rounds: 2",
    )


@pytest.mark.parametrize("path", PATHS)
def test_one_round_declared_two_is_refused_naming_both_numbers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """Test Plan 7: the declaration reaches the gate on BOTH paths."""
    root, at = _blocked(tmp_path, monkeypatch)
    _transcript(tmp_path, at, [ANNOUNCED])

    _refused(
        root,
        _resolve_brainstorm(root, path, ROUND_TWO),
        "shows 1 answered question round",
        "declares 2",
    )


@pytest.mark.parametrize("path", PATHS)
def test_three_rounds_are_refused_whatever_is_declared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    root, at = _blocked(tmp_path, monkeypatch)
    _transcript(tmp_path, at, [ANNOUNCED, None, None])

    _refused(root, _resolve_brainstorm(root, path, ROUND_TWO), "never a round 3")


@pytest.mark.parametrize("path", PATHS)
def test_zero_answered_rounds_keeps_the_existing_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    root, _ = _blocked(tmp_path, monkeypatch)
    conversation_at(tmp_path / "projects", [], session_id=SESSION)

    _refused(root, _resolve_brainstorm(root, path, ROUND_TWO), "no answered question")


@pytest.mark.parametrize("path", PATHS)
def test_an_unobservable_gate_records_the_declaration_as_claimed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    root, _ = _blocked(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s-missing")
    run = _resolve_brainstorm(root, path, ROUND_TWO)

    out = run()

    assert out.exit_code == 0, out.output
    flat = " ".join(out.output.split())
    assert "could not verify" in flat
    assert "rounds: 2" in flat
    assert _decisions(root) == ["gate-question-rounds-brainstorm"]


# --- where a declaration may not appear --------------------------------------


@pytest.mark.parametrize("path", PATHS)
def test_questions_on_a_resolve_that_clears_no_gate_are_refused(tmp_path: Path, path: str) -> None:
    root = started_run(tmp_path)
    argv = ["run", "resolve", RUN, "--step", "implement-phase", "--item", "phase/1"]
    if path == "record":
        rec = write_record(root, implement_record(questions=ROUND_TWO))
        argv += ["--record", str(rec)]
    else:
        argv += ["--state", "done", *_flags(ROUND_TWO)]
    files, before = snapshot(root), head(root)

    out = fr(root, argv)

    assert out.exit_code == 2, out.output
    assert "clears none" in " ".join(out.output.split())
    assert snapshot(root) == files and head(root) == before


@pytest.mark.parametrize(
    "flags",
    [
        ["--question-rounds", "1"],
        ["--round-two-trigger", "design-risk"],
        ["--round-two-reason", "why"],
    ],
)
def test_the_round_flags_are_refused_beside_a_record(tmp_path: Path, flags: list[str]) -> None:
    root = started_run(tmp_path)
    rec = write_record(root, implement_record())
    files = snapshot(root)
    argv = ["run", "resolve", RUN, "--step", "implement-phase", "--item", "phase/1"]

    out = fr(root, [*argv, "--record", str(rec), *flags])

    assert out.exit_code == 2, out.output
    assert flags[0] in out.output
    assert snapshot(root) == files


@pytest.mark.parametrize(
    ("flags", "needle"),
    [
        (["--question-rounds", "2"], "trigger"),
        (["--question-rounds", "2", "--round-two-trigger", "design-risk"], "reason"),
        (["--question-rounds", "1", "--round-two-trigger", "design-risk"], "only for rounds: 2"),
        (["--question-rounds", "3"], "question-rounds"),
        (["--round-two-trigger", "design-risk"], "--question-rounds"),
        (["--no-questions", "--reason", "x", "--question-rounds", "1"], "--no-questions"),
    ],
)
def test_an_invalid_flag_declaration_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flags: list[str], needle: str
) -> None:
    root, at = _blocked(tmp_path, monkeypatch)
    _transcript(tmp_path, at, [None])
    argv = ["run", "resolve", RUN, "--step", "brainstorm", "--state", "done"]
    argv += ["--emitted", f"spec={SPEC}", *flags]

    _refused(root, lambda: fr(root, argv), needle)


# --- the verdict table itself, pure ------------------------------------------


def _round(*texts: str) -> Any:
    from fr.run.telemetry import Round

    return Round(question_texts=texts, answered=True)


@pytest.mark.parametrize(
    ("observed", "declared", "refusal"),
    [
        ([("q",)], None, None),
        ([("q",)], {"rounds": 1}, None),
        ([("Round 1 of 2: q",), ("q",)], ROUND_TWO, None),
        ([("ROUND 1 OF 2 — q",), ("q",)], ROUND_TWO, None),
        ([("q",), ("Round 1 of 2",)], ROUND_TWO, "not told"),
        ([("q",), ("q",)], {**ROUND_TWO, "trigger": "operator-request"}, None),
        ([("q",), ("q",)], None, "declares 1"),
        ([("q",)], ROUND_TWO, "declares 2"),
        ([("Round 1 of 2",), ("q",), ("q",)], ROUND_TWO, "never a round 3"),
    ],
)
def test_the_verdict_table(
    observed: list[tuple[str, ...]], declared: dict | None, refusal: str | None
) -> None:
    from fr.commands.run_cmd import question_rounds_refusal
    from fr.record.model import QuestionRounds

    questions = None if declared is None else QuestionRounds(**declared)
    got = question_rounds_refusal([_round(*t) for t in observed], questions)
    if refusal is None:
        assert got is None
    else:
        assert got is not None and refusal in got
