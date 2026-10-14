"""`fr verification set` and its downgrade guard — spec 2026-10-14 exit-gates R8."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.journal.model import journal_path, parse_journal, spec_journal_slug
from fr.verification import labels as labels_mod
from fr.verification.labels import SyncOutcome

from tests.unit.record_support import RUN, commit_all, fr, git, head, write_record
from tests.unit.test_record_apply import _at_spec_review, _resolve, _spec_review_record

SPEC = "docs/spec.md"
SECTION = (
    "\n## Verification\n\nstrategy: live\ngate: tester\n- req-r1: live — needs a release\n"
    "\nprose stays.\n"
)


class _Sync:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, *_a: object, **_k: object) -> SyncOutcome:
        self.calls += 1
        return SyncOutcome(synced=True)


@pytest.fixture(autouse=True)
def sync(monkeypatch: pytest.MonkeyPatch) -> _Sync:
    fake = _Sync()
    monkeypatch.setattr(labels_mod, "sync_exit_labels", fake)
    return fake


def _at(tmp_path: Path, section: str | None = SECTION, *, past_review: bool = False) -> Path:
    root = _at_spec_review(tmp_path)
    if section is not None:
        with (root / SPEC).open("a") as f:
            f.write(section)
    commit_all(root, "spec section")
    if past_review:
        out = _resolve(
            root, write_record(root, _spec_review_record()), step="spec-review", item=None
        )
        assert out.exit_code == 0, out.output
        commit_all(root, "after spec-review")
    return root


def _set(root: Path, *args: str):
    return fr(root, ["verification", "set", "--run", RUN, "--reason", "because", *args])


def _decisions(root: Path):
    slug = spec_journal_slug(Path(SPEC).stem)
    path = journal_path(root, "spec", slug)
    return [e for e in parse_journal(path.read_text()) if e.id.startswith("exit-change-")]


def test_set_rewrites_one_line_journals_the_reason_commits_and_resyncs(
    tmp_path: Path, sync: _Sync
) -> None:
    root = _at(tmp_path)
    before, calls = (root / SPEC).read_text(), sync.calls
    out = _set(root, "--strategy", "candidate")
    assert out.exit_code == 0, out.output
    after = (root / SPEC).read_text()
    assert after == before.replace("strategy: live\n", "strategy: candidate\n", 1)
    (decision,) = _decisions(root)
    assert decision.id == "exit-change-1" and decision.kind == "decision"
    assert "because" in decision.body and "candidate" in decision.body
    assert git(root, "status", "--porcelain").strip() == ""
    assert "verification" in git(root, "log", "-3", "--format=%s")
    assert sync.calls == calls + 1


def test_a_second_change_numbers_its_decision(tmp_path: Path) -> None:
    root = _at(tmp_path)
    assert _set(root, "--strategy", "candidate").exit_code == 0
    assert _set(root, "--strategy", "live").exit_code == 0
    assert [e.id for e in _decisions(root)] == ["exit-change-1", "exit-change-2"]


def test_a_row_and_a_gate_are_written_beside_their_kind(tmp_path: Path) -> None:
    root = _at(tmp_path)
    assert (
        _set(root, "--row", "req-r1", "--strategy", "candidate", "--gate", "tester").exit_code == 0
    )
    text = (root / SPEC).read_text()
    assert "- req-r1: candidate — because\n" in text and "gate: req-r1=tester\n" in text
    assert "prose stays." in text


def test_a_spec_with_no_section_is_refused_with_how_to_add_one(tmp_path: Path) -> None:
    root = _at(tmp_path, section=None)
    before = (root / SPEC).read_text()
    out = _set(root, "--strategy", "candidate")
    assert out.exit_code == 2 and "## Verification" in out.output
    assert (root / SPEC).read_text() == before and _no_journal(root)


def _no_journal(root: Path) -> bool:
    slug = spec_journal_slug(Path(SPEC).stem)
    path = journal_path(root, "spec", slug)
    return not path.exists() or not any(
        e.id.startswith("exit-change-") for e in parse_journal(path.read_text())
    )


def test_an_unknown_row_is_refused(tmp_path: Path) -> None:
    root = _at(tmp_path)
    out = _set(root, "--row", "nope", "--strategy", "candidate")
    assert out.exit_code == 2 and "nope" in out.output and _no_journal(root)


def test_before_spec_review_there_is_no_guard(tmp_path: Path) -> None:
    root = _at(tmp_path)  # spec-review not done
    assert _set(root, "--strategy", "none").exit_code == 0


@pytest.mark.parametrize(
    "args",
    [
        ("--strategy", "candidate"),  # the run's kind drops from post-merge
        ("--strategy", "live", "--gate", "none"),  # the run gate leaves the post-merge set
        ("--row", "req-r1", "--strategy", "candidate"),  # one row's kind is lowered
        ("--row", "req-r1", "--strategy", "live", "--gate", "developer"),  # a row gate leaves
    ],
)
def test_after_spec_review_waiting_less_is_refused_and_writes_nothing(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    root = _at(tmp_path, past_review=True)
    before, tip = (root / SPEC).read_text(), head(root)
    out = _set(root, *args)
    assert out.exit_code == 2, out.output
    assert "--answered-by operator" in out.output
    assert (root / SPEC).read_text() == before and head(root) == tip and _no_journal(root)


def test_after_spec_review_waiting_more_needs_no_answer(tmp_path: Path) -> None:
    root = _at(tmp_path, "\n## Verification\n\nstrategy: candidate\n", past_review=True)
    assert _set(root, "--strategy", "live").exit_code == 0


def test_a_verified_operator_answer_allows_the_downgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _at(tmp_path, past_review=True)
    monkeypatch.setattr("fr.run.telemetry.operator_answered_since", lambda env, since: True)
    out = _set(root, "--strategy", "candidate", "--answered-by", "operator")
    assert out.exit_code == 0, out.output
    (decision,) = _decisions(root)
    assert "operator" in decision.body


def test_an_unheld_operator_claim_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _at(tmp_path, past_review=True)
    before = (root / SPEC).read_text()
    monkeypatch.setattr("fr.run.telemetry.operator_answered_since", lambda env, since: False)
    out = _set(root, "--strategy", "candidate", "--answered-by", "operator")
    assert out.exit_code == 2 and "does not hold" in out.output
    assert (root / SPEC).read_text() == before and _no_journal(root)


def test_an_agent_answer_does_not_lift_the_guard(tmp_path: Path) -> None:
    root = _at(tmp_path, past_review=True)
    out = _set(root, "--strategy", "candidate", "--answered-by", "agent")
    assert out.exit_code == 2
