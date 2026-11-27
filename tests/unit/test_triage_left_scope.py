"""`left_scope` and the `left-scope` stage (spec 2026-11-27-closeout-state R4)."""

from __future__ import annotations

from typing import Any

from fr.triage.batch import derive_batch_stage, is_open, left_scope
from fr.triage.model import Batch, Facts, Truncation

from tests.unit.triage_board_fixtures import (
    batch,
    dispatch,
    facts,
    issue,
    pr,
)


CANCEL_EVENT = {"kind": "cancel", "at": "2026-10-01T12:00:00Z", "reason": "superseded"}


def _b(bid: str = "a", **kw: Any) -> Batch:
    return Batch.model_validate(batch(bid, [1], **kw))


def _gone(f: Facts) -> Facts:
    return f.model_copy(update={"repos": ["example-org/other"]})


def _truncated(f: Facts) -> Facts:
    warn = Truncation(source="repos", target="example-org", limit=100)
    return _gone(f).model_copy(update={"warnings": [warn]})


def test_left_scope_is_true_when_the_repo_is_not_in_the_facts() -> None:
    f = facts([issue(1)])
    assert left_scope(_b(), f) is False
    assert left_scope(_b(), _gone(f)) is True


def test_left_scope_is_false_when_the_repo_list_was_truncated() -> None:
    assert left_scope(_b(), _truncated(facts([issue(1)]))) is False


def test_a_truncation_of_another_list_does_not_hide_a_departure() -> None:
    warn = Truncation(source="issues", target="example-org/widgets", limit=100)
    f = _gone(facts([issue(1)])).model_copy(update={"warnings": [warn]})
    assert left_scope(_b(), f) is True


def test_the_stage_is_left_scope_for_a_dispatched_batch() -> None:
    f = _gone(facts([issue(1)]))
    assert derive_batch_stage(_b(events=[dispatch("a")]), f) == "left-scope"


def test_the_stage_is_left_scope_for_a_merged_batch() -> None:
    merged = pr(10, "feat/batch-a", state="MERGED", merged_at="2026-10-01T09:00:00Z")
    f = facts([issue(1, state="closed", prs=[merged])])
    b = _b(events=[dispatch("a")])
    assert derive_batch_stage(b, f) == "merged"
    assert derive_batch_stage(b, _gone(f)) == "left-scope"


def test_the_stage_is_left_scope_for_a_never_dispatched_batch() -> None:
    f = facts([issue(1)])
    assert derive_batch_stage(_b(), f) == "proposed"
    assert derive_batch_stage(_b(), _gone(f)) == "left-scope"


def test_a_cancelled_batch_stays_cancelled() -> None:
    b = _b(events=[dispatch("a"), CANCEL_EVENT])
    assert derive_batch_stage(b, _gone(facts([issue(1)]))) == "cancelled"


def test_a_truncated_repo_list_keeps_today_s_stage() -> None:
    b = _b(events=[dispatch("a")])
    assert derive_batch_stage(b, _truncated(facts([issue(1)]))) == "dispatched"


def test_the_old_stage_returns_with_the_repo() -> None:
    f = facts([issue(1)])
    b = _b(events=[dispatch("a")])
    assert derive_batch_stage(b, _gone(f)) == "left-scope"
    assert derive_batch_stage(b, f) == "dispatched"


def test_a_left_scope_batch_is_not_open() -> None:
    f = facts([issue(1)])
    assert is_open(_b(), f) is True
    assert is_open(_b(), _gone(f)) is False
