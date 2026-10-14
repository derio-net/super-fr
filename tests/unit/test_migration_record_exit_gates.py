"""Record kind 9 -> 10 (spec 2026-10-14 exit-gates §C, R12): the step record's
`JournalItem` gains `gate` and `narrows`, the Owner gate a decision records. The
record model is closed-world and read by released fr versions, so the kind moves:
a stamp migration, the structure validator, and this repo's records migrated.
Nothing is removed or moved, so no frozen legacy model is owed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION
from fr.record.model import RECORD_SCHEMA_VERSION, JournalItem, parse_record

_V9 = """\
schema_version: 9
run: r1
step: implement-phase
item: phase/1
outcome: done
ticks: [P1.T1.S1]
journal:
  - {kind: decision, id: d1, title: plain decision}
"""


def _record_file(root: Path, text: str = _V9) -> Path:
    path = root / "docs" / "superpowers" / "runs" / "r1.records" / "implement-phase__phase-1.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_journal_item_accepts_gate_and_narrows() -> None:
    item = JournalItem.model_validate(
        {
            "kind": "decision",
            "title": "t",
            "gate": "owner",
            "narrows": ["derio-net/super-fr#1", "#2"],
            "answered_by": "operator",
        }
    )
    assert item.gate == "owner"
    assert item.narrows == ("derio-net/super-fr#1", "#2")


def test_the_record_kind_is_at_version_ten() -> None:
    assert RECORD_SCHEMA_VERSION == 10
    assert artifact_kind("record").current_version == 10


def test_the_chain_from_one_reaches_ten_hop_by_hop() -> None:
    chain = MIGRATIONS.chain("record", PRE_FRAMEWORK_VERSION)
    assert [s.to_version for s in chain] == [2, 3, 4, 5, 6, 7, 8, 9, 10]
    hop = MIGRATIONS.chain("record", 9)[0]
    assert (hop.from_version, hop.to_version) == (9, 10)


def test_a_v9_record_is_stamped_with_no_body_rewrite(tmp_path: Path) -> None:
    path = _record_file(tmp_path)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert path.read_text() == _V9.replace("schema_version: 9\n", "schema_version: 10\n")
    assert parse_record(path.read_text()).schema_version == 10


def test_an_unreadable_v9_record_is_refused_and_left_alone(tmp_path: Path) -> None:
    bad = _V9.replace("outcome: done", "outcome: done\nnot_a_field: 1")
    path = _record_file(tmp_path, bad)

    report = run_migrations(tmp_path, dry_run=False)

    assert not report.ok
    assert path.read_text() == bad


def _brainstorm(tmp_path: Path, evidence: dict[str, str] | None, **extra: object):
    from fr.journal.model import parse_journal

    from tests.integration.test_fr_goal_shape import _workspace
    from tests.unit.record_support import RUN, fr, write_record
    from tests.unit.requirements_support import seed_requirements

    root = _workspace(tmp_path, "feat/x")
    assert (
        fr(root, ["run", "start", "fr-goal", "--branch", "feat/x", "--run-id", RUN]).exit_code == 0
    )
    assert "blocked on operator gate" in fr(root, ["run", "advance", RUN]).output
    spec_rel = "docs/superpowers/specs/2026-09-25-x-design.md"
    (root / spec_rel).parent.mkdir(parents=True, exist_ok=True)
    (root / spec_rel).write_text("# x design\n")
    seed_requirements(root, spec_rel)
    data: dict[str, object] = {
        "run": RUN,
        "step": "brainstorm",
        "outcome": "done",
        "emitted": {"spec": spec_rel},
        "journal": [
            {"kind": "decision", "id": "narrow-1", "title": "ships half", "narrows": ["#1"]},
            {"kind": "decision", "id": "plain-1", "title": "kept it flat"},
            {"kind": "decision", "id": "own-1", "title": "the agent's", "answered_by": "agent"},
        ],
        **extra,
    }
    if evidence is not None:
        data["evidence"] = evidence
    rec = write_record(root, data)
    out = fr(root, ["run", "resolve", RUN, "--step", "brainstorm", "--record", str(rec)])
    assert out.exit_code == 0, out.output
    journal = root / "docs/superpowers/journals/specs/2026-09-25-x.md"
    return {e.id: e for e in parse_journal(journal.read_text())}


def _answered(tmp_path: Path, monkeypatch, *, question: str, answer: str | None = None) -> None:
    """An observable Claude Code session with one answered round, after the gate."""
    from tests.unit.transcript_sessions import ORCHESTRATOR, question_rows, records, write_session

    rows = question_rows(
        "2099-01-01T00:00:00.000Z", tool_use_id="toolu_q1", first_question=question
    )
    if answer is not None:
        rows[1]["toolUseResult"]["answers"] = {question: answer}
    write_session(tmp_path / "projects", session_id="s-q", rows=[*records(ORCHESTRATOR), *rows])
    monkeypatch.setenv("FR_HARNESS", "claude-code")
    monkeypatch.setenv("FR_TRANSCRIPT_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s-q")


def test_an_observed_operator_gate_stamps_its_ordinary_decisions(
    tmp_path: Path, monkeypatch
) -> None:
    _answered(tmp_path, monkeypatch, question="Should the parser stay flat?")
    entries = _brainstorm(tmp_path, None)
    assert entries["plain-1"].decided_by == "operator"
    assert entries["own-1"].decided_by == "agent"  # an explicit `agent` is kept
    for e in entries.values():
        assert e.answered_by is None  # never the released fr's resolution-only token


def test_p3_r2_a_narrowing_no_answered_round_names_stays_the_agents(
    tmp_path: Path, monkeypatch
) -> None:
    _answered(tmp_path, monkeypatch, question="Should the parser stay flat?")
    entries = _brainstorm(tmp_path, None)
    assert entries["narrow-1"].decided_by is None


@pytest.mark.parametrize("where", ["question", "answer"])
def test_p3_r2_a_narrowing_an_answered_round_names_is_the_operators(
    tmp_path: Path, monkeypatch, where: str
) -> None:
    if where == "question":
        _answered(tmp_path, monkeypatch, question="Ship only half of #1 here?")
    else:
        _answered(tmp_path, monkeypatch, question="How much ships?", answer="Half; #1's rest later")
    entries = _brainstorm(tmp_path, None)
    assert entries["narrow-1"].decided_by == "operator"


def test_p3_r3_an_unobserved_gate_never_stamps_a_narrowing_and_notes_the_rest(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("FR_HARNESS", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    entries = _brainstorm(tmp_path, {"answered_by": "operator"})
    assert entries["narrow-1"].decided_by is None
    assert entries["plain-1"].decided_by == "operator"
    assert "recorded unverified" in entries["plain-1"].body


def test_p3_r3_an_unobserved_gate_claimed_by_the_agent_stamps_nothing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("FR_HARNESS", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    entries = _brainstorm(tmp_path, {"answered_by": "agent"})
    assert entries["plain-1"].decided_by is None and entries["narrow-1"].decided_by is None


def test_a_brainstorm_cleared_without_asking_writes_no_operator_answer(tmp_path: Path) -> None:
    entries = _brainstorm(
        tmp_path, None, no_questions=True, reason="the request decided everything"
    )
    assert entries["narrow-1"].decided_by is None
    assert entries["plain-1"].decided_by is None


def test_p3_r8_the_migration_names_every_field_it_adds() -> None:
    from fr.artifacts.record_exit_gates import RECORD_EXIT_GATES_MIGRATION

    for field in ("gate", "narrows", "filed_as"):
        assert field in RECORD_EXIT_GATES_MIGRATION.description


def test_the_validator_accepts_both_fields(tmp_path: Path) -> None:
    text = _V9.replace("schema_version: 9", "schema_version: 10").replace(
        "{kind: decision, id: d1, title: plain decision}",
        "{kind: decision, id: d1, title: t, gate: owner, narrows: ['#1'], answered_by: operator}",
    )
    path = _record_file(tmp_path, text)
    assert artifact_kind("record").validate(path) == []


# --- p3-r2 addendum: exact ref matching (parser differential) ------------------------


def _decider(text: str, narrows: tuple[str, ...], identity=("derio-net", "super-fr")):
    from fr.commands.run_cmd import GateAnswer
    from fr.record.apply import _Context, _stamped_decider
    from fr.run.telemetry import Round

    ctx = _Context(
        scope="spec", slug="s", journal_file=None, plan_dir=None, phase=None,
        completes_phase=False, emits_ticks=False,
        gate_answer=GateAnswer("operator", observed=True, rounds=(Round(question_texts=(text,)),)),
        identity=identity,
    )  # fmt: skip
    return _stamped_decider(ctx, narrows)[0]


@pytest.mark.parametrize(
    ("text", "narrows", "want"),
    [
        ("Ship half of #12 here?", ("#1",), None),  # `#1` never matches `#12`
        ("Ship half of #123 here?", ("#12",), None),
        ("Ship half of #12 here?", ("derio-net/super-fr#12",), "operator"),
        ("See https://github.com/derio-net/super-fr/issues/12", ("#12",), "operator"),
        (
            "Ship half of #12 here?",
            ("https://github.com/derio-net/super-fr/issues/12",),
            "operator",
        ),
        ("Ship half of other/repo#12?", ("#12",), None),  # another repo's #12
        ("Ship half of #12 here?", ("other/repo#12",), None),
        ("Ship half of other/repo#12?", ("other/repo#12",), "operator"),
        ("Ship #12 and #13?", ("#12", "#14"), None),  # every ref, not some
    ],
)
def test_p3_r2_narrowed_refs_match_answered_rounds_exactly(
    text: str, narrows: tuple[str, ...], want: str | None
) -> None:
    assert _decider(text, narrows) == want


def test_p3_r2_an_unknown_repo_identity_stamps_no_narrowing() -> None:
    assert _decider("Ship half of #12 here?", ("#12",), identity=None) is None
